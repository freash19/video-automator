import asyncio
import os
import json
import time
import subprocess
import sys
from urllib.parse import urlparse
from html import escape as _html_escape
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
from ui.logger import logger
from ui.notify import send_telegram, send_telegram_many, fetch_telegram_chat_ids
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
_automation_refs: Dict[str, HeyGenAutomation] = {}
_task_status: Dict[str, Dict[str, Any]] = {}
_task_scene_done: Dict[str, set] = {}
_global_scene_done: set = set()

def _now_ts() -> int:
    try:
        return int(time.time())
    except Exception:
        return 0

def _browser_launch_command(cfg: Dict[str, Any]) -> List[str]:
    chrome_path = str(cfg.get("chrome_binary") or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    profile_path = str(cfg.get("chrome_profile_path") or "")
    cdp_url = str(cfg.get("chrome_cdp_url") or "")
    profiles = cfg.get("profiles") or {}
    profile_to_use = str(cfg.get("profile_to_use") or "").strip()
    if not profile_to_use or profile_to_use.lower() == "ask":
        if "chrome_automation" in profiles:
            profile_to_use = "chrome_automation"
        elif profiles:
            profile_to_use = list(profiles.keys())[0]
    prof = profiles.get(profile_to_use) if profile_to_use else None
    if isinstance(prof, dict):
        if prof.get("profile_path"):
            profile_path = str(prof.get("profile_path"))
        if prof.get("cdp_url"):
            cdp_url = str(prof.get("cdp_url"))
    if not profile_path:
        profile_path = "~/chrome_automation"
    port = 9222
    if cdp_url:
        try:
            parsed = urlparse(cdp_url)
            if parsed.port:
                port = int(parsed.port)
        except Exception:
            pass
    profile_path = os.path.expanduser(profile_path)
    return [
        chrome_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_path}",
        "https://app.heygen.com/projects",
    ]

def _is_browser_closed_error(msg: str) -> bool:
    text = str(msg or "")
    return "Target page, context or browser has been closed" in text or "has been closed" in text or "closed by user" in text

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

def _compact_report_entries(items: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for it in items or []:
        if isinstance(it, dict):
            cur = {}
            for k in ("scene_idx", "query", "error", "reason", "kind", "prompt", "attempt", "screenshot"):
                if it.get(k) is not None:
                    cur[k] = it.get(k)
            if cur:
                out.append(cur)
        else:
            out.append({"value": it})
    return out

def _telegram_config() -> tuple[str, str, bool]:
    token = str(runner.config.get("telegram_bot_token") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = str(runner.config.get("telegram_chat_id") or os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    broadcast_all = bool(runner.config.get("telegram_broadcast_all", False))
    return token, chat_id, broadcast_all

def _telegram_chats_path() -> str:
    return os.path.join("state", "telegram_chats.json")

def _load_telegram_chats() -> List[str]:
    path = _telegram_chats_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [str(x) for x in data if str(x).strip()]
    except Exception:
        return []
    return []

def _save_telegram_chats(chat_ids: List[str]) -> None:
    try:
        os.makedirs("state", exist_ok=True)
        with open(_telegram_chats_path(), "w", encoding="utf-8") as f:
            json.dump(sorted({str(c) for c in chat_ids if str(c).strip()}), f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _get_broadcast_chat_ids(token: str, fallback_chat_id: str) -> List[str]:
    cfg_list = runner.config.get("telegram_chat_ids")
    if isinstance(cfg_list, list):
        ids = [str(x) for x in cfg_list if str(x).strip()]
    else:
        ids = []
    cached = _load_telegram_chats()
    ids.extend(cached)
    if fallback_chat_id:
        ids.append(fallback_chat_id)
    ids = sorted({c for c in ids if c})
    if ids:
        return ids
    fetched = fetch_telegram_chat_ids(token)
    if fetched:
        _save_telegram_chats(fetched)
    return fetched

def _format_task_report_line(report: Dict[str, Any]) -> str:
    if not isinstance(report, dict):
        return ""
    labels = {
        "validation_missing": "несоответствия",
        "broll_skipped": "b-roll пропущен",
        "broll_no_results": "b-roll без результатов",
        "broll_errors": "ошибки b-roll",
        "manual_intervention": "вмешательство",
        "nano_banano_errors": "ошибки Nano Banana",
    }
    parts = []
    for k, label in labels.items():
        try:
            v = int(report.get(k) or 0)
        except Exception:
            v = 0
        if v > 0:
            parts.append(f"{label}: {v}")
    return ", ".join(parts)

def _format_scene_errors(details: Optional[Dict[str, List[Dict[str, Any]]]]) -> str:
    if not isinstance(details, dict):
        return ""
    scenes = set()
    for key in ("validation_missing", "broll_errors", "broll_no_results", "broll_skipped", "nano_banano_errors", "manual_intervention"):
        items = details.get(key) or []
        for it in items:
            if isinstance(it, dict) and it.get("scene_idx") is not None:
                scenes.add(str(it.get("scene_idx")))
    if not scenes:
        return ""
    ordered = sorted(scenes, key=lambda x: int(x) if str(x).isdigit() else x)
    return ", ".join(ordered)

def _tg_escape(v: Any) -> str:
    try:
        return _html_escape(str(v or ""), quote=True)
    except Exception:
        return ""

def _scene_idx_from_item(it: Any) -> Optional[int]:
    if not isinstance(it, dict):
        return None
    v = it.get("scene_idx")
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None

def _classify_broll_error(it: Dict[str, Any]) -> str:
    kind = str(it.get("kind") or "").strip()
    reason = str(it.get("reason") or "").strip()
    err = str(it.get("error") or "").strip()

    r = reason.lower()
    e = err.lower()

    if kind in ("validation_failed", "nano_validation_failed"):
        if "set_as_bg" in r or "needs_set_bg" in r or "still_visible" in r:
            return "бирол не установлен на фон"
        if "bg_color_visible_after_insert" in r or "empty_canvas" in r:
            return "не вставлен бирол"
        if kind == "nano_validation_failed":
            return "Nano Banana: валидация не прошла"
        return "валидация B-roll не прошла"

    if "панель" in e or "media" in e or "вкладка" in e or "video" in e:
        return "не вставлен бирол"

    return "ошибка b-roll"

def _compute_scene_health(t: Dict[str, Any]) -> Dict[str, Any]:
    details = t.get("report_details") if isinstance(t, dict) else None
    if not isinstance(details, dict):
        details = {}

    errors_by_scene: Dict[int, List[str]] = {}

    def add(scene_idx: int, label: str) -> None:
        if scene_idx is None:
            return
        if scene_idx not in errors_by_scene:
            errors_by_scene[scene_idx] = []
        if label and label not in errors_by_scene[scene_idx]:
            errors_by_scene[scene_idx].append(label)

    for it in (details.get("validation_missing") or []):
        idx = _scene_idx_from_item(it)
        if idx is not None:
            add(idx, "не заполнен текст сцены")

    for it in (details.get("broll_no_results") or []):
        idx = _scene_idx_from_item(it)
        if idx is not None:
            add(idx, "не вставлен бирол (нет результатов)")

    for it in (details.get("nano_banano_errors") or []):
        idx = _scene_idx_from_item(it)
        if idx is not None:
            add(idx, "нано банано не сгенерировало изображение")

    for it in (details.get("broll_errors") or []):
        idx = _scene_idx_from_item(it)
        if idx is None:
            continue
        label = _classify_broll_error(it if isinstance(it, dict) else {})
        add(idx, label)

    total = 0
    try:
        total = int(t.get("scene_total") or 0)
    except Exception:
        total = 0
    bad = sorted(errors_by_scene.keys())
    ok = 0
    if total > 0:
        ok = max(total - len(bad), 0)
    ratio = (ok / total) if total > 0 else 0.0
    return {"scene_total": total, "scene_ok": ok, "ratio": ratio, "errors_by_scene": errors_by_scene}

def _send_task_telegram(t: Dict[str, Any], report: Optional[Dict[str, Any]] = None) -> None:
    token, chat_id, broadcast_all = _telegram_config()
    if not token or (not chat_id and not broadcast_all):
        return
    try:
        status = str(t.get("status") or "")
        episode = str(t.get("episode") or "")
        part = str(t.get("part") or "")
        health = _compute_scene_health(t)
        scene_total = int(health.get("scene_total") or 0)
        scene_ok = int(health.get("scene_ok") or 0)
        ratio = float(health.get("ratio") or 0.0)
        scenes = f"{scene_ok}/{scene_total}"
        project_url = str(t.get("template_url") or "").strip()
        project_status = str(t.get("project_status") or "").strip()
        speakers = t.get("speakers") if isinstance(t.get("speakers"), list) else []
        speakers_text = ", ".join([str(s) for s in speakers if str(s).strip()])

        st = status.lower()
        has_scene_errors = bool(health.get("errors_by_scene"))
        early_fail = st in ("failed", "stopped") and (scene_total == 0 or scene_ok == 0)
        if early_fail:
            emoji = "❌"
        elif scene_total > 0 and ratio < 0.8:
            emoji = "❌"
        elif has_scene_errors:
            emoji = "⚠️"
        elif st == "success":
            emoji = "✅"
        else:
            emoji = "⚠️"

        lines = [
            f"Название эпизода: <b>{_tg_escape(episode)}</b>",
            f"Часть: {_tg_escape(part)}",
            f"Статус: {emoji} {_tg_escape(status)}",
            f"Сцены: {_tg_escape(scenes)}",
        ]
        if project_status:
            lines.append(f"Проект: {_tg_escape(project_status)}")
        if project_url:
            lines.append(f"Ссылка: {_tg_escape(project_url)}")
        if speakers_text:
            lines.append(f"Спикеры: {_tg_escape(speakers_text)}")
        err = str(t.get("error") or "").strip()
        if err:
            lines.append(f"Ошибка: {_tg_escape(err)}")

        if has_scene_errors:
            lines.append("Ошибки:")
            errors_by_scene = health.get("errors_by_scene") or {}
            ordered = sorted([k for k in errors_by_scene.keys() if isinstance(k, int)])
            for scene_idx in ordered:
                reasons = errors_by_scene.get(scene_idx) or []
                reasons_text = "; ".join([str(x) for x in reasons if str(x).strip()])
                if reasons_text:
                    lines.append(f"• Сцена {scene_idx}: {_tg_escape(reasons_text)}")
        rep_line = _format_task_report_line(report or {})
        if rep_line:
            lines.append(f"Отчёт: {_tg_escape(rep_line)}")
        text = "\n".join([l for l in lines if l])
        ok = False
        if broadcast_all:
            chat_ids = _get_broadcast_chat_ids(token, chat_id)
            ok = send_telegram_many(token, chat_ids, text) if chat_ids else False
        else:
            ok = send_telegram(token, chat_id, text)
        if ok:
            _log.append({"level": "info", "msg": "telegram_sent"})
            logger.info("[telegram] sent")
        else:
            _log.append({"level": "warn", "msg": "telegram_failed"})
            logger.warning("[telegram] failed")
    except Exception as e:
        try:
            _log.append({"level": "error", "msg": f"telegram_error: {e}"})
        except Exception:
            pass
        try:
            logger.error(f"[telegram] error: {e}")
        except Exception:
            pass

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
    if msg == "browser_closed_event":
        asyncio.create_task(_stop_all_tasks("browser_closed_event"))

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
            k = _task_key(str(ep), int(part))
            t = _ensure_task(str(ep), int(part))
            t["stage"] = st
            # Реалтайм TaskStatus: обновляем снапшот из живой автоматики
            try:
                auto = _automation_refs.get(k)
                if auto is not None and getattr(auto, "task_status", None) is not None:
                    _task_status[k] = auto.task_status.model_dump()
            except Exception:
                pass
            if st == "start_part":
                t["started_at"] = t.get("started_at") or _now_ts()
                t["finished_at"] = None
                t["error"] = ""
                t["report"] = None
                try:
                    old = _task_scene_done.get(k) or set()
                    for scene_idx in old:
                        _global_scene_done.discard(f"{k}:{int(scene_idx)}")
                except Exception:
                    pass
                _task_scene_done[k] = set()
                t["scene_done"] = 0
                _set_task_status(t, "running")
            elif st == "finish_part":
                ok = bool((s or {}).get("ok"))
                rep = (s or {}).get("report")
                if rep is not None:
                    t["report"] = rep
                _set_task_status(t, "success" if ok else "failed")
                # Отправляем уведомление только если заполнена хотя бы одна сцена
                scene_done = int(t.get('scene_done') or 0)
                if scene_done > 0:
                    _send_task_telegram(t, rep if isinstance(rep, dict) else t.get("report"))
            elif st == "start_scene":
                _set_task_status(t, t.get("status") if t.get("status") != "queued" else "running")
            elif st == "finish_scene":
                try:
                    if bool((s or {}).get("ok", True)):
                        raw_scene = (s or {}).get("scene")
                        try:
                            scene_idx = int(raw_scene)
                        except Exception:
                            scene_idx = None
                        if scene_idx is not None:
                            seen = _task_scene_done.get(k)
                            if not isinstance(seen, set):
                                seen = set()
                                _task_scene_done[k] = seen
                            if scene_idx not in seen:
                                seen.add(scene_idx)
                                t["scene_done"] = len(seen)
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
            ep = (s or {}).get("episode")
            part = (s or {}).get("part")
            raw_scene = (s or {}).get("scene")
            if ep is not None and part is not None and raw_scene is not None:
                try:
                    k = _task_key(str(ep), int(part))
                    scene_idx = int(raw_scene)
                    gk = f"{k}:{scene_idx}"
                    if gk not in _global_scene_done and bool((s or {}).get("ok", True)):
                        _global_scene_done.add(gk)
                        _progress["done_scenes"] = int(_progress.get("done_scenes") or 0) + 1
                except Exception:
                    pass
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
            
        if not await runner.automation.open_browser():
            _set_task_status(tinfo, "failed")
            tinfo["error"] = "Could not open browser"
            return False

        auto = HeyGenAutomation(runner.csv_path, runner.config, browser=runner.automation.browser, playwright=runner.automation.playwright)
        try:
            auto.df = runner.automation.df
        except Exception:
            pass
        try:
            auto.set_hooks(on_notice=events.on_notice, on_step=events.on_step)
        except Exception:
            pass
        try:
            template_url, scenes = auto.get_episode_data(ep, int(part))
            tinfo["template_url"] = str(template_url or "").strip()
            speakers = []
            for s in scenes or []:
                sp = s.get("speaker")
                if sp:
                    speakers.append(str(sp).strip())
            if speakers:
                tinfo["speakers"] = sorted({s for s in speakers if s})
        except Exception:
            pass
        try:
            auto.pause_events = [_global_pause, pause_ev]
        except Exception:
            pass
        _automation_refs[key] = auto
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
            if _is_browser_closed_error(str(e)):
                await _stop_all_tasks("browser_closed")
        if not ok and not str(tinfo.get("error") or ""):
            try:
                last_err = str(getattr(auto, "_last_error", "") or "")
            except Exception:
                last_err = ""
            if last_err:
                tinfo["error"] = last_err
        try:
            tinfo["project_status"] = "На генерации" if bool(getattr(auto, "_generation_enabled", lambda: False)()) else "Черновик"
        except Exception:
            pass
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
                    "nano_banano_errors": len(rep.get("nano_banano_errors") or []),
                }
            except Exception:
                rep_summary = None
            try:
                tinfo["report_details"] = {
                    "validation_missing": _compact_report_entries(rep.get("validation_missing")),
                    "broll_skipped": _compact_report_entries(rep.get("broll_skipped")),
                    "broll_no_results": _compact_report_entries(rep.get("broll_no_results")),
                    "broll_errors": _compact_report_entries(rep.get("broll_errors")),
                    "manual_intervention": _compact_report_entries(rep.get("manual_intervention")),
                    "nano_banano_errors": _compact_report_entries(rep.get("nano_banano_errors")),
                }
            except Exception:
                pass
        try:
            ts = getattr(auto, "task_status", None)
            if ts is not None:
                _task_status[key] = ts.model_dump()
        except Exception:
            pass
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

async def _stop_all_tasks(reason: str) -> None:
    global _progress
    global _log
    global _task_scene_done
    global _global_scene_done
    runner.stop()
    # Close browser on stop
    try:
        if runner.automation:
            await runner.automation.close_browser()
    except Exception:
        pass

    try:
        _progress = {"done": 0, "total": 0, "done_parts": 0, "total_parts": 0, "done_scenes": 0, "total_scenes": 0}
    except Exception:
        pass
    try:
        _task_scene_done = {}
        _global_scene_done = set()
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
            if str(t.get("status")) in ("running", "paused", "queued"):
                _set_task_status(t, "stopped")
    except Exception:
        pass
    try:
        _log.append({"level": "info", "msg": reason})
    except Exception:
        _log = [{"level": "info", "msg": reason}]
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
    try:
        runner.automation.load_data()
    except Exception as e:
        try:
            _log.append({"level": "error", "msg": f"csv_upload_failed: {e}"})
        except Exception:
            pass
        try:
            logger.error(f"[csv_upload] failed: {e}")
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e))
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
    try:
        runner.automation.load_data()
    except Exception as e:
        try:
            _log.append({"level": "error", "msg": f"csv_text_failed: {e}"})
        except Exception:
            pass
        try:
            logger.error(f"[csv_text] failed: {e}")
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e))
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

@app.post("/telegram/sync")
def api_telegram_sync():
    token, chat_id, broadcast_all = _telegram_config()
    if not token:
        raise HTTPException(status_code=400, detail="telegram_bot_token missing")
    chats = _get_broadcast_chat_ids(token, chat_id)
    if not chats:
        raise HTTPException(status_code=404, detail="no chats found")
    _save_telegram_chats(chats)
    return {"ok": True, "count": len(chats), "chats": chats}

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
async def api_stop():
    await _stop_all_tasks("stopped")
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

@app.post("/run-workflow")
async def api_run_workflow(payload: Dict[str, Any]):
    episode = str((payload or {}).get("episode") or "").strip()
    part = (payload or {}).get("part")
    workflow = (payload or {}).get("workflow")
    if not episode or part is None:
        raise HTTPException(status_code=400, detail="episode and part required")
    runner.cancel = False
    try:
        _global_pause.set()
    except Exception:
        pass
    try:
        _apply_workflow_settings(str(workflow or "") or None)
    except Exception:
        pass
    try:
        await runner.load()
    except Exception:
        pass
    _start_task(episode, int(part))
    return {"id": _task_key(episode, int(part))}

@app.get("/task/{tid}/status")
def api_task_status(tid: str):
    k = str(tid or "")
    if k in _task_status:
        return _task_status[k]
    t = _tasks.get(k)
    if isinstance(t, dict):
        # Fallback minimal status
        return {
            "task_id": k,
            "steps": [],
            "metrics": {
                "scenes_total": int(t.get("scene_total") or 0),
                "scenes_completed": int(t.get("scene_done") or 0),
                "brolls_total": 0,
                "brolls_inserted": 0,
            },
            "global_status": str(t.get("status") or "queued"),
        }
    raise HTTPException(status_code=404, detail="task not found")

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

@app.post("/browser/open")
async def api_open_browser(payload: Dict[str, Any] = None):
    try:
        cfg = runner.config
        
        # Если передан профиль, обновляем конфиг
        if payload and "profile" in payload:
            profile_name = str(payload["profile"]).strip()
            if profile_name:
                cfg["profile_to_use"] = profile_name
                # Сохраняем выбор в файл
                try:
                    with open("config.json", "w", encoding="utf-8") as f:
                        json.dump(cfg, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass

        profile_to_use = cfg.get('profile_to_use', '')
        profiles = cfg.get('profiles', {})
        profile = profiles.get(profile_to_use, {}) if profile_to_use else {}
        
        ok = await runner.automation.open_browser()
        if not ok:
            profile_info = ""
            if profile_to_use:
                browser_type = profile.get('browser_type', 'chrome' if profile.get('cdp_url') else 'chromium')
                cdp_url = profile.get('cdp_url', '')
                if browser_type == 'chrome' and cdp_url:
                    profile_info = f" Профиль: {profile_to_use}, CDP: {cdp_url}. Убедитесь, что Chrome запущен с remote debugging на этом порту."
                else:
                    profile_info = f" Профиль: {profile_to_use} (Chromium)."
            raise RuntimeError(f"Не удалось открыть браузер.{profile_info}")
        try:
            _log.append({"level": "info", "msg": "browser_opened"})
        except Exception:
            pass
        try:
            logger.info("[open_browser] success")
        except Exception:
            pass
        return {"ok": True}
    except RuntimeError:
        raise
    except Exception as e:
        try:
            _log.append({"level": "error", "msg": f"browser_open_failed: {e}"})
        except Exception:
            pass
        try:
            logger.error(f"[open_browser] failed: {e}")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Ошибка открытия браузера: {str(e)}")

@app.post("/inspector/start")
def api_start_inspector(payload: Dict[str, Any]):
    try:
        url = str((payload or {}).get("url") or "").strip()
        target = str((payload or {}).get("target") or "").strip()
        headless = bool((payload or {}).get("headless", False))
        if not url:
            url = "https://app.heygen.com/projects"
        cmd = [sys.executable, "tools/inspector.py", url]
        if target:
            cmd.extend(["--target", target])
        if headless:
            cmd.append("--headless")
        env = os.environ.copy()
        env.setdefault("PWDEBUG", "1")
        subprocess.Popen(cmd, env=env)
        try:
            _log.append({"level": "info", "msg": f"inspector_started: {url}"})
        except Exception:
            pass
        try:
            logger.info(f"[inspector_start] success: {url}")
        except Exception:
            pass
        return {"ok": True}
    except Exception as e:
        try:
            _log.append({"level": "error", "msg": f"inspector_failed: {e}"})
        except Exception:
            pass
        try:
            logger.error(f"[inspector_start] failed: {e}")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/config")
def api_get_config():
    return runner.config

@app.put("/config")
async def api_put_config(payload: Dict[str, Any]):
    cfg = runner.config
    old_csv = cfg.get("csv_file")
    for k, v in (payload or {}).items():
        cfg[k] = v
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    runner.config = cfg
    # Reload CSV if csv_file was changed
    new_csv = cfg.get("csv_file")
    if new_csv and new_csv != old_csv:
        runner.csv_path = new_csv
        runner.automation.csv_path = new_csv
        await runner.load()
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


# ======================= VIDEO ENDPOINTS =======================
from ui.state import (
    get_videos, save_videos, get_video_list, add_video, 
    update_video, delete_video as state_delete_video, 
    bulk_add_videos, set_last_scraped, _now_iso
)
from ui.postprocess import ffmpeg_concat_advanced, get_video_info, format_file_size, format_duration


@app.get("/videos")
def api_get_videos():
    """Get all videos from state"""
    data = get_videos()
    return data


@app.post("/videos/scrape")
async def api_scrape_videos(payload: Dict[str, Any] = None):
    """Scrape videos from HeyGen projects page"""
    max_count = (payload or {}).get("max_count", 30)
    
    try:
        # Check if we can connect to browser
        from ui.video_scraper import scrape_heygen_videos
        
        _log.append({"level": "info", "msg": f"Starting video scrape, max_count={max_count}"})
        logger.info(f"[scrape_videos] Starting, max_count={max_count}")
        
        # Get already scraped titles to skip
        existing = get_video_list()
        already_scraped = {v.get("title") for v in existing if v.get("title")}
        _log.append({"level": "info", "msg": f"Already have {len(already_scraped)} videos in database"})
        
        # Use existing automation page if available
        auto = runner.automation
        # HeyGenAutomation uses _page attribute
        current_page = getattr(auto, '_page', None)
        
        # Check if page is still valid (not closed)
        page_valid = False
        if current_page is not None:
            try:
                # Try to check if page is still open
                if not current_page.is_closed():
                    page_valid = True
            except Exception:
                pass
        
        if not page_valid:
            _log.append({"level": "info", "msg": "Opening browser..."})
            logger.info("[scrape_videos] Opening browser...")
            # Reset page reference
            auto._page = None
            # Try to open browser
            ok = await auto.open_browser()
            if not ok:
                _log.append({"level": "error", "msg": "Could not connect to browser"})
                raise HTTPException(status_code=500, detail="Could not connect to browser. Make sure Chrome is running with remote debugging enabled.")
            current_page = getattr(auto, '_page', None)
            if current_page is None:
                raise HTTPException(status_code=500, detail="Browser opened but page not available")
        
        page = current_page
        _log.append({"level": "info", "msg": "Browser connected, starting scrape..."})
        logger.info("[scrape_videos] Browser connected, starting scrape...")
        
        # Scrape videos
        videos = await scrape_heygen_videos(page, max_count=max_count, already_scraped_titles=already_scraped)
        
        _log.append({"level": "info", "msg": f"Scrape complete, found {len(videos)} new videos"})
        
        # Save to state
        added = bulk_add_videos(videos)
        
        _log.append({"level": "info", "msg": f"Saved {len(added)} videos to database"})
        logger.info(f"[scrape_videos] scraped {len(added)} videos")
        
        return {"ok": True, "count": len(added), "videos": added}
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        _log.append({"level": "error", "msg": f"scrape_videos_failed: {e}"})
        _log.append({"level": "error", "msg": error_details})
        logger.error(f"[scrape_videos] failed: {e}")
        logger.error(error_details)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/videos/{video_id}/download")
async def api_download_video(video_id: str):
    """Download a single video by ID"""
    try:
        videos = get_video_list()
        video = None
        for v in videos:
            if v.get("id") == video_id:
                video = v
                break
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Get download directory from config
        download_dir = str(runner.config.get("download_dir") or "./downloads")
        os.makedirs(download_dir, exist_ok=True)
        
        file_path = None
        
        # If we have a direct download URL, use it
        if video.get("download_url"):
            from ui.video_scraper import download_video_by_url
            filename = f"{video.get('title', 'video')}_{video_id[:8]}.mp4"
            file_path = await download_video_by_url(
                video["download_url"], 
                download_dir, 
                filename
            )
        else:
            # Otherwise, navigate to the video and download via browser
            from ui.video_scraper import download_single_video
            
            auto = runner.automation
            current_page = getattr(auto, '_page', None)
            
            # Check if page is still valid (not closed)
            page_valid = False
            if current_page is not None:
                try:
                    if not current_page.is_closed():
                        page_valid = True
                except Exception:
                    pass
            
            if not page_valid:
                auto._page = None  # Reset reference
                ok = await auto.open_browser()
                if not ok:
                    raise HTTPException(status_code=500, detail="Could not connect to browser")
                current_page = getattr(auto, '_page', None)
                if current_page is None:
                    raise HTTPException(status_code=500, detail="Browser opened but page not available")
            
            file_path = await download_single_video(
                current_page, 
                video.get("title", ""), 
                download_dir
            )
        
        if file_path and os.path.isfile(file_path):
            # Update video info
            info = get_video_info(file_path)
            updates = {"file_path": file_path, "status": "downloaded"}
            if info:
                updates["size"] = format_file_size(info.get("size", 0))
                updates["duration"] = format_duration(info.get("duration", 0))
            
            update_video(video_id, updates)
            
            _log.append({"level": "info", "msg": f"downloaded video: {video.get('title')}"})
            logger.info(f"[download_video] success: {file_path}")
            
            return {"ok": True, "file_path": file_path, "size": updates.get("size")}
        else:
            raise HTTPException(status_code=500, detail="Download failed")
            
    except HTTPException:
        raise
    except Exception as e:
        _log.append({"level": "error", "msg": f"download_video_failed: {e}"})
        logger.error(f"[download_video] failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/videos/download-batch")
async def api_download_batch(payload: Dict[str, Any]):
    """Download multiple videos by IDs"""
    video_ids = payload.get("video_ids") or []
    if not video_ids:
        raise HTTPException(status_code=400, detail="video_ids required")
    
    results = []
    errors = []
    
    for vid in video_ids:
        try:
            result = await api_download_video(vid)
            results.append({"id": vid, "ok": True, "file_path": result.get("file_path")})
        except Exception as e:
            errors.append({"id": vid, "error": str(e)})
    
    return {"ok": True, "downloaded": len(results), "errors": errors, "results": results}


@app.post("/videos/merge")
async def api_merge_videos(payload: Dict[str, Any]):
    """Merge selected videos using FFmpeg"""
    video_ids = payload.get("video_ids") or []
    output_name = payload.get("output_name") or f"merged_{int(time.time())}.mp4"
    
    if not video_ids or len(video_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 video_ids required")
    
    try:
        videos = get_video_list()
        videos_by_id = {v.get("id"): v for v in videos}
        
        # Collect input file paths in order
        input_files = []
        missing = []
        
        for vid in video_ids:
            video = videos_by_id.get(vid)
            if not video:
                missing.append(vid)
                continue
            
            file_path = video.get("file_path")
            if not file_path or not os.path.isfile(file_path):
                missing.append(vid)
                continue
            
            input_files.append(file_path)
        
        if missing:
            raise HTTPException(
                status_code=400, 
                detail=f"Missing or not downloaded videos: {missing}"
            )
        
        # Get video quality settings from config
        bitrate = int(runner.config.get("video_bitrate_kbps") or 5000)
        resolution = str(runner.config.get("video_resolution") or "1080p")
        video_codec = str(runner.config.get("video_codec") or "h264")
        audio_codec = str(runner.config.get("audio_codec") or "aac")
        
        # Output path
        download_dir = str(runner.config.get("download_dir") or "./downloads")
        os.makedirs(download_dir, exist_ok=True)
        output_path = os.path.join(download_dir, output_name)
        
        # Run FFmpeg merge
        _log.append({"level": "info", "msg": f"merging {len(input_files)} videos..."})
        logger.info(f"[merge_videos] merging {len(input_files)} videos to {output_path}")
        
        return_code = ffmpeg_concat_advanced(
            inputs=input_files,
            output_path=output_path,
            bitrate_kbps=bitrate,
            resolution=resolution,
            video_codec=video_codec,
            audio_codec=audio_codec
        )
        
        if return_code != 0:
            raise HTTPException(status_code=500, detail="FFmpeg merge failed")
        
        # Get output file info
        info = get_video_info(output_path)
        size_str = format_file_size(info.get("size", 0)) if info else None
        duration_str = format_duration(info.get("duration", 0)) if info else None

        try:
            merged_entry = {
                "title": output_name,
                "file_path": output_path,
                "size": size_str,
                "duration": duration_str,
                "duration_sec": info.get("duration") if info else None,
                "merged": True,
                "created_at": _now_iso(),
            }
            add_video(merged_entry)
        except Exception:
            pass
        
        _log.append({"level": "info", "msg": f"merge complete: {output_path}"})
        logger.info(f"[merge_videos] complete: {output_path}")
        
        return {
            "ok": True, 
            "output_path": output_path,
            "size": size_str,
            "duration": duration_str,
            "video_count": len(input_files)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        _log.append({"level": "error", "msg": f"merge_videos_failed: {e}"})
        logger.error(f"[merge_videos] failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/videos/{video_id}")
def api_delete_video(video_id: str):
    """Delete a video from state (optionally delete file)"""
    videos = get_video_list()
    video = None
    for v in videos:
        if v.get("id") == video_id:
            video = v
            break
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Delete the file if it exists
    file_path = video.get("file_path")
    if file_path and os.path.isfile(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            logger.warning(f"Could not delete file {file_path}: {e}")
    
    # Remove from state
    state_delete_video(video_id)
    
    return {"ok": True}


@app.post("/videos/clear")
def api_clear_videos():
    """Clear all videos from state"""
    from ui.state import clear_videos
    clear_videos()
    return {"ok": True}


@app.put("/videos/{video_id}")
def api_update_video(video_id: str, payload: Dict[str, Any]):
    """Update video metadata"""
    result = update_video(video_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"ok": True, "video": result}


@app.post("/reveal-in-finder")
def api_reveal_in_finder(payload: Dict[str, Any]):
    """Open file in Finder (macOS) or file explorer"""
    file_path = payload.get("path")
    if not file_path:
        raise HTTPException(status_code=400, detail="Path required")
    
    import subprocess
    import platform
    
    abs_path = os.path.abspath(file_path)
    
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail=f"File not found: {abs_path}")
    
    try:
        system = platform.system()
        if system == "Darwin":  # macOS
            subprocess.run(["open", "-R", abs_path], check=True)
        elif system == "Windows":
            subprocess.run(["explorer", "/select,", abs_path], check=True)
        else:  # Linux
            subprocess.run(["xdg-open", os.path.dirname(abs_path)], check=True)
        
        return {"ok": True, "path": abs_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
