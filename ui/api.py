import asyncio
import os
import json
import time
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form
from fastapi import Query
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from ui.runner import AutomationRunner, RunnerEvents
from ui.workflows import list_workflows, load_workflow, save_workflow, validate_workflow_dict, Workflow
from ui.state import get_recent_episodes, get_projects, add_projects, save_projects, add_projects_with_data, add_projects_with_records
from ui.locator_library import list_locators, save_locator, delete_locator
from heygen_automation import HeyGenAutomation
import pandas as pd
import io

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

runner = AutomationRunner("config.json")
events = RunnerEvents()
_progress: Dict[str, Any] = {"done": 0, "total": 0, "done_parts": 0, "total_parts": 0, "done_scenes": 0, "total_scenes": 0}
_log: List[Dict[str, Any]] = []
_run_task: Optional[asyncio.Task] = None
_tasks: Dict[str, Dict[str, Any]] = {}
_active_tasks: Dict[str, asyncio.Task] = {}
_task_pause: Dict[str, asyncio.Event] = {}
_global_pause = asyncio.Event()
_global_pause.set()
_sem = asyncio.Semaphore(int(getattr(runner, "max_concurrency", 2) or 2))

def _now_ts() -> int:
    try:
        return int(time.time())
    except Exception:
        return 0

def _task_key(episode: str, part: int) -> str:
    return f"{episode}::{int(part)}"

def _ensure_task(episode: str, part: int) -> Dict[str, Any]:
    ep = str(episode or "")
    p = int(part or 0)
    k = _task_key(ep, p)
    t = _tasks.get(k)
    if isinstance(t, dict):
        return t
    t = {
        "key": k,
        "episode": ep,
        "part": p,
        "status": "queued",
        "stage": "",
        "error": "",
        "started_at": None,
        "finished_at": None,
        "scene_done": 0,
        "scene_total": 0,
        "report": None,
    }
    _tasks[k] = t
    return t

def _set_task_status(t: Dict[str, Any], status: str) -> None:
    t["status"] = str(status or "")
    if status in ("success", "failed", "stopped") and not t.get("finished_at"):
        t["finished_at"] = _now_ts()

def _set_csv_file(path: str) -> None:
    runner.config["csv_file"] = path
    runner.csv_path = path
    runner.automation = HeyGenAutomation(path, runner.config)
    try:
        runner.automation.set_hooks(on_notice=runner.events.on_notice, on_step=runner.events.on_step)
    except Exception:
        pass

def _apply_workflow_settings(workflow: Optional[str]) -> None:
    runner.config.pop("workflow_file", None)
    runner.config.pop("workflow_steps", None)
    if not workflow:
        return
    p = os.path.join(os.getcwd(), "workflows", workflow)
    wf = load_workflow(p)
    if wf.settings:
        runner.config.update(wf.settings)
    runner.config["workflow_file"] = workflow
    runner.config["workflow_steps"] = [s.model_dump() for s in (wf.steps or [])]

def _normalize_project_row(row: Dict[str, Any], episode_id: str) -> Dict[str, Any]:
    r = dict(row or {})
    if "episode_id" not in r:
        if "episode" in r:
            r["episode_id"] = r.get("episode")
        elif "id" in r:
            r["episode_id"] = r.get("id")
        else:
            r["episode_id"] = episode_id
    if "part_idx" not in r and "part" in r:
        r["part_idx"] = r.get("part")
    if "scene_idx" not in r:
        for cand in ("scene", "scene_number"):
            if cand in r:
                r["scene_idx"] = r.get(cand)
                break
    if "brolls" not in r and "broll_query" in r:
        r["brolls"] = r.get("broll_query")
    return r

def _write_projects_csv(episodes: List[str]) -> str:
    items = get_projects()
    all_rows: List[Dict[str, Any]] = []
    for ep in episodes:
        pr = _find_project(items, ep)
        if not pr:
            raise HTTPException(status_code=404, detail=f"project not found: {ep}")
        data = pr.get("data") or []
        if not isinstance(data, list) or len(data) == 0:
            raise HTTPException(status_code=400, detail=f"project has no rows: {ep}")
        for row in data:
            if not isinstance(row, dict):
                continue
            all_rows.append(_normalize_project_row(row, ep))

    required = ["episode_id", "part_idx", "scene_idx", "text"]
    for c in required:
        if any(c not in r for r in all_rows):
            raise HTTPException(status_code=400, detail=f"missing column: {c}")

    df = pd.DataFrame(all_rows)
    cols = list(df.columns)
    ordered = [c for c in required if c in cols] + [c for c in cols if c not in required]
    df = df[ordered]
    state_dir = os.path.join(os.getcwd(), "state")
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, f"run_projects_{int(time.time())}.csv")
    df.to_csv(path, index=False)
    return path

def _project_public(pr: Dict[str, Any], include_data: bool) -> Dict[str, Any]:
    out = {"episode": pr.get("episode"), "status": pr.get("status"), "created_at": pr.get("created_at")}
    if include_data and "data" in pr:
        out["data"] = pr.get("data")
    return out

def _as_int(v) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        if v != v:
            return None
        try:
            return int(v)
        except Exception:
            return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return int(float(s))
    except Exception:
        return None

def _nonempty(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    return bool(str(v).strip())

def _project_stats(pr: Dict[str, Any]) -> Dict[str, Any]:
    rows = pr.get("data") or []
    if not isinstance(rows, list):
        rows = []

    parts_vals = []
    speakers = []
    seen_speakers = set()
    broll_count = 0
    template_url = None

    for r in rows:
        if not isinstance(r, dict):
            continue
        part = _as_int(r.get("part_idx") if "part_idx" in r else r.get("part"))
        if part is not None:
            parts_vals.append(part)
        sp = r.get("speaker")
        if _nonempty(sp):
            sp_s = str(sp).strip()
            if sp_s not in seen_speakers:
                seen_speakers.add(sp_s)
                speakers.append(sp_s)
        if _nonempty(r.get("broll_query")) or _nonempty(r.get("brolls")):
            broll_count += 1
        if template_url is None and _nonempty(r.get("template_url")):
            template_url = str(r.get("template_url")).strip()

    scene_col = None
    for candidate in ("scene_idx", "scene", "scene_number"):
        if any(isinstance(r, dict) and candidate in r for r in rows):
            scene_col = candidate
            break

    if scene_col:
        scenes = sum(1 for r in rows if isinstance(r, dict) and _nonempty(r.get(scene_col)))
        if scenes == 0:
            scenes = len(rows)
    else:
        scenes = len(rows)

    parts_max = max(parts_vals) if parts_vals else 0

    return {
        "parts": parts_max,
        "scenes": scenes,
        "rows": len(rows),
        "speakers": speakers,
        "brolls": broll_count,
        "template_url": template_url,
    }

def _project_response(pr: Dict[str, Any], include_data: bool) -> Dict[str, Any]:
    return {"project": _project_public(pr, include_data), "stats": _project_stats(pr)}

def _find_project(items: List[Dict[str, Any]], episode_id: str) -> Optional[Dict[str, Any]]:
    for pr in items:
        if isinstance(pr, dict) and str(pr.get("episode")) == str(episode_id):
            return pr
    return None

def _on_notice(msg: str):
    if runner.cancel:
        return
    _log.append({"level": "info", "msg": msg})

def _on_progress(p):
    global _progress
    if runner.cancel:
        return
    try:
        for k, v in (p or {}).items():
            _progress[k] = v
    except Exception:
        _progress = p

def _on_step(s):
    global _progress
    try:
        st = str((s or {}).get("type") or "")
        ep = (s or {}).get("episode")
        part = (s or {}).get("part")
        if ep is not None and part is not None:
            t = _ensure_task(str(ep), int(part))
            t["stage"] = st
            if st == "start_part":
                t["started_at"] = t.get("started_at") or _now_ts()
                t["finished_at"] = None
                t["error"] = ""
                t["report"] = None
                _set_task_status(t, "running")
            elif st == "finish_part":
                ok = bool((s or {}).get("ok"))
                rep = (s or {}).get("report")
                if rep is not None:
                    t["report"] = rep
                _set_task_status(t, "success" if ok else "failed")
            elif st == "start_scene":
                _set_task_status(t, t.get("status") if t.get("status") != "queued" else "running")
            elif st == "finish_scene":
                try:
                    if bool((s or {}).get("ok", True)):
                        t["scene_done"] = int(t.get("scene_done") or 0) + 1
                except Exception:
                    pass
            elif st == "start_broll":
                _set_task_status(t, t.get("status") if t.get("status") != "queued" else "running")
            elif st == "finish_broll":
                ok = bool((s or {}).get("ok", True))
                if not ok and not t.get("error"):
                    t["error"] = "broll_failed"
    except Exception:
        pass
    _log.append({"level": "step", "msg": json.dumps(s, ensure_ascii=False)})
    try:
        st = str((s or {}).get("type") or "")
        if st == "finish_part":
            _progress["done_parts"] = int(_progress.get("done_parts") or 0) + 1
        if st == "finish_scene":
            _progress["done_scenes"] = int(_progress.get("done_scenes") or 0) + 1
        total_scenes = int(_progress.get("total_scenes") or 0)
        total_parts = int(_progress.get("total_parts") or 0)
        if total_scenes > 0:
            _progress["done"] = int(_progress.get("done_scenes") or 0)
            _progress["total"] = total_scenes
        else:
            _progress["done"] = int(_progress.get("done_parts") or 0)
            _progress["total"] = total_parts
    except Exception:
        pass

events.on_notice = _on_notice
events.on_progress = _on_progress
events.on_step = _on_step
runner.set_events(events)

async def _run_one(ep: str, part: int) -> bool:
    key = _task_key(ep, part)
    pause_ev = _task_pause.get(key)
    if pause_ev is None:
        pause_ev = asyncio.Event()
        pause_ev.set()
        _task_pause[key] = pause_ev
    tinfo = _ensure_task(ep, part)
    tinfo["scene_done"] = int(tinfo.get("scene_done") or 0)
    async with _sem:
        await _global_pause.wait()
        await pause_ev.wait()
        if events.on_step:
            events.on_step({"type": "start_part", "episode": ep, "part": int(part)})
        try:
            from ui.state import update_project_status
            update_project_status(ep, "running")
        except Exception:
            pass
        auto = HeyGenAutomation(runner.csv_path, runner.config)
        try:
            auto.df = runner.automation.df
        except Exception:
            pass
        try:
            auto.set_hooks(on_notice=events.on_notice, on_step=events.on_step)
        except Exception:
            pass
        try:
            auto.pause_events = [_global_pause, pause_ev]
        except Exception:
            pass
        ok = False
        rep_summary = None
        try:
            ok = await auto.process_episode_part(ep, int(part))
        except asyncio.CancelledError:
            _set_task_status(tinfo, "stopped")
            raise
        except Exception as e:
            _set_task_status(tinfo, "failed")
            tinfo["error"] = str(e)
        if not ok and not str(tinfo.get("error") or ""):
            try:
                last_err = str(getattr(auto, "_last_error", "") or "")
            except Exception:
                last_err = ""
            if last_err:
                tinfo["error"] = last_err
        try:
            rep = getattr(auto, "report", None)
        except Exception:
            rep = None
        if isinstance(rep, dict):
            try:
                rep_summary = {
                    "validation_missing": len(rep.get("validation_missing") or []),
                    "broll_skipped": len(rep.get("broll_skipped") or []),
                    "broll_no_results": len(rep.get("broll_no_results") or []),
                    "broll_errors": len(rep.get("broll_errors") or []),
                    "manual_intervention": len(rep.get("manual_intervention") or []),
                }
            except Exception:
                rep_summary = None
        if events.on_step:
            payload = {"type": "finish_part", "episode": ep, "part": int(part), "ok": bool(ok)}
            if rep_summary is not None:
                payload["report"] = rep_summary
            events.on_step(payload)
        try:
            from ui.state import update_project_status
            update_project_status(ep, "completed" if ok else "failed")
        except Exception:
            pass
        return bool(ok)

def _start_task(ep: str, part: int) -> None:
    key = _task_key(ep, part)
    if key in _active_tasks and not _active_tasks[key].done():
        return
    _ensure_task(ep, part)
    pause_ev = _task_pause.get(key)
    if pause_ev is None:
        pause_ev = asyncio.Event()
        pause_ev.set()
        _task_pause[key] = pause_ev
    async def _go():
        try:
            await _run_one(ep, part)
        except asyncio.CancelledError:
            t = _tasks.get(key)
            if isinstance(t, dict):
                _set_task_status(t, "stopped")
        finally:
            _active_tasks.pop(key, None)
    _active_tasks[key] = asyncio.create_task(_go())

def _plan_tasks_for_episodes(episodes: List[str]) -> Dict[str, Any]:
    planned = []
    total_parts = 0
    total_scenes = 0
    for ep in episodes:
        parts = runner.automation.get_all_episode_parts(ep)
        for p in parts:
            t = _ensure_task(ep, int(p))
            try:
                _, scenes = runner.automation.get_episode_data(ep, int(p))
                t["scene_total"] = int(len(scenes or []))
            except Exception:
                t["scene_total"] = int(t.get("scene_total") or 0)
            planned.append(t["key"])
            total_parts += 1
            total_scenes += int(t.get("scene_total") or 0)
    return {"planned": planned, "total_parts": total_parts, "total_scenes": total_scenes}

@app.get("/workflows")
def api_list_workflows():
    return {"files": list_workflows()}

@app.get("/workflows/{name}")
def api_get_workflow(name: str):
    p = os.path.join(os.getcwd(), "workflows", name)
    wf = load_workflow(p)
    return wf.model_dump()

@app.put("/workflows/{name}/settings")
def api_put_workflow_settings(name: str, payload: Dict[str, Any]):
    p = os.path.join(os.getcwd(), "workflows", name)
    wf = load_workflow(p)
    wf.settings = payload or {}
    save_workflow(wf, p)
    return {"ok": True}

@app.post("/workflows/validate")
def api_validate_workflow(payload: Dict[str, Any]):
    wf = validate_workflow_dict(payload)
    return wf.model_dump()

@app.get("/locators")
def api_get_locators():
    return {"locators": list_locators()}

@app.post("/locators")
def api_post_locator(payload: Dict[str, Any]):
    name = str((payload or {}).get("name") or "").strip()
    selector = str((payload or {}).get("selector") or "").strip()
    if not name or not selector:
        raise HTTPException(status_code=400, detail="name and selector required")
    save_locator(name, selector)
    return {"ok": True, "locators": list_locators()}

@app.delete("/locators/{name}")
def api_delete_locator(name: str):
    nm = str(name or "").strip()
    if not nm:
        raise HTTPException(status_code=400, detail="name required")
    delete_locator(nm)
    return {"ok": True, "locators": list_locators()}

@app.post("/csv/upload")
async def api_csv_upload(file: UploadFile = File(...)):
    os.makedirs("uploads", exist_ok=True)
    path = os.path.join("uploads", file.filename)
    with open(path, "wb") as f:
        f.write(await file.read())
    _set_csv_file(path)
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(runner.config, f, ensure_ascii=False, indent=2)
    await runner.load()
    return {"ok": True, "path": path}

@app.post("/csv/text")
async def api_csv_text(text: str = Form(...)):
    df = pd.read_csv(io.StringIO(text))
    os.makedirs("uploads", exist_ok=True)
    path = os.path.join("uploads", "pasted.csv")
    df.to_csv(path, index=False)
    _set_csv_file(path)
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(runner.config, f, ensure_ascii=False, indent=2)
    await runner.load()
    return {"ok": True, "path": path}

@app.get("/csv/stats")
def api_csv_stats():
    return runner.csv_stats()

@app.get("/progress")
def api_progress():
    return _progress

@app.get("/logs")
def api_logs(limit: int = 2000):
    return _log[-limit:]

@app.post("/run")
async def api_run(workflow: Optional[str] = Form(None)):
    global _log
    _log = []
    try:
        _apply_workflow_settings(workflow)
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(runner.config, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    runner.cancel = False
    global _progress
    _progress = {"done": 0, "total": 0, "done_parts": 0, "total_parts": 0, "done_scenes": 0, "total_scenes": 0}
    await runner.load()
    eps = runner.episodes
    try:
        plan = _plan_tasks_for_episodes([str(e) for e in eps])
        _progress["total_parts"] = int(plan.get("total_parts") or 0)
        _progress["total_scenes"] = int(plan.get("total_scenes") or 0)
        _progress["done_parts"] = 0
        _progress["done_scenes"] = 0
        if int(_progress.get("total_scenes") or 0) > 0:
            _progress["total"] = int(_progress.get("total_scenes") or 0)
        else:
            _progress["total"] = int(_progress.get("total_parts") or 0)
        _progress["done"] = 0
    except Exception:
        pass
    for ep in eps:
        parts = runner.automation.get_all_episode_parts(ep)
        for p in parts:
            _start_task(str(ep), int(p))
    return {"ok": True, "total": len(eps)}

@app.post("/run/projects")
async def api_run_projects(payload: Dict[str, Any]):
    global _log
    _log = []
    workflow = payload.get("workflow")
    episodes = payload.get("episodes") or []
    episodes = [str(e) for e in episodes if e]
    if not episodes:
        raise HTTPException(status_code=400, detail="episodes required")
    try:
        _apply_workflow_settings(workflow)
    except Exception:
        pass
    csv_path = _write_projects_csv(episodes)
    _set_csv_file(csv_path)
    runner.config["episodes_to_process"] = episodes
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(runner.config, f, ensure_ascii=False, indent=2)
    runner.cancel = False
    global _progress
    _progress = {"done": 0, "total": 0, "done_parts": 0, "total_parts": 0, "done_scenes": 0, "total_scenes": 0}
    await runner.load()
    try:
        plan = _plan_tasks_for_episodes(episodes)
        _progress["total_parts"] = int(plan.get("total_parts") or 0)
        _progress["total_scenes"] = int(plan.get("total_scenes") or 0)
        _progress["done_parts"] = 0
        _progress["done_scenes"] = 0
        if int(_progress.get("total_scenes") or 0) > 0:
            _progress["total"] = int(_progress.get("total_scenes") or 0)
        else:
            _progress["total"] = int(_progress.get("total_parts") or 0)
        _progress["done"] = 0
    except Exception:
        pass
    for ep in episodes:
        parts = runner.automation.get_all_episode_parts(ep)
        for p in parts:
            _start_task(str(ep), int(p))
    return {"ok": True, "total": len(episodes)}

@app.post("/stop")
def api_stop():
    global _progress
    global _log
    runner.stop()
    try:
        _progress = {"done": 0, "total": 0, "done_parts": 0, "total_parts": 0, "done_scenes": 0, "total_scenes": 0}
    except Exception:
        pass
    try:
        _global_pause.set()
    except Exception:
        pass
    try:
        for t in list(_active_tasks.values()):
            if t is not None and not t.done():
                t.cancel()
    except Exception:
        pass
    try:
        for ev in list(_task_pause.values()):
            if ev is not None:
                ev.set()
    except Exception:
        pass
    try:
        for k, t in list(_tasks.items()):
            if not isinstance(t, dict):
                continue
            if str(t.get("status")) == "running" or str(t.get("status")) == "paused":
                _set_task_status(t, "stopped")
    except Exception:
        pass
    try:
        _log.append({"level": "info", "msg": "stopped"})
    except Exception:
        _log = [{"level": "info", "msg": "stopped"}]
    try:
        from ui.state import get_projects, save_projects
        items = get_projects()
        changed = False
        for pr in items:
            if isinstance(pr, dict) and str(pr.get("status")) == "running":
                pr["status"] = "pending"
                changed = True
        if changed:
            save_projects(items)
    except Exception:
        pass
    return {"ok": True}

@app.post("/pause")
def api_pause():
    try:
        _global_pause.clear()
        for t in _tasks.values():
            if isinstance(t, dict) and str(t.get("status")) == "running":
                _set_task_status(t, "paused")
    except Exception:
        pass
    _log.append({"level": "info", "msg": "paused"})
    return {"ok": True}

@app.post("/resume")
def api_resume():
    try:
        _global_pause.set()
        for t in _tasks.values():
            if isinstance(t, dict) and str(t.get("status")) == "paused":
                _set_task_status(t, "running")
    except Exception:
        pass
    _log.append({"level": "info", "msg": "resumed"})
    return {"ok": True}

@app.get("/tasks")
def api_tasks(episode: Optional[str] = Query(None)):
    items = list(_tasks.values())
    if episode:
        items = [t for t in items if isinstance(t, dict) and str(t.get("episode")) == str(episode)]
    out = []
    for t in items:
        if not isinstance(t, dict):
            continue
        k = str(t.get("key") or "")
        status = str(t.get("status") or "queued")
        if status == "running":
            ev = _task_pause.get(k)
            if ev is not None and not ev.is_set():
                status = "paused"
        out.append({**t, "status": status})
    prio = {"running": 0, "paused": 1, "queued": 2, "stopped": 3, "failed": 4, "success": 5}
    out.sort(key=lambda x: (prio.get(str(x.get("status")), 99), str(x.get("episode")), int(x.get("part") or 0)))
    return {"tasks": out}

@app.post("/tasks/{episode}/{part}/pause")
def api_task_pause(episode: str, part: int):
    k = _task_key(episode, part)
    ev = _task_pause.get(k)
    if ev is None:
        ev = asyncio.Event()
        ev.set()
        _task_pause[k] = ev
    ev.clear()
    t = _ensure_task(episode, int(part))
    _set_task_status(t, "paused")
    return {"ok": True}

@app.post("/tasks/{episode}/{part}/resume")
def api_task_resume(episode: str, part: int):
    k = _task_key(episode, part)
    ev = _task_pause.get(k)
    if ev is None:
        ev = asyncio.Event()
        _task_pause[k] = ev
    ev.set()
    t = _ensure_task(episode, int(part))
    if str(t.get("status")) == "paused":
        _set_task_status(t, "running")
    return {"ok": True}

@app.post("/tasks/{episode}/{part}/stop")
def api_task_stop(episode: str, part: int):
    k = _task_key(episode, part)
    task = _active_tasks.get(k)
    if task is not None and not task.done():
        try:
            task.cancel()
        except Exception:
            pass
    try:
        ev = _task_pause.get(k)
        if ev is not None:
            ev.set()
    except Exception:
        pass
    t = _ensure_task(episode, int(part))
    _set_task_status(t, "stopped")
    return {"ok": True}

@app.post("/tasks/{episode}/{part}/start")
def api_task_start(episode: str, part: int):
    try:
        try:
            _global_pause.set()
        except Exception:
            pass
        try:
            k = _task_key(str(episode), int(part))
            ev = _task_pause.get(k)
            if ev is not None:
                ev.set()
        except Exception:
            pass
        _start_task(str(episode), int(part))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True}

@app.get("/config")
def api_get_config():
    return runner.config

@app.put("/config")
def api_put_config(payload: Dict[str, Any]):
    cfg = runner.config
    for k, v in (payload or {}).items():
        cfg[k] = v
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    runner.config = cfg
    return {"ok": True}

@app.get("/episodes")
def api_get_episodes():
    return {"episodes": runner.episodes}

@app.post("/episodes/select")
def api_select_episodes(payload: Dict[str, Any]):
    eps = payload.get("episodes") or []
    runner.config["episodes_to_process"] = eps
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(runner.config, f, ensure_ascii=False, indent=2)
    return {"ok": True, "episodes": eps}

@app.post("/episodes/override")
def api_override_episode(episode_id: str = Form(...), title: Optional[str] = Form(None), template_url: Optional[str] = Form(None)):
    runner.apply_episode_overrides(episode_id, title, template_url)
    return {"ok": True}

@app.get("/episodes/recent")
def api_recent_episodes():
    return {"recent": get_recent_episodes()}

@app.get("/episodes/stats/{episode_id}")
def api_episode_stats(episode_id: str):
    df = runner.automation.df
    try:
        if 'episode_id' in df.columns:
            rows = df[df['episode_id'] == episode_id]
        elif 'episode' in df.columns:
            rows = df[df['episode'] == episode_id]
        else:
            rows = df
        part_col = 'part_idx' if 'part_idx' in rows.columns else ('part' if 'part' in rows.columns else None)
        scene_col = 'scene_idx' if 'scene_idx' in rows.columns else ('scene' if 'scene' in rows.columns else ('scene_number' if 'scene_number' in rows.columns else None))
        parts = []
        if part_col:
            parts = sorted(list({int(p) for p in pd.to_numeric(rows[part_col], errors='coerce').dropna().tolist()}))
        scenes = 0
        if scene_col:
            scenes = len(rows[scene_col].dropna().tolist())
        tmpl = None
        if 'template_url' in rows.columns and len(rows) > 0:
            tmpl = str(rows.iloc[0]['template_url'])
        return {"episode_id": episode_id, "parts": parts, "scenes": scenes, "template_url": tmpl}
    except Exception:
        return {"episode_id": episode_id, "parts": [], "scenes": 0, "template_url": None}

@app.get("/projects")
def api_get_projects(status: Optional[str] = None, include_data: bool = False):
    items = get_projects()
    if status:
        items = [p for p in items if str(p.get("status")) == str(status)]
    projects = []
    for p in items:
        if not isinstance(p, dict):
            continue
        projects.append({**_project_public(p, include_data), "stats": _project_stats(p)})
    return {"projects": projects}

@app.get("/projects/{episode_id}")
def api_get_project(episode_id: str, include_data: bool = True):
    items = get_projects()
    pr = _find_project(items, episode_id)
    if not pr:
        raise HTTPException(status_code=404, detail="project not found")
    return _project_response(pr, include_data)

@app.post("/projects/add")
def api_add_projects(payload: Dict[str, Any]):
    eps = payload.get("episodes") or []
    rows = payload.get("rows") or []
    if isinstance(rows, list) and len(rows) > 0:
        items = add_projects_with_records(rows, eps)
        return {"ok": True, "projects": [{**_project_public(p, False), "stats": _project_stats(p)} for p in items if isinstance(p, dict)]}
    try:
        df = runner.automation.df
    except Exception:
        df = None
    if df is not None:
        items = add_projects_with_data(df, [e for e in eps if e])
    else:
        items = add_projects([e for e in eps if e])
    return {"ok": True, "projects": [{**_project_public(p, False), "stats": _project_stats(p)} for p in items if isinstance(p, dict)]}

@app.put("/projects/{episode_id}")
def api_put_project(episode_id: str, payload: Dict[str, Any]):
    items = get_projects()
    pr = _find_project(items, episode_id)
    if not pr:
        raise HTTPException(status_code=404, detail="project not found")
    if "status" in payload:
        pr["status"] = payload.get("status")
    if "data" in payload:
        pr["data"] = payload.get("data") or []
    save_projects(items)
    return {"ok": True, "project": _project_public(pr, False), "stats": _project_stats(pr)}

@app.delete("/projects/{episode_id}")
def api_delete_project(episode_id: str):
    items = get_projects()
    kept: List[Dict[str, Any]] = []
    removed = False
    for pr in items:
        if isinstance(pr, dict) and str(pr.get("episode")) == str(episode_id):
            removed = True
            continue
        if isinstance(pr, dict):
            kept.append(pr)
    if not removed:
        raise HTTPException(status_code=404, detail="project not found")
    save_projects(kept)
    return {"ok": True}

@app.post("/projects/update")
def api_update_projects(payload: Dict[str, Any]):
    items = payload.get("projects") or []
    save_projects(items)
    return {"ok": True}
@app.put("/workflows/{name}")
def api_put_workflow(name: str, payload: Dict[str, Any]):
    p = os.path.join(os.getcwd(), "workflows", name)
    wf = Workflow(**payload)
    save_workflow(wf, p)
    return {"ok": True}
