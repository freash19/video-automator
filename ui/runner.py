import asyncio
import json
import os
import sys
from typing import Callable, Dict, Any, List, Optional

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from heygen_automation import HeyGenAutomation
from ui.state import save_recent_episodes

class RunnerEvents:
    def __init__(self):
        self.on_notice: Optional[Callable[[str], None]] = None
        self.on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_step: Optional[Callable[[Dict[str, Any]], None]] = None

class AutomationRunner:
    def __init__(self, config_path: str = "config.json"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self.csv_path = self.config.get("csv_file", "scenarios.csv")
        self.events = RunnerEvents()
        self.max_concurrency = int(self.config.get("max_concurrency", 2))
        self.parallel_mode = str(self.config.get("parallel_mode", "tabs"))
        self.headless = bool(self.config.get("headless", False))
        self.automation = HeyGenAutomation(self.csv_path, self.config)
        self.episodes: List[str] = []
        self.cancel = False
        self._tasks: List[asyncio.Task] = []

    def _is_browser_closed_error(self, msg: str) -> bool:
        text = str(msg or "")
        return "Target page, context or browser has been closed" in text or "has been closed" in text or "closed by user" in text

    def set_events(self, events: RunnerEvents):
        self.events = events
        try:
            self.automation.set_hooks(on_notice=self.events.on_notice, on_step=self.events.on_step)
        except Exception:
            pass

    async def load(self) -> None:
        self.automation.load_data()
        eps = self.config.get("episodes_to_process") or []
        if not eps:
            try:
                eps = sorted([str(e) for e in self.automation.df["episode_id"].dropna().unique()])
            except Exception:
                eps = []
        self.episodes = eps

    async def run_many(self, episodes: List[str]) -> bool:
        sem = asyncio.Semaphore(self.max_concurrency)
        results = []

        async def run_ep_part(ep: str, part: int) -> bool:
            async with sem:
                if self.cancel:
                    return False
                if self.events.on_step:
                    self.events.on_step({"type": "start_part", "episode": ep, "part": part})
                try:
                    from ui.state import update_project_status
                    update_project_status(ep, "running")
                except Exception:
                    pass
                ok = False
                try:
                    ok = await self.automation.process_episode_part(ep, part)
                except Exception as e:
                    if self._is_browser_closed_error(str(e)):
                        self.cancel = True
                        for t in self._tasks:
                            if not t.done():
                                try:
                                    t.cancel()
                                except Exception:
                                    pass
                    if self.events.on_notice:
                        self.events.on_notice(f"error: episode={ep} part={part} err={str(e)}")
                rep = None
                try:
                    rep = getattr(self.automation, "report", None)
                except Exception:
                    rep = None
                rep_summary = None
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
                if self.events.on_step:
                    payload = {"type": "finish_part", "episode": ep, "part": part, "ok": bool(ok)}
                    if rep_summary is not None:
                        payload["report"] = rep_summary
                    self.events.on_step(payload)
                if self.events.on_notice:
                    self.events.on_notice(f"finish: episode={ep} part={part} ok={bool(ok)}")
                try:
                    from ui.state import update_project_status
                    update_project_status(ep, "completed" if ok else "failed")
                except Exception:
                    pass
                try:
                    if bool(self.config.get("close_browser_on_finish", True)):
                        await self.automation.close_browser()
                except Exception:
                    pass
                return bool(ok)

        tasks = []
        for ep in episodes:
            parts = self.automation.get_all_episode_parts(ep)
            for p in parts:
                tasks.append(asyncio.create_task(run_ep_part(ep, p)))
        self._tasks = tasks

        total = len(tasks)
        done = 0
        ok_all = True
        cancelled_once = False
        try:
            for coro in asyncio.as_completed(tasks):
                if self.cancel and not cancelled_once:
                    cancelled_once = True
                    ok_all = False
                    for t in tasks:
                        if not t.done():
                            try:
                                t.cancel()
                            except Exception:
                                pass
                try:
                    ok = await coro
                except asyncio.CancelledError:
                    ok = False
                except Exception:
                    ok = False
                done += 1
                ok_all = ok_all and ok
                if self.events.on_progress:
                    self.events.on_progress({"done": done, "total": total})
        finally:
            if self.cancel:
                ok_all = False
                for t in tasks:
                    if not t.done():
                        try:
                            t.cancel()
                        except Exception:
                            pass
                try:
                    await asyncio.gather(*tasks, return_exceptions=True)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass
        save_recent_episodes(episodes)
        return ok_all

    def stop(self):
        self.cancel = True
        for t in self._tasks:
            try:
                t.cancel()
            except Exception:
                pass

    def csv_stats(self) -> Dict[str, Any]:
        df = self.automation.df
        if df is None:
            return {"episodes": [], "parts": 0, "scenes": 0, "templates": {}, "words": 0, "chars": 0, "broll_scenes": 0, "broll_count": 0}

        try:
            ep_series = df.get("episode_id")
            if ep_series is None:
                return {"episodes": [], "parts": 0, "scenes": 0, "templates": {}, "words": 0, "chars": 0, "broll_scenes": 0, "broll_count": 0}
            eps = sorted([str(e) for e in ep_series.dropna().unique()])
        except Exception:
            eps = []

        total_parts = 0
        total_scenes = 0
        templates: Dict[str, str] = {}
        words = 0
        chars = 0
        broll_scenes = 0
        broll_count = 0

        try:
            part_series = df.get("part_idx")
            if part_series is not None:
                total_parts = int(df.groupby("episode_id")["part_idx"].nunique(dropna=True).sum())
        except Exception:
            total_parts = 0

        try:
            total_scenes = int(df[df.get("scene_idx").notna()].shape[0]) if df.get("scene_idx") is not None else int(df.shape[0])
        except Exception:
            total_scenes = 0

        try:
            text_series = df.get("text")
            if text_series is not None:
                t = text_series.fillna("").astype(str)
                chars = int(t.str.len().sum())
                words = int(t.str.count(r"\S+").sum())
        except Exception:
            words = 0
            chars = 0

        try:
            b = df.get("brolls")
            if b is not None:
                b2 = b.fillna("").astype(str).str.strip()
                b2 = b2.mask(b2.str.lower() == "nan", "")
                broll_scenes = int((b2 != "").sum())
                broll_count = broll_scenes
        except Exception:
            broll_scenes = 0
            broll_count = 0

        try:
            tmpl_series = df.get("template_url")
            if tmpl_series is not None:
                tmp = df[["episode_id", "template_url"]].dropna(subset=["episode_id"])
                first = tmp.groupby("episode_id")["template_url"].first()
                templates = {str(k): str(v) for k, v in first.to_dict().items() if v is not None}
        except Exception:
            templates = {}

        return {"episodes": eps, "parts": total_parts, "scenes": total_scenes, "templates": templates, "words": words, "chars": chars, "broll_scenes": broll_scenes, "broll_count": broll_count}

    def estimate_time_sec(self, scenes: int) -> float:
        a = float(self.config.get("pre_fill_wait", 1.5))
        b = float(self.config.get("delay_between_scenes", 1.5))
        c = float(self.config.get("save_fallback_wait_sec", 7.0))
        d = float(self.config.get("post_reload_wait", 1.5))
        per_scene = b + 0.5
        overhead = a + c + d + 10.0
        return scenes * per_scene + overhead

    def apply_episode_overrides(self, episode_id: str, title: Optional[str], template_url: Optional[str]) -> None:
        try:
            if title:
                self.automation.df.loc[self.automation.df['episode_id'] == episode_id, 'title'] = title
            if template_url:
                self.automation.df.loc[self.automation.df['episode_id'] == episode_id, 'template_url'] = template_url
        except Exception:
            pass
