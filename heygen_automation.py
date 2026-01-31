import asyncio
import pandas as pd
import random
from playwright.async_api import async_playwright, Page, Locator
import os
import json
import re
import argparse
import subprocess
import sys
from typing import Awaitable, Callable, Any
from ui.step_wrapper import step
from ui.logger import logger
from automation_models import TaskStatus, AutomationStep, Metrics, StepStatus
from core.config import get_settings
from core.broll import (
    select_media_source, 
    select_orientation, 
    select_video_tab,
    try_delete_foreground,
    open_media_panel,
    handle_nano_banano
)
from core.browser import prepare_canvas_for_broll, human_coordinate_click, human_fast_center_click
from utils.clipboard import parse_nano_banano_prompt

class HeyGenAutomation:
    def __init__(self, csv_path: str, config: dict, browser=None, playwright=None):
        """
        Инициализация автоматизации HeyGen
        
        Args:
            csv_path: Путь к CSV файлу со сценариями
            config: Конфигурация
            browser: Опциональный объект браузера Playwright
            playwright: Опциональный объект Playwright
        """
        self.csv_path = csv_path
        self.df = None
        self.config = config or {}
        self.browser = browser
        self.playwright = playwright
        self.max_scenes = int(self.config.get('max_scenes', 15))
        self.pre_fill_wait = float(self.config.get('pre_fill_wait', 1.0))
        self.delay_between_scenes = float(self.config.get('delay_between_scenes', 2.5))
        self.min_unfilled_scenes_visible = int(self.config.get('min_unfilled_scenes_visible', 4))
        
        try:
            if 'pre_generation_pause_sec' in self.config:
                self.confirm_timeout_sec = int(self.config.get('pre_generation_pause_sec', 10))
            else:
                self.confirm_timeout_sec = int(self.config.get('confirm_timeout_sec', 10))
        except Exception:
            self.confirm_timeout_sec = 10
        self.post_reload_wait = float(self.config.get('post_reload_wait', 1.5))
        self.search_results_timeout_ms = int(self.config.get('search_results_timeout_ms', 5000))
        self.validation_ready_timeout_ms = int(self.config.get('validation_ready_timeout_ms', 6000))
        self.reload_timeout_ms = int(self.config.get('reload_timeout_ms', 90000))
        self.generation_redirect_timeout_ms = int(self.config.get('generation_redirect_timeout_ms', 120000))
        self.save_notification_timeout_ms = int(self.config.get('save_notification_timeout_ms', 4000))
        self.save_fallback_wait_sec = float(self.config.get('save_fallback_wait_sec', 7.0))
        self.close_media_panel_after_broll = bool(self.config.get('close_media_panel_after_broll', True))
        self.orientation_choice = str(self.config.get('orientation_choice', 'Горизонтальная'))
        self.media_source = str(self.config.get('media_source', 'all')).lower()
        self.enable_notifications = bool(self.config.get('enable_notifications', False))
        self.verify_scene_after_insert = bool(self.config.get('verify_scene_after_insert', False))
        self._broll_delay_range = (
            float(self.config.get('broll_step_delay_min_sec', 0.25)),
            float(self.config.get('broll_step_delay_max_sec', 0.55)),
        )
        self.broll_before_make_bg_wait_sec = float(self.config.get('broll_before_make_bg_wait_sec', 0.7))
        self.broll_after_make_bg_min_wait_sec = float(self.config.get('broll_after_make_bg_min_wait_sec', 0.9))
        self._on_notice = None
        self._on_step = None
        self.csv_columns = self.config.get('csv_columns') or {}
        self.episodes_to_process = self.config.get('episodes_to_process') or []
        self.report = None
        self.pause_events = []
        self._current_episode_id = None
        self._current_part_idx = None
        self._last_error = ""
        self._page = None
        self.task_status: TaskStatus | None = None
        try:
            os.makedirs("debug/screenshots", exist_ok=True)
        except Exception:
            pass

    def _coerce_scalar(self, v):
        if isinstance(v, pd.Series):
            if len(v) == 0:
                return None
            try:
                return v.iloc[0]
            except Exception:
                return None
        if isinstance(v, pd.DataFrame):
            if v.shape[0] == 0 or v.shape[1] == 0:
                return None
            try:
                return v.iat[0, 0]
            except Exception:
                return None
        return v

    def _as_clean_str(self, v) -> str:
        v2 = self._coerce_scalar(v)
        if v2 is None:
            return ""
        try:
            if pd.isna(v2):
                return ""
        except Exception:
            pass
        s = str(v2)
        return s.strip()

    def _normalize_speaker_key(self, speaker: str | None) -> str | None:
        if not speaker:
            return None
        s = str(speaker).strip()
        if not s:
            return None
        compact = re.sub(r"[^a-zA-Z0-9]+", " ", s).strip().lower()
        mapping = {
            "dr peter": "Dr_Peter",
            "doctor peter": "Dr_Peter",
            "peter": "Dr_Peter",
            "michael": "Michael",
            "hiroshi": "Hiroshi",
        }
        if compact in mapping:
            return mapping[compact]
        safe = re.sub(r"[^a-zA-Z0-9_\-]+", "_", s).strip("_")
        return safe or None

    async def _scroll_scene_list_until_label(
        self,
        page: Page,
        label: str,
        max_scrolls: int = 40,
        delta_px: int = 700,
    ) -> bool:
        target = page.locator('span[data-node-view-content-react]').filter(
            has_text=re.compile(rf'^\s*{re.escape(label)}\s*$', re.I)
        )
        try:
            if await target.count() > 0:
                return True
        except Exception:
            pass

        try:
            await page.wait_for_selector('span[data-node-view-content-react]', timeout=4000)
        except Exception:
            pass

        async def _reset_to_top() -> None:
            try:
                await page.evaluate(
                    """
                    (sel) => {
                      const pickAnchor = (sel) => {
                        const els = Array.from(document.querySelectorAll(sel) || []);
                        let best = null;
                        let bestX = Infinity;
                        for (const el of els) {
                          const r = el.getBoundingClientRect();
                          if (!r || r.width <= 1 || r.height <= 1) continue;
                          if (r.bottom < 0 || r.top > window.innerHeight) continue;
                          if (r.left < bestX) {
                            bestX = r.left;
                            best = el;
                          }
                        }
                        return best || document.querySelector(sel);
                      };
                      const el = pickAnchor(sel);
                      if (!el) return;
                      const isScrollable = (n) => {
                        if (!n) return false;
                        const s = getComputedStyle(n);
                        const oy = s.overflowY;
                        return (oy === 'auto' || oy === 'scroll') && n.scrollHeight > n.clientHeight;
                      };
                      let p = el.parentElement;
                      while (p && !isScrollable(p)) p = p.parentElement;
                      const sc = p || document.scrollingElement;
                      if (sc) sc.scrollTop = 0;
                    }
                    """,
                    'span[data-node-view-content-react]',
                )
            except Exception:
                return

        async def _scroll_down() -> bool:
            try:
                res = await page.evaluate(
                        """
                        (sel, delta) => {
                          const pickAnchor = (sel) => {
                            const els = Array.from(document.querySelectorAll(sel) || []);
                            let best = null;
                            let bestX = Infinity;
                            for (const el of els) {
                              const r = el.getBoundingClientRect();
                              if (!r || r.width <= 1 || r.height <= 1) continue;
                              if (r.bottom < 0 || r.top > window.innerHeight) continue;
                              if (r.left < bestX) {
                                bestX = r.left;
                                best = el;
                              }
                            }
                            return best || document.querySelector(sel);
                          };
                          const el = pickAnchor(sel);
                          if (!el) return { moved: false, x: null, y: null };
                          const r0 = el.getBoundingClientRect();
                          const x = r0 ? (r0.left + r0.width / 2) : null;
                          const y = r0 ? (r0.top + r0.height / 2) : null;
                          const isScrollable = (n) => {
                            if (!n) return false;
                            const s = getComputedStyle(n);
                            const oy = s.overflowY;
                            return (oy === 'auto' || oy === 'scroll') && n.scrollHeight > n.clientHeight;
                          };
                          let p = el.parentElement;
                          while (p && !isScrollable(p)) p = p.parentElement;
                          const sc = p || document.scrollingElement;
                          if (!sc) return { moved: false, x, y };
                          const prev = sc.scrollTop;
                          sc.scrollTop = Math.min(sc.scrollTop + delta, sc.scrollHeight);
                          return { moved: sc.scrollTop !== prev, x, y };
                        }
                        """,
                        'span[data-node-view-content-react]',
                        int(delta_px),
                    )
                moved = bool(res and res.get("moved"))
                if moved:
                    return True
                x = res.get("x") if isinstance(res, dict) else None
                y = res.get("y") if isinstance(res, dict) else None
                if x is not None and y is not None:
                    try:
                        await page.mouse.move(float(x), float(y))
                        await page.mouse.wheel(0, int(delta_px))
                        return True
                    except Exception:
                        return False
                return False
            except Exception:
                return False

        for pass_idx in range(2):
            if pass_idx == 1:
                await _reset_to_top()
                await asyncio.sleep(0.05)

            for _ in range(max_scrolls):
                try:
                    if await target.count() > 0:
                        return True
                except Exception:
                    pass

                moved = await _scroll_down()
                if not moved:
                    break
                await asyncio.sleep(0.05)

        try:
            return await target.count() > 0
        except Exception:
            return False

    async def _ensure_min_unfilled_scenes_visible(
        self,
        page: Page,
        current_scene_idx: int,
        min_visible: int = 4,
        max_steps: int = 25,
        delta_px: int = 650,
    ) -> None:
        """
        Scroll the current scene to the center of the viewport.
        This handles both early scenes (providing context above) and late scenes (avoiding bounce at bottom).
        """
        try:
            text_label = f"text_{current_scene_idx}"
            
            # Find the specific scene element
            span_locator = page.locator('span[data-node-view-content-react]').filter(
                has_text=re.compile(rf'^\s*{re.escape(text_label)}\s*$')
            )
            
            if await span_locator.count() > 0:
                # Scroll the element to the center of the view
                await span_locator.first.evaluate(
                    "(el) => el.scrollIntoView({ block: 'center', behavior: 'instant' })"
                )
                await asyncio.sleep(0.1)
                
        except Exception:
            pass

    def _generation_enabled(self) -> bool:
        return bool(self.config.get("enable_generation", True))

    async def _apply_part_title(self, page: Page, title: str) -> bool:
        t = str(title or "").strip()
        if not t:
            return True
        await self._await_gate()
        locator = page.get_by_role("textbox", name=re.compile(r"Без названия — видео", re.I))
        try:
            if await locator.count() == 0:
                locator = page.get_by_role("textbox", name=re.compile(r"Untitled", re.I))
        except Exception:
            pass
        try:
            if await locator.count() == 0:
                return False
        except Exception:
            return False
        try:
            await locator.first.click(timeout=8000)
        except Exception:
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
            try:
                await locator.first.click(timeout=8000, force=True)
            except Exception:
                pass
        await asyncio.sleep(0.05)
        try:
            await locator.first.fill(t)
        except Exception:
            try:
                handle = await locator.first.element_handle()
                if handle:
                    await page.evaluate(
                        "(el, value) => { el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }",
                        handle,
                        t,
                    )
            except Exception:
                return False
        await asyncio.sleep(0.05)
        return True

    def normalize_text_for_compare(self, text: str) -> str:
        try:
            t = str(text or '')
            if bool(self.config.get('enable_enhance_voice', False)):
                t = re.sub(r"\[[^\]]*\]", "", t)
            t = re.sub(r"\s+", " ", t).strip()
            return t
        except Exception:
            return str(text or '').strip()

    def set_hooks(self, on_notice=None, on_step=None):
        self._on_notice = on_notice
        self._on_step = on_step

    def _emit_notice(self, msg: str):
        try:
            if msg is None:
                return
            m = str(msg)
            print(m)
            if self._on_notice:
                self._on_notice(m)
        except Exception:
            pass

    def _emit_step(self, payload: dict):
        try:
            if self._on_step:
                p = dict(payload or {})
                if self._current_episode_id is not None and "episode" not in p:
                    p["episode"] = self._current_episode_id
                if self._current_part_idx is not None and "part" not in p:
                    p["part"] = self._current_part_idx
                self._on_step(p)
        except Exception:
            pass

    async def _await_gate(self):
        evs = getattr(self, "pause_events", None)
        if not evs:
            return
        for ev in list(evs):
            try:
                await ev.wait()
            except asyncio.CancelledError:
                raise
            except Exception:
                continue

    async def perform_step(self, name: str, action_func: Callable[[], Awaitable[Any]], critical: bool = True):
        step_rec = AutomationStep(name=name, status=StepStatus.PENDING)
        if self.task_status is None:
            self.task_status = TaskStatus(task_id=f"{self._current_episode_id}:{self._current_part_idx}")
        self.task_status.steps.append(step_rec)
        try:
            logger.info(f"[{name}] start")
            res = await action_func()
            if res is False:
                if critical:
                    step_rec.status = StepStatus.FAILED
                    logger.error(f"[{name}] failed")
                    if self.task_status:
                        self.task_status.global_status = "failed"
                    raise RuntimeError(f"{name} failed")
                step_rec.status = StepStatus.SKIPPED
                logger.warning(f"[{name}] skipped")
                return False
            step_rec.status = StepStatus.SUCCESS
            logger.info(f"[{name}] success")
            return res
        except asyncio.CancelledError:
            step_rec.status = StepStatus.FAILED
            logger.error(f"[{name}] cancelled")
            raise
        except Exception as e:
            err = str(e)
            step_rec.status = StepStatus.FAILED if critical else StepStatus.SKIPPED
            step_rec.error_message = err
            try:
                page = getattr(self, "_page", None)
                if page:
                    safe = "".join(ch for ch in name if ch.isalnum() or ch in "_-")
                    ts = int(asyncio.get_event_loop().time() * 1000)
                    path = f"debug/screenshots/{safe}_{ts}.png"
                    try:
                        await page.screenshot(path=path, full_page=True)
                        step_rec.screenshot_path = path
                    except Exception as se:
                        logger.error(f"[{name}] screenshot_failed: {se}")
            except Exception:
                pass
            try:
                logger.error(f"[{name}] failed: {err}")
                self._last_error = err
                if self.task_status and critical:
                    self.task_status.global_status = "failed"
            except Exception:
                pass
            if critical:
                raise
            return None

    async def _take_error_screenshot(self, page: Page, name: str):
        try:
            ts = int(asyncio.get_event_loop().time() * 1000)
            safe_name = "".join(ch for ch in name if ch.isalnum() or ch in "_-")
            path = f"debug/screenshots/{safe_name}_{ts}.png"
            await page.screenshot(path=path, full_page=True)
            self._emit_notice(f"📸 screenshot: {path}")
        except Exception as e:
            self._emit_notice(f"⚠️ screenshot failed: {e}")

    def _block_generation_reason(self) -> str:
        if not self.report:
            return ""
        reasons = []
        try:
            if self.report.get('validation_missing'):
                reasons.append(f"несоответствия: {len(self.report.get('validation_missing') or [])}")
        except Exception:
            pass
        try:
            if self.report.get('broll_skipped'):
                reasons.append(f"пропуски B-roll: {len(self.report.get('broll_skipped') or [])}")
        except Exception:
            pass
        try:
            if self.report.get('broll_errors'):
                reasons.append(f"ошибки B-roll: {len(self.report.get('broll_errors') or [])}")
        except Exception:
            pass
        try:
            if self.report.get('broll_no_results'):
                reasons.append(f"B-roll без результатов: {len(self.report.get('broll_no_results') or [])}")
        except Exception:
            pass
        try:
            if self.task_status and self.task_status.steps:
                skipped = [s for s in self.task_status.steps if s.status == StepStatus.SKIPPED]
                if skipped:
                    reasons.append(f"пропущенные шаги: {len(skipped)}")
        except Exception:
            pass
        return "; ".join(reasons)

    def _should_block_generation(self) -> bool:
        if not self.report:
            return False
        try:
            if self.report.get('validation_missing'):
                return True
        except Exception:
            pass
        try:
            if self.report.get('broll_skipped'):
                return True
        except Exception:
            pass
        try:
            if self.report.get('broll_errors'):
                return True
        except Exception:
            pass
        try:
            if self.report.get('broll_no_results'):
                return True
        except Exception:
            pass
        try:
            if self.task_status and self.task_status.steps:
                for s in self.task_status.steps:
                    if s.status == StepStatus.SKIPPED:
                        return True
        except Exception:
            pass
        return False

    async def _broll_pause(self, base: float = 0.0):
        try:
            await self._await_gate()
            a, b = self._broll_delay_range
            if a < 0:
                a = 0.0
            if b < a:
                b = a
            remaining = float(base) + random.uniform(a, b)
            if remaining <= 0:
                return
            while remaining > 0:
                await self._await_gate()
                chunk = 0.2 if remaining > 0.2 else remaining
                await asyncio.sleep(chunk)
                remaining -= chunk
        except asyncio.CancelledError:
            raise
        except Exception:
            try:
                await asyncio.sleep(float(base) if base else 0.1)
            except Exception:
                pass

    async def _try_click(self, loc, page: Page, timeout_ms: int = 8000) -> bool:
        try:
            await loc.scroll_into_view_if_needed()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        try:
            await loc.click(timeout=timeout_ms)
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        try:
            await loc.click(timeout=timeout_ms, force=True)
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        try:
            h = await loc.element_handle()
            if h:
                await page.evaluate("(el) => el && el.click && el.click()", h)
                return True
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        return False

    @step("open_media_panel")
    async def _open_media_panel(self, page: Page) -> bool:
        return await open_media_panel(page, gate_callback=self._await_gate)

    async def _select_video_tab(self, page: Page) -> bool:
        # Delegate to core.broll implementation which has been updated with fixes
        return await select_video_tab(page, gate_callback=self._await_gate)

    async def _locate_broll_search_input(self, page: Page):
        try:
            inp = page.get_by_role("textbox", name=re.compile(r"(Искать видео онлайн|Search videos online)", re.I))
            if await inp.count() > 0:
                return inp.first
        except Exception:
            pass
        selectors = [
            'input[placeholder*="Искать"][placeholder*="онлайн"]',
            'input[placeholder="Искать видео онлайн"]',
            'input[placeholder="Искать Изображение онлайн"]',
            'input[placeholder*="Search"][placeholder*="online"]',
            'input[placeholder="Search videos online"]',
            'input[type="search"]',
        ]
        for sel in selectors:
            try:
                loc = page.locator(sel)
                if await loc.count() > 0:
                    return loc.first
            except Exception:
                continue
        return None

    async def _locate_broll_result_card(self, page: Page):
        candidates = [
            page.locator('[role="option"]'),
            page.locator('[role="listitem"]'),
            page.locator('[role="button"][aria-label*="video" i]'),
            page.locator('[role="button"][aria-label*="видео" i]'),
            page.locator('div.tw-group').filter(has=page.locator('img, video')),
            page.locator('[role="button"]').filter(has=page.locator('img, video')),
        ]
        for loc in candidates:
            try:
                if await loc.count() > 0:
                    return loc.first
            except Exception:
                continue
        return None

    async def _read_locator_text(self, locator: Locator) -> str:
        try:
            val = await locator.inner_text(timeout=1500)
            if val is not None:
                return str(val)
        except Exception:
            pass
        try:
            val = await locator.text_content(timeout=1500)
            if val is not None:
                return str(val)
        except Exception:
            pass
        return ""

    async def _fast_replace_text(self, page: Page, locator: Locator, text: str) -> None:
        try:
            await locator.scroll_into_view_if_needed()
        except Exception:
            pass
        try:
            await locator.click(timeout=3000)
        except Exception:
            try:
                await locator.click(timeout=3000, force=True)
            except Exception:
                pass
        await self._await_gate()
        try:
            await page.keyboard.press('Meta+A')
            await asyncio.sleep(0.05)
            await page.keyboard.press('Backspace')
            await asyncio.sleep(0.05)
            await page.keyboard.insert_text(text)
            await asyncio.sleep(0.1)
            await page.keyboard.press('Tab')
        except Exception:
            pass

    async def _verify_scene_text(self, page: Page, locator: Locator, expected: str) -> bool:
        target = str(expected or "").strip()
        if not target:
            return True
        for attempt in range(3):
            await self._await_gate()
            await asyncio.sleep(0.2)
            try:
                matches = page.get_by_text(target, exact=True)
                if await matches.count() > 0:
                    return True
            except Exception:
                pass
            if attempt == 0:
                await self._fast_replace_text(page, locator, expected)
            else:
                try:
                    await page.keyboard.press('Tab')
                except Exception:
                    pass
        self._emit_notice("❌ scene_verify_failed")
        return False

    @step("confirm_broll_added")
    async def _confirm_broll_added(self, page: Page, min_wait_sec: float = 0.0) -> bool:
        try:
            if min_wait_sec and min_wait_sec > 0:
                await self._broll_pause(float(min_wait_sec))
            for _ in range(50):
                busy = page.locator('[aria-busy="true"]')
                try:
                    if await busy.count() > 0:
                        await self._broll_pause(0.2)
                        continue
                except Exception:
                    pass
                return True
            return True
        except Exception:
            return True

    async def _try_delete_foreground(self, page: Page) -> bool:
        clicks = [(0.5, 0.5), (0.5, 0.42), (0.5, 0.62), (0.4, 0.5), (0.6, 0.5)]
        pressed_any = False
        for (rx, ry) in clicks:
            try:
                try:
                    await page.keyboard.press("Escape")
                except Exception:
                    pass
                canvas = page.locator("canvas").first
                box = await canvas.bounding_box()
                if box:
                    await page.mouse.click(box["x"] + box["width"] * rx, box["y"] + box["height"] * ry)
                else:
                    vs = page.viewport_size
                    if vs:
                        await page.mouse.click(vs["width"] * rx, vs["height"] * ry)
            except Exception:
                try:
                    vs = page.viewport_size
                    if vs:
                        await page.mouse.click(vs["width"] * rx, vs["height"] * ry)
                except Exception:
                    pass

            await self._broll_pause(0.2)
            for key in ("Backspace", "Delete"):
                try:
                    await page.keyboard.press(key)
                    pressed_any = True
                    break
                except Exception:
                    continue
            await self._broll_pause(0.2)
            if pressed_any:
                break
        return pressed_any

    async def _click_scene_center(self, page: Page) -> bool:
        try:
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
            canvas = page.locator("canvas").first
            box = await canvas.bounding_box()
            if box:
                await page.mouse.click(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5)
                return True
            vs = page.viewport_size
            if vs:
                await page.mouse.click(vs["width"] * 0.5, vs["height"] * 0.5)
                return True
        except Exception:
            pass
        return False

    def load_data(self):
        """Загрузить данные из CSV"""
        print(f"📁 Загружаю данные из {self.csv_path}...")
        try:
            try:
                self.df = pd.read_csv(self.csv_path, encoding='utf-8-sig', sep=None, engine='python')
            except Exception:
                self.df = pd.read_csv(self.csv_path, encoding='utf-8', sep=None, engine='python')
        except Exception as e:
            print(f"❌ Ошибка чтения CSV: {e}")
            raise
        print(f"✅ Загружено {len(self.df)} строк")
        # Нормализация названий колонок (удаление BOM и лишних пробелов)
        cols_before = list(self.df.columns)
        norm_map = {}
        for c in cols_before:
            c2 = str(c).replace('\ufeff', '').strip()
            norm_map[c] = c2
        if norm_map:
            self.df = self.df.rename(columns=norm_map)
        print(f"Колонки: {list(self.df.columns)}")
        # Поддержка кастомных имен колонок
        colmap = {
            'episode_id': self.csv_columns.get('episode_id', 'episode_id'),
            'part_idx': self.csv_columns.get('part_idx', 'part_idx'),
            'scene_idx': self.csv_columns.get('scene_idx', 'scene_idx'),
            'text': self.csv_columns.get('text', 'text'),
            'title': self.csv_columns.get('title', 'title'),
            'template_url': self.csv_columns.get('template_url', 'template_url'),
            'speaker': self.csv_columns.get('speaker', 'speaker'),
            'brolls': self.csv_columns.get('brolls', 'brolls')
        }
        required = [colmap['episode_id'], colmap['part_idx'], colmap['scene_idx'], colmap['text']]
        # Авто-замена известных синонимов
        synonyms = {
            'brolls': ['broll_query', 'broll', 'broll_query_ru']
        }
        for target, alts in synonyms.items():
            if target not in self.df.columns:
                for a in alts:
                    if a in self.df.columns:
                        self.df = self.df.rename(columns={a: target})
                        break
        missing = [c for c in required if c not in self.df.columns]
        if missing:
            print(f"❌ Отсутствуют обязательные колонки: {missing}")
            print("   Убедись, что разделитель CSV — ';' или ',' и первая строка содержит заголовки.")
            raise KeyError(f"Missing columns: {missing}")
        # Переименовываем в стандартные названия
        ren = {v: k for k, v in colmap.items() if v in self.df.columns}
        if ren:
            self.df = self.df.rename(columns=ren)
        try:
            self.df['part_idx'] = pd.to_numeric(self.df['part_idx'], errors='coerce')
            self.df['scene_idx'] = pd.to_numeric(self.df['scene_idx'], errors='coerce')
        except Exception:
            pass
        return self.df
    
    def get_all_episode_parts(self, episode_id: str):
        """
        Получить все части конкретного эпизода
        
        Args:
            episode_id: ID эпизода (например, 'ep_1')
            
        Returns:
            list: Список номеров частей
        """
        episode_data = self.df[self.df['episode_id'] == episode_id]
        
        if episode_data.empty:
            return []
        vals = pd.to_numeric(episode_data['part_idx'], errors='coerce').dropna().tolist()
        parts = sorted({int(v) for v in vals})
        return parts
    
    def get_episode_data(self, episode_id: str, part_idx: int):
        """
        Получить данные для конкретного эпизода и части
        
        Args:
            episode_id: ID эпизода (например, 'ep_1')
            part_idx: Номер части (например, 1)
            
        Returns:
            tuple: (template_url, list of scenes)
        """
        # Фильтруем данные по episode_id и part_idx
        episode_data = self.df[
            (self.df['episode_id'] == episode_id) & 
            (self.df['part_idx'] == part_idx)
        ].copy()
        
        if episode_data.empty:
            print(f"⚠️ Нет данных для {episode_id}, часть {part_idx}")
            return None, []
        
        # Получаем URL шаблона из ЛЮБОЙ строки этого эпизода (они одинаковые для всех частей)
        episode_rows = self.df[self.df['episode_id'] == episode_id]
        template_url = None
        if 'template_url' in episode_rows.columns and len(episode_rows) > 0:
            template_url = self._as_clean_str(episode_rows.iloc[0]['template_url'])
            if not template_url:
                template_url = None
        
        episode_data = episode_data.sort_values('scene_idx', key=lambda s: pd.to_numeric(s, errors='coerce'))
        
        # Формируем список сцен
        scenes = []
        for _, row in episode_data.iterrows():
            bval = self._as_clean_str(row.get('brolls', None))
            bval = '' if bval.lower() == 'nan' else bval
            sidx_raw = self._coerce_scalar(row.get('scene_idx'))
            sidx_num = pd.to_numeric(sidx_raw, errors='coerce')
            sidx = 0
            try:
                sidx = 0 if pd.isna(sidx_num) else int(sidx_num)
            except Exception:
                sidx = 0
            text_v = self._coerce_scalar(row.get('text'))
            if text_v is None:
                text_s = ''
            else:
                try:
                    text_s = '' if pd.isna(text_v) else str(text_v)
                except Exception:
                    text_s = str(text_v)
            scenes.append({
                'scene_idx': sidx,
                'speaker': self._as_clean_str(row.get('speaker')),
                'text': text_s,
                'title': self._as_clean_str(row.get('title')) or f"{episode_id}_part_{part_idx}",
                'brolls': bval
            })
        
        print(f"📋 Эпизод: {episode_id}, Часть: {part_idx}")
        print(f"🔗 URL шаблона: {template_url}")
        print(f"🎬 Сцен для заполнения: {len(scenes)}")
        
        return template_url, scenes
    
    @step("fill_scene")
    async def fill_scene(self, page: Page, scene_number: int, text: str, speaker: str | None = None):
        """
        Заполнить конкретную сцену текстом
        
        Args:
            page: Playwright страница
            scene_number: Номер сцены (1, 2, 3, ...)
            text: Текст для вставки
        """
        text_label = f"text_{scene_number}"
        self._emit_notice(f"✏️ scene_start: scene={scene_number} label={text_label}")
        self._emit_step({"type": "start_scene", "scene": scene_number})
        
        try:
            await self._await_gate()
            # Ищем span с текстом text_X (строгий матч по всей строке)
            span_locator = page.locator('span[data-node-view-content-react]').filter(
                has_text=re.compile(rf'^\s*{re.escape(text_label)}\s*$')
            )
            
            # Проверяем существование
            count = await span_locator.count()
            if count == 0:
                await self._scroll_scene_list_until_label(page, text_label)
                try:
                    count = await span_locator.count()
                except Exception:
                    count = 0
                if count == 0:
                    self._emit_notice(f"⚠️ scene_field_missing: scene={scene_number} label={text_label}")
                    self._emit_step({"type": "finish_scene", "scene": scene_number, "ok": False})
                    return False

            await self._ensure_min_unfilled_scenes_visible(
                page,
                scene_number,
                min_visible=self.min_unfilled_scenes_visible,
            )
            
            safe_speaker = self._normalize_speaker_key(speaker)

            async def _select_scene():
                await self._await_gate()
                await span_locator.first.scroll_into_view_if_needed()
                try:
                    await page.keyboard.press('Escape')
                except Exception:
                    pass
                ok = await human_fast_center_click(page, span_locator.first)
                if not ok:
                    return False
                await self._await_gate()
                await asyncio.sleep(random.uniform(0.1, 0.2))
                try:
                    s_over = (self.config.get('step_overrides') or {}).get('fill_scene') or {}
                    extra_delay = float(s_over.get('delay_sec', 0))
                    if extra_delay > 0:
                        await asyncio.sleep(extra_delay)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass
                return True

            step_name_select = f"select_scene_{scene_number}" if not safe_speaker else f"select_scene_{scene_number}_{safe_speaker}"
            ok_select = await self.perform_step(step_name_select, _select_scene, critical=True)
            if not ok_select:
                self._emit_notice(f"❌ scene_focus_failed: scene={scene_number} label={text_label}")
                self._emit_step({"type": "finish_scene", "scene": scene_number, "ok": False})
                return False

            async def _insert_text():
                await self._await_gate()
                
                # --- Verification Step ---
                # Check if we really focused the correct scene before deleting anything
                try:
                    # We expect to see 'text_N'
                    expected_placeholder = f"text_{scene_number}"
                    
                    # Read current text from the active element (which we just clicked)
                    current_content = await span_locator.first.inner_text(timeout=1000)
                    current_content = current_content.strip()
                    
                    # Regex to see if it looks like ANY placeholder 'text_M'
                    m = re.fullmatch(r"text_(\d+)", current_content)
                    
                    if m:
                        found_idx = int(m.group(1))
                        if found_idx != scene_number:
                            # CRITICAL ERROR: We are about to overwrite the WRONG scene!
                            self._emit_notice(f"❌ Safety Abort: Wanted scene {scene_number}, but focused scene {found_idx}")
                            # Unfocus to be safe
                            await page.keyboard.press('Escape')
                            return False
                    else:
                        # If the text is NOT a placeholder (e.g. it's already filled text),
                        # we should probably proceed carefully. But usually we are filling empty templates.
                        # For now, we only block if we see a conflicting placeholder number.
                        pass
                        
                except Exception:
                    # If we can't read text, proceed at own risk or log warning
                    pass
                # -------------------------

                await page.keyboard.press('Meta+A')
                await asyncio.sleep(0.05)
                await page.keyboard.press('Backspace')
                await asyncio.sleep(random.uniform(0.05, 0.1))

                await self._await_gate()
                await page.keyboard.insert_text(text)
                await asyncio.sleep(random.uniform(0.1, 0.2))
                await page.keyboard.press('Tab')
                await asyncio.sleep(random.uniform(0.1, 0.2))
                try:
                    if bool(self.config.get('enable_enhance_voice', False)):
                        btn = page.locator('button#voice-enhancement-jeFjSzUn:has-text("Enhance Voice")')
                        if await btn.count() == 0:
                            btn = page.locator('button:has(iconpark-icon[name="director-mode"])').filter(has_text=re.compile(r'^\s*Enhance Voice\s*$'))
                        if await btn.count() > 0:
                            await btn.first.click(timeout=3000)
                            await asyncio.sleep(0.1)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass

                if self.config.get('enable_enhance_voice'):
                    try:
                        enhance_buttons = page.locator('button:has(iconpark-icon[name="director-mode"])').filter(has_text=re.compile(r'Enhance Voice|Усилить голос'))
                        button_count = await enhance_buttons.count()
                        if button_count > 0:
                            await enhance_buttons.last.click()
                            await asyncio.sleep(0.3)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        pass

                await asyncio.sleep(random.uniform(0.1, 0.2))
                return True

            step_name_insert = f"insert_text_{scene_number}" if not safe_speaker else f"insert_text_{scene_number}_{safe_speaker}"
            ok_insert = await self.perform_step(step_name_insert, _insert_text, critical=True)
            if not ok_insert:
                self._emit_notice(f"❌ scene_check_failed: scene={scene_number}")
                self._emit_step({"type": "finish_scene", "scene": scene_number, "ok": False})
                return False
            if self.verify_scene_after_insert:
                pass
            self._emit_notice(f"✅ scene_done: scene={scene_number}")
            self._emit_step({"type": "finish_scene", "scene": scene_number, "ok": True})
            return True
            
        except asyncio.CancelledError:
            raise
        except Exception as e:
            try:
                self._last_error = str(e)
            except Exception:
                pass
            self._emit_notice(f"❌ scene_error: scene={scene_number} err={e}")
            self._emit_step({"type": "finish_scene", "scene": scene_number, "ok": False})
            msg = str(e)
            if "Target page, context or browser has been closed" in msg or "has been closed" in msg:
                raise
            return False

    # Поиск по бейджу сцены отключен по запросу
    
    async def delete_empty_scenes(self, page: Page, filled_scenes_count: int, max_scenes: int = 15):
        """
        Удалить все пустые сцены после заполненных
        
        Args:
            page: Playwright страница
            filled_scenes_count: Количество заполненных сцен
            max_scenes: Максимальное количество сцен в шаблоне
        """
        empty_scenes = list(range(filled_scenes_count + 1, max_scenes + 1))
        
        if not empty_scenes:
            print("✅ Все сцены заполнены, удаление не требуется")
            return
        
        print(f"\n🗑️  Удаляю пустые сцены: {empty_scenes}")
        await self._await_gate()
        try:
            await page.wait_for_selector('span[data-node-view-content-react]', timeout=self.validation_ready_timeout_ms)
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(self.post_reload_wait)
        
        for scene_num in empty_scenes:
            await self._await_gate()
            try:
                text_label = f"text_{scene_num}"
                print(f"  🗑️  Удаляю сцену {scene_num}: {text_label}")
                
                # Находим span с текстом text_X
                span_locator = page.locator(f'span[data-node-view-content-react]:has-text("{text_label}")')
                
                # Проверяем существование
                count = await span_locator.count()
                if count == 0:
                    print(f"  ⚠️  Сцена {text_label} не найдена, пропускаю")
                    continue
                
                # Кликаем на span, чтобы выделить сцену (устойчиво)
                await span_locator.first.scroll_into_view_if_needed()
                try:
                    await page.keyboard.press('Escape')
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass
                try:
                    await span_locator.first.click(timeout=3000)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    try:
                        await span_locator.first.click(timeout=3000, force=True)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        box = await span_locator.first.bounding_box()
                        if box:
                            await page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
                await asyncio.sleep(random.uniform(0.3, 0.5))
                
                # Ищем кнопку с тремя точками (more-level)
                more_button = page.locator('button:has(iconpark-icon[name="more-level"])')
                
                # Проверяем существование кнопки
                button_count = await more_button.count()
                if button_count == 0:
                    print(f"  ⚠️  Кнопка меню не найдена для {text_label}")
                    continue
                
                # Кликаем на кнопку с тремя точками (берем последнюю видимую)
                try:
                    await more_button.last.click()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    await more_button.first.click(force=True)
                await asyncio.sleep(random.uniform(0.3, 0.5))
                
                # Ждем появления меню и ищем пункт
                delete_item = page.locator('div[role="menuitem"]').filter(has_text=re.compile(r'Удалить сцену|Delete scene'))
                try:
                    await delete_item.first.wait_for(state='visible', timeout=2000)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass
                
                # Проверяем существование пункта меню
                delete_count = await delete_item.count()
                if delete_count == 0:
                    print(f"  ⚠️  Пункт 'Удалить сцену' не найден")
                    continue
                
                # Кликаем на "Удалить сцену"
                try:
                    await delete_item.first.click()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    await delete_item.first.click(force=True)
                await asyncio.sleep(random.uniform(0.5, 0.8))
                
                print(f"  ✅ Сцена {scene_num} удалена")
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"  ❌ Ошибка при удалении сцены {scene_num}: {e}")
                continue
        
        print("✅ Удаление пустых сцен завершено")
    
    async def click_generate_button(self, page: Page):
        """
        Нажать кнопку "Сгенерировать"
        
        Args:
            page: Playwright страница
        """
        print("\n🔘 Нажимаю кнопку 'Сгенерировать'...")
        await self._await_gate()
        
        try:
            strategy = str(self.config.get('generate_button_selector_strategy', 'text')).lower()
            names_raw = str(self.config.get('generate_button_name', 'Сгенерировать|Generate'))
            names = [n.strip() for n in names_raw.split('|') if n.strip()]
            custom_sel = str(self.config.get('generate_button_selector_custom', '') or '')
            icon_name = str(self.config.get('generate_button_icon_name', '') or '')
            button = None
            if strategy == 'role':
                for n in names:
                    try:
                        btn_candidate = page.get_by_role('button', name=n)
                        if await btn_candidate.count() > 0:
                            button = btn_candidate
                            break
                    except Exception:
                        continue
            elif strategy == 'icon' and icon_name:
                try:
                    ico = page.locator(f'iconpark-icon[name="{icon_name}"]')
                    if await ico.count() > 0:
                        button = ico.first.locator('xpath=ancestor::button[1]')
                except Exception:
                    button = None
            elif strategy == 'custom' and custom_sel:
                try:
                    button = page.locator(custom_sel)
                except Exception:
                    button = None
            # Fallbacks: text search then generic button text
            if button is None:
                # Ищем кнопку по тексту
                pattern = '|'.join([re.escape(n) for n in names]) if names else r'Сгенерировать|Generate'
                button = page.locator('button').filter(has_text=re.compile(pattern))
            
            # Проверяем существование
            count = await button.count()
            if count == 0:
                print("❌ Кнопка 'Сгенерировать' не найдена")
                return False
            
            # Скроллим к кнопке
            await self._await_gate()
            await button.scroll_into_view_if_needed()
            await asyncio.sleep(random.uniform(0.3, 0.5))
            
            # Кликаем
            await self._await_gate()
            await button.click()
            try:
                s_over = (self.config.get('step_overrides') or {}).get('click_generate_button') or {}
                extra_delay = float(s_over.get('delay_sec', 0))
                if extra_delay > 0:
                    await self._await_gate()
                    await asyncio.sleep(extra_delay)
            except Exception:
                pass
            print("✅ Кнопка 'Сгенерировать' нажата")
            await self._await_gate()
            await asyncio.sleep(random.uniform(1.0, 2.0))
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка при нажатии кнопки: {e}")
            return False
    
    async def fill_and_submit_final_window(self, page: Page, title: str):
        """
        Заполнить название видео и нажать "Отправить" в финальном окне
        
        Args:
            page: Playwright страница
            title: Название видео
        """
        print(f"\n📝 Заполняю финальное окно с названием: {title}")
        await self._await_gate()
        
        try:
            # Ждем появления попап окна с заголовком "Сгенерировать видео"
            print("  ⏳ Жду появления окна генерации...")
            await page.wait_for_selector('div:has-text("Сгенерировать видео")', timeout=10000)
            await self._await_gate()
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # Находим поле ввода по placeholder
            input_field = page.locator('input[placeholder="Без названия — видео"]')
            
            # Проверяем существование
            count = await input_field.count()
            if count == 0:
                print("  ❌ Поле ввода названия не найдено")
                return False
            
            # В попапе может быть несколько таких полей, берем последний (в попапе)
            print(f"  ✏️  Ввожу название: {title}")
            
            # Кликаем на поле
            await self._await_gate()
            await input_field.last.click()
            await asyncio.sleep(random.uniform(0.2, 0.3))
            
            # Очищаем поле
            await self._await_gate()
            await page.keyboard.press('Meta+A')
            await asyncio.sleep(0.1)
            await page.keyboard.press('Backspace')
            await asyncio.sleep(random.uniform(0.1, 0.2))
            
            # Вводим название
            await self._await_gate()
            await page.keyboard.insert_text(title)
            await asyncio.sleep(random.uniform(0.3, 0.5))
            
            print("  ✅ Название введено")
            
            # Находим кнопку "Отправить" в попапе
            submit_button = page.locator('button').filter(has_text=re.compile(r'Отправить|Submit', re.I))
            
            # Проверяем существование
            button_count = await submit_button.count()
            if button_count == 0:
                print("  ❌ Кнопка 'Отправить' не найдена")
                return False
            
            print("  🚀 Нажимаю кнопку 'Отправить'...")
            
            # Кликаем на кнопку
            await self._await_gate()
            await submit_button.last.click()
            
            print("  ✅ Видео отправлено на генерацию!")
            print("  ⏳ Жду редиректа на страницу проектов...")
            
            # Ждем редиректа на страницу projects
            try:
                await page.wait_for_url("**/projects**", timeout=self.generation_redirect_timeout_ms)
                print("  ✅ Редирект выполнен, видео в процессе генерации!")
                await self._await_gate()
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"  ⚠️ Таймаут ожидания редиректа, но продолжаю: {e}")
                await self._await_gate()
                await asyncio.sleep(3)
            
            return True
            
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"  ❌ Ошибка при заполнении финального окна: {e}")
            return False
    
    @step("open_browser")
    async def open_browser(self) -> bool:
        """
        Открыть браузер и сохранить его в self.browser и self.playwright.
        
        Returns:
            True если браузер успешно открыт
        """
        if self.browser is not None:
            try:
                # Check if browser is still connected
                if self.playwright_context and self.playwright_context.pages:
                    # Ping functionality or just assume true if pages exist
                    return True
                if self.browser.is_connected():
                    return True
            except Exception:
                # If connection check failed, reset and try to launch again
                print("⚠️ Browser connection lost, restarting...")
                self.browser = None
                self.playwright_context = None
                self.page = None

        try:
            p = await async_playwright().start()
            self.playwright = p
            
            print("\n🌐 Подключаюсь к браузеру через CDP...")
            browser_mode = (self.config.get('browser') or 'chrome').lower()
            chrome_cdp_url = self.config.get('chrome_cdp_url') or 'http://localhost:9222'
            multilogin_cdp_url = self.config.get('multilogin_cdp_url')
            profiles = self.config.get('profiles') or {}
            profile_to_use = (self.config.get('profile_to_use') or '').strip()
            force_embedded = bool(self.config.get('force_embedded_browser', False))
            self._debug_keep_open = bool(self.config.get('debug_keep_browser_open_on_error', False))

            if profile_to_use.lower() == 'ask' or not profile_to_use:
                if 'chrome_automation' in profiles:
                    profile_to_use = 'chrome_automation'
                elif profiles:
                    profile_to_use = list(profiles.keys())[0]
                else:
                    profile_to_use = 'chrome_automation'
                print(f"⚠️ Профиль был 'ask' или пуст, переключился на: {profile_to_use}")

            if not force_embedded and browser_mode == 'multilogin':
                if not multilogin_cdp_url:
                    print("❌ Не задан 'multilogin_cdp_url' в config.json")
                    raise RuntimeError("multilogin_cdp_url missing")
                browser = await p.chromium.connect_over_cdp(multilogin_cdp_url)
                print("✅ Подключился к Multilogin по CDP!")
            elif not force_embedded:
                chosen_cdp = chrome_cdp_url
                profile_path = str(self.config.get('chrome_profile_path', '~/chrome_automation'))

                if profiles and profile_to_use and profile_to_use in profiles:
                    pconf = profiles[profile_to_use] or {}
                    if pconf.get('cdp_url'):
                        chosen_cdp = pconf['cdp_url']
                    if pconf.get('profile_path'):
                        profile_path = pconf['profile_path']
                    print(f"✅ Выбран профиль Chrome: {profile_to_use} ({chosen_cdp})")

                abs_profile_path = os.path.abspath(os.path.expanduser(profile_path))
                os.makedirs(abs_profile_path, exist_ok=True)
                
                # Cleanup SingletonLock to avoid crashes if previous session died
                lock_file = os.path.join(abs_profile_path, "SingletonLock")
                if os.path.exists(lock_file):
                    try:
                        os.remove(lock_file)
                        print(f"🧹 Removed stale SingletonLock: {lock_file}")
                    except Exception as e:
                        print(f"⚠️ Failed to remove SingletonLock: {e}")

                print("🚀 Запускаю Chrome с постоянным профилем...")
                
                # Определяем путь к Chrome в зависимости от ОС
                chrome_path = ""
                if sys.platform == "darwin": # macOS
                    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
                elif sys.platform == "win32": # Windows
                    chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe"
                
                # Проверяем тип браузера в профиле
                pconf = profiles.get(profile_to_use, {})
                browser_type = pconf.get('browser_type', 'chrome') # default to chrome if not specified

                # Parse port from chosen_cdp (e.g., http://localhost:9222 -> 9222)
                cdp_port = 9222
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(chosen_cdp)
                    if parsed.port:
                        cdp_port = parsed.port
                except Exception:
                    pass

                # Try to connect first if browser might be running
                try:
                    print(f"🔄 Trying to connect to existing browser at {chosen_cdp}...")
                    browser = await p.chromium.connect_over_cdp(chosen_cdp)
                    if browser.contexts:
                        print(f"✅ Connected to existing browser at {chosen_cdp}")
                        self.browser = browser
                        self.playwright_context = browser.contexts[0]
                        # Don't return yet, let it flow to page creation if needed
                    else:
                        print("⚠️ Connected but no contexts found.")
                except Exception:
                    print("ℹ️ No existing browser found, launching new one...")

                if not self.browser:
                    launch_kwargs = {
                        "user_data_dir": abs_profile_path,
                        "headless": False,
                        "viewport": {"width": 1280, "height": 800}, # Use fixed viewport as requested
                        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "ignore_https_errors": True,
                        "locale": "ru-RU",  # Force Russian locale
                        "args": [
                            "--disable-blink-features=AutomationControlled",
                            "--no-sandbox",
                            "--ignore-certificate-errors",
                            "--ignore-ssl-errors",
                            "--allow-insecure-localhost",
                            "--disable-web-security",
                            "--enable-webgl",
                            "--enable-accelerated-2d-canvas",
                            "--ignore-gpu-blocklist",
                            "--enable-gpu-rasterization",
                            "--enable-zero-copy",
                            "--disable-gpu-driver-bug-workarounds",
                            "--no-default-browser-check",
                            "--no-first-run",
                            "--lang=ru-RU", # Force UI language
                            f"--remote-debugging-port={cdp_port}",
                        ]
                    }

                    if browser_type == 'chromium':
                        print(f"ℹ️ Профиль {profile_to_use} использует Chromium (bundled)")
                    else:
                        # Для 'chrome' пытаемся найти системный
                        if os.path.exists(chrome_path):
                            print(f"🚀 Found System Chrome: {chrome_path}")
                            launch_kwargs["executable_path"] = chrome_path
                        else:
                            print(f"⚠️ System Chrome not found at {chrome_path}. Trying 'channel=chrome'...")
                            launch_kwargs["channel"] = "chrome"

                    try:
                        browser = await p.chromium.launch_persistent_context(**launch_kwargs)
                        print(f"✅ Браузер запущен с профилем: {profile_to_use} на порту {cdp_port}")
                        
                        # Stealth init script
                        try:
                            await browser.add_init_script("""
                                Object.defineProperty(navigator, 'webdriver', {
                                    get: () => undefined
                                });
                            """)
                            print("🕵️ Stealth script injected")
                        except Exception as e:
                            print(f"⚠️ Failed to inject stealth script: {e}")

                    except Exception as e:
                        print(f"❌ Ошибка запуска браузера: {e}")
                        print("⚠️ Пробую fallback на bundled Chromium...")
                        # Fallback: remove executable_path/channel and try again
                        launch_kwargs.pop("executable_path", None)
                        launch_kwargs.pop("channel", None)
                        browser = await p.chromium.launch_persistent_context(**launch_kwargs)
                        print(f"✅ Fallback: Chromium запущен с профилем: {profile_to_use}")
            else:
                auth_state_path = "debug/auth_state.json"
                launch_args = [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--ignore-certificate-errors",
                    "--ignore-ssl-errors",
                    "--allow-insecure-localhost",
                    "--disable-web-security"
                ]
                browser = await p.chromium.launch(
                    headless=False,
                    args=launch_args
                )
                print("✅ Запущен встроенный Chromium (force_embedded_browser)!")

            contexts = browser.contexts
            if not contexts:
                auth_state_path = "debug/auth_state.json"
                context_options = {
                    "viewport": {"width": 1280, "height": 800},
                    "ignore_https_errors": True
                }

                if os.path.exists(auth_state_path):
                    print(f"📂 Загружаю состояние авторизации из {auth_state_path}")
                    context_options["storage_state"] = auth_state_path
                else:
                    print("⚠️ Файл авторизации не найден, запускаю чистую сессию")

                context = await browser.new_context(**context_options)

                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """)
            else:
                context = contexts[0]

            if not context.pages:
                page = await context.new_page()
            else:
                page = context.pages[0]

            try:
                page.set_default_timeout(float(self.config.get('playwright_timeout_ms', 5000)))
            except Exception:
                pass
            
            self.browser = browser
            self._page = page
            return True
        except Exception as e:
            logger.error(f"[open_browser] failed: {e}")
            return False

    async def process_episode_part(self, episode_id: str, part_idx: int):
        """
        Обработать одну часть эпизода
        
        Args:
            episode_id: ID эпизода
            part_idx: Номер части
        """
        self._current_episode_id = episode_id
        self._current_part_idx = int(part_idx)
        # Получаем данные
        template_url, scenes = self.get_episode_data(episode_id, part_idx)
        
        if template_url is None or (isinstance(template_url, str) and template_url.strip() == "") or not scenes:
            try:
                self.task_status = TaskStatus(task_id=f"{episode_id}:{part_idx}")
                self.task_status.global_status = "failed"
            except Exception:
                pass
            try:
                self._last_error = "no_data_for_processing"
            except Exception:
                pass
            try:
                logger.error("[process_episode_part] failed: no data for processing")
            except Exception:
                pass
            return False
        
        # Инициализация TaskStatus и метрик
        try:
            total_scenes = len(scenes or [])
            total_brolls = sum(1 for s in (scenes or []) if str(s.get("brolls", "")).strip())
        except Exception:
            total_scenes = 0
            total_brolls = 0
        self.task_status = TaskStatus(
            task_id=f"{episode_id}:{part_idx}",
            metrics=Metrics(scenes_total=total_scenes, brolls_total=total_brolls),
        )
        if self.task_status:
            self.task_status.global_status = "running"

        p = None
        page = None
        try:
            async def _init_session():
                nonlocal p, page
                # Используем существующий браузер, если он есть
                if self.browser is not None and self.playwright is not None:
                    p = self.playwright
                    browser = self.browser
                    contexts = browser.contexts
                    if not contexts:
                        auth_state_path = "debug/auth_state.json"
                        context_options = {
                            "viewport": {"width": 1280, "height": 800},
                            "ignore_https_errors": True
                        }
                        if os.path.exists(auth_state_path):
                            context_options["storage_state"] = auth_state_path
                        context = await browser.new_context(**context_options)
                        await context.add_init_script("""
                            Object.defineProperty(navigator, 'webdriver', {
                                get: () => undefined
                            });
                        """)
                    else:
                        context = contexts[0]
                    if not context.pages:
                        page = await context.new_page()
                    else:
                        page = context.pages[0]
                    try:
                        page.set_default_timeout(float(self.config.get('playwright_timeout_ms', 5000)))
                    except Exception:
                        pass
                    self._page = page
                    return True
                
                p = await async_playwright().start()
                print("\n🌐 Подключаюсь к браузеру через CDP...")
                browser_mode = (self.config.get('browser') or 'chrome').lower()
                chrome_cdp_url = self.config.get('chrome_cdp_url') or 'http://localhost:9222'
                multilogin_cdp_url = self.config.get('multilogin_cdp_url')
                profiles = self.config.get('profiles') or {}
                profile_to_use = (self.config.get('profile_to_use') or '').strip()
                force_embedded = bool(self.config.get('force_embedded_browser', False))
                self._debug_keep_open = bool(self.config.get('debug_keep_browser_open_on_error', False))

                if profile_to_use.lower() == 'ask' or not profile_to_use:
                    if 'chrome_automation' in profiles:
                        profile_to_use = 'chrome_automation'
                    elif profiles:
                        profile_to_use = list(profiles.keys())[0]
                    else:
                        profile_to_use = 'chrome_automation'
                    print(f"⚠️ Профиль был 'ask' или пуст, переключился на: {profile_to_use}")

                if not force_embedded and browser_mode == 'multilogin':
                    if not multilogin_cdp_url:
                        print("❌ Не задан 'multilogin_cdp_url' в config.json")
                        raise RuntimeError("multilogin_cdp_url missing")
                    browser = await p.chromium.connect_over_cdp(multilogin_cdp_url)
                    print("✅ Подключился к Multilogin по CDP!")
                elif not force_embedded:
                    chosen_cdp = chrome_cdp_url
                    profile_path = str(self.config.get('chrome_profile_path', '~/chrome_automation'))

                    if profiles and profile_to_use and profile_to_use in profiles:
                        pconf = profiles[profile_to_use] or {}
                        if pconf.get('cdp_url'):
                            chosen_cdp = pconf['cdp_url']
                        if pconf.get('profile_path'):
                            profile_path = pconf['profile_path']
                        print(f"✅ Выбран профиль Chrome: {profile_to_use} ({chosen_cdp})")

                    abs_profile_path = os.path.expanduser(profile_path)
                    os.makedirs(abs_profile_path, exist_ok=True)

                    try:
                        print(f"🔄 Попытка подключения к {chosen_cdp}...")
                        browser = await p.chromium.connect_over_cdp(chosen_cdp)
                        print("✅ Подключился к Chrome через CDP!")
                    except Exception:
                        print(f"⚠️ Не удалось подключиться к {chosen_cdp}.")
                        print("🚀 Запускаю встроенный Chromium с сохраненным состоянием...")

                        auth_state_path = "debug/auth_state.json"
                        launch_args = [
                            "--disable-blink-features=AutomationControlled",
                            "--no-sandbox",
                            "--ignore-certificate-errors",
                            "--ignore-ssl-errors",
                            "--allow-insecure-localhost",
                            "--disable-web-security"
                        ]

                        browser = await p.chromium.launch(
                            headless=False,
                            args=launch_args
                        )
                        print("✅ Запущен встроенный Chromium!")
                else:
                    auth_state_path = "debug/auth_state.json"
                    launch_args = [
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--ignore-certificate-errors",
                        "--ignore-ssl-errors",
                        "--allow-insecure-localhost",
                        "--disable-web-security"
                    ]
                    browser = await p.chromium.launch(
                        headless=False,
                        args=launch_args
                    )
                    print("✅ Запущен встроенный Chromium (force_embedded_browser)!")

                contexts = browser.contexts
                if not contexts:
                    auth_state_path = "debug/auth_state.json"
                    context_options = {
                        "viewport": {"width": 1280, "height": 800},
                        "ignore_https_errors": True
                    }

                    if os.path.exists(auth_state_path):
                        print(f"📂 Загружаю состояние авторизации из {auth_state_path}")
                        context_options["storage_state"] = auth_state_path
                    else:
                        print("⚠️ Файл авторизации не найден, запускаю чистую сессию")

                    context = await browser.new_context(**context_options)

                    await context.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });
                    """)
                else:
                    context = contexts[0]

                if not context.pages:
                    page = await context.new_page()
                else:
                    page = context.pages[0]

                try:
                    page.set_default_timeout(float(self.config.get('playwright_timeout_ms', 5000)))
                except Exception:
                    pass
                self._page = page
                return True

            await self.perform_step("authorize_session", _init_session, critical=True)

            wf_steps = self.config.get("workflow_steps") or []
            if isinstance(wf_steps, list) and len(wf_steps) > 0:
                ok = await self._run_workflow(page, template_url, scenes, episode_id, part_idx, wf_steps)
                return bool(ok)
            
            # Переходим на страницу шаблона
            print(f"📄 Открываю шаблон: {template_url}")
            async def _open_template():
                # Reuse existing page if available
                if page:
                    await page.goto(template_url, wait_until='domcontentloaded', timeout=120000)
                else:
                    # Should not happen if _init_session succeeded
                    raise RuntimeError("No page available for navigation")
                return True

            await self.perform_step("open_template", _open_template, critical=True)
            
            # Ждем загрузки страницы и появления первого поля text_1
            print("⏳ Жду загрузки страницы и элементов...")
            try:
                # Ждем появления первого текстового поля (до 30 секунд)
                await page.wait_for_selector('span[data-node-view-content-react]', timeout=30000)
                print("✅ Элементы загрузились!")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"⚠️ Timeout при ожидании элементов, но продолжаю: {e}")
            
            # Дополнительная пауза для стабильности
            await asyncio.sleep(self.pre_fill_wait)

            part_title = ""
            try:
                part_title = str((scenes[0] or {}).get("title") or "")
            except Exception:
                part_title = ""
            async def _set_title():
                return await self._apply_part_title(page, part_title)
            await self.perform_step("set_part_title", _set_title, critical=False)
            
            # Заполняем сцены
            self.report = {
                'validation_missing': [],
                'broll_skipped': [],
                'broll_no_results': [],
                'broll_errors': [],
                'manual_intervention': []
            }
            print(f"\n📝 Начинаю заполнение {len(scenes)} сцен...")
            success_count = 0
            
            for idx, scene in enumerate(scenes, 1):
                await self._await_gate()
                async def _fill_one():
                    return await self.fill_scene(page, scene['scene_idx'], scene['text'], scene.get('speaker'))
                safe_sp = self._normalize_speaker_key(scene.get('speaker'))
                step_name = f"fill_scene_{scene['scene_idx']}" if not safe_sp else f"fill_scene_{scene['scene_idx']}_{safe_sp}"
                success = await self.perform_step(step_name, _fill_one, critical=True)
                if success:
                    success_count += 1
                    try:
                        if self.task_status:
                            self.task_status.metrics.scenes_completed += 1
                    except Exception:
                        pass
                    # Обработка B-rolls, если заданы в CSV
                    if str(scene.get('brolls', '')).strip():
                        try:
                            await self._await_gate()
                            async def _broll_one():
                                return await self.handle_broll_for_scene(page, scene['scene_idx'], str(scene['brolls']).strip())
                            ok_b = await self.perform_step(f"handle_broll_{scene['scene_idx']}", _broll_one, critical=False)
                            if ok_b:
                                try:
                                    if self.task_status:
                                        self.task_status.metrics.brolls_inserted += 1
                                except Exception:
                                    pass
                        except asyncio.CancelledError:
                            raise
                        except Exception as e:
                            print(f"⚠️ Ошибка обработки brolls для сцены {scene['scene_idx']}: {e}")
                            if self.report is not None:
                                self.report['broll_errors'].append({'scene_idx': scene['scene_idx'], 'error': str(e)})
                # Пауза между сценами
                if idx < len(scenes):
                    await self._await_gate()
                    await asyncio.sleep(self.delay_between_scenes)
            
            print(f"\n📊 Заполнено сцен: {success_count}/{len(scenes)}")

            final_validation = None
            for attempt in range(1, 4):
                try:
                    if self.report is not None:
                        self.report['validation_missing'] = []
                except Exception:
                    pass
                final_validation = await self.refresh_and_validate(page, scenes, interactive=False)
                if not final_validation.get('ok', True):
                    print(f"⚠️ Несоответствия после проверки {attempt}/3")
                await self.delete_empty_scenes(page, len(scenes), max_scenes=self.max_scenes)
                missing = final_validation.get('missing') or []
                if not missing:
                    break
                await asyncio.sleep(self.pre_fill_wait)

            self.print_final_report()
            final_missing = []
            try:
                if final_validation:
                    final_missing = final_validation.get('missing') or []
            except Exception:
                final_missing = []
            if final_missing:
                await self.notify('HeyGen', 'Несоответствия после 3 проверок — задача завершена без генерации')
                if self.task_status:
                    self.task_status.global_status = "failed"
                return False
            if self._should_block_generation():
                reason = self._block_generation_reason()
                await self.notify('HeyGen', f'Генерация заблокирована: {reason}')
                print("============================================================")
                print("Генерация заблокирована из-за пропусков/ошибок")
                if reason:
                    print(f"Причина: {reason}")
                print("============================================================")
                if self.task_status:
                    self.task_status.global_status = "failed"
                return False
            if not self._generation_enabled():
                async def _save_only():
                    await self.click_save_and_wait(page)
                    return True
                await self.perform_step("save_before_exit", _save_only, critical=False)
                print("⏭️ Генерация отключена — проект сохранён")
                if self.task_status:
                    self.task_status.global_status = "completed"
                return True
            # Нажимаем кнопку "Сгенерировать"
            await self.click_generate_button(page)
            
            # Заполняем финальное окно и отправляем
            title = scenes[0]['title']
            await self.fill_and_submit_final_window(page, title)
            
            # Вкладка автоматически закроется после обработки
            print(f"\n✅ Часть {part_idx} обработана и отправлена на генерацию!")
            if self.task_status:
                self.task_status.global_status = "completed"
            
            return True
        except asyncio.CancelledError:
            print("⛔ Задача отменена")
            raise
        except Exception as e:
            print(f"❌ Ошибка обработки части эпизода {episode_id} part={part_idx}: {e}")
            return False
        finally:
            self._current_episode_id = None
            self._current_part_idx = None

    def _wf_bool(self, v, default: bool = False) -> bool:
        if v is None:
            return default
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        if s in ("1", "true", "yes", "y", "on"):
            return True
        if s in ("0", "false", "no", "n", "off"):
            return False
        return default

    def _wf_float(self, v, default: float = 0.0) -> float:
        if v is None:
            return default
        if isinstance(v, (int, float)) and v == v:
            return float(v)
        s = str(v).strip()
        if not s:
            return default
        try:
            return float(s)
        except Exception:
            return default

    def _wf_int(self, v, default: int = 0) -> int:
        if v is None:
            return default
        if isinstance(v, bool):
            return default
        if isinstance(v, int):
            return v
        if isinstance(v, float) and v == v:
            return int(v)
        s = str(v).strip()
        if not s:
            return default
        try:
            return int(float(s))
        except Exception:
            return default

    def _wf_render(self, v, ctx: dict) -> str:
        s = str(v or "")
        if "{{" not in s:
            return s
        try:
            def _repl(m):
                k = str(m.group(1) or "").strip()
                if k in ctx:
                    return str(ctx.get(k) or "")
                return m.group(0)
            return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", _repl, s)
        except Exception:
            return s

    @step("execute_workflow_step")
    async def _execute_single_step(self, page: Page, raw: dict, ctx: dict, template_url: str, scenes: list, has_broll_step: bool) -> bool:
        step_type = str(raw.get("type") or "").strip()
        params = raw.get("params") if isinstance(raw.get("params"), dict) else {}
        try:
            if step_type in ("navigate_to_template", "navigate"):
                url = self._wf_render(params.get("url") or template_url, ctx).strip()
                wait_until = self._wf_render(params.get("wait_until") or "domcontentloaded", ctx).strip() or "domcontentloaded"
                timeout = self._wf_int(params.get("timeout_ms"), 120000)
                print(f"📄 Открываю: {url}")
                await page.goto(url, wait_until=wait_until, timeout=timeout)
                return True

            if step_type in ("wait_for", "wait_for_selector"):
                sel = self._wf_render(params.get("selector") or "", ctx).strip()
                if not sel:
                    return True
                timeout = self._wf_int(params.get("timeout_ms"), 30000)
                state = self._wf_render(params.get("state") or "visible", ctx).strip() or "visible"
                await page.wait_for_selector(sel, timeout=timeout, state=state)
                return True

            if step_type in ("wait", "sleep"):
                sec = self._wf_float(params.get("sec"), self.pre_fill_wait)
                await asyncio.sleep(sec)
                return True

            if step_type == "click":
                sel = self._wf_render(params.get("selector") or "", ctx).strip()
                if not sel:
                    return True
                timeout = self._wf_int(params.get("timeout_ms"), None)
                loc = page.locator(sel)
                which = self._wf_render(params.get("which") or "", ctx).strip().lower()
                if which == "last":
                    loc = loc.last
                elif which.isdigit():
                    loc = loc.nth(int(which))
                if timeout is None:
                    await loc.click()
                else:
                    await loc.click(timeout=timeout)
                return True

            if step_type == "fill":
                sel = self._wf_render(params.get("selector") or "", ctx).strip()
                text = self._wf_render(params.get("text") or "", ctx).replace("\\n", "\n")
                if not sel:
                    return True
                await page.locator(sel).fill(text)
                return True

            if step_type == "press":
                sel = self._wf_render(params.get("selector") or "", ctx).strip()
                key = self._wf_render(params.get("key") or "", ctx).strip()
                if not sel or not key:
                    return True
                await page.press(sel, key)
                return True

            if step_type in ("select_episode_parts", "select_parts_by_episode"):
                episode = self._wf_render(
                    params.get("episode")
                    or params.get("episode_name")
                    or params.get("episode_title")
                    or ctx.get("episode_id")
                    or "",
                    ctx,
                ).strip()
                title_selector = self._wf_render(params.get("title_selector") or "", ctx).strip()
                checkbox_selector = self._wf_render(params.get("checkbox_selector") or "", ctx).strip()
                button_selector = self._wf_render(
                    params.get("button_selector") or params.get("after_button_selector") or "", ctx
                ).strip()
                timeout = self._wf_int(params.get("timeout_ms"), 60000)
                hover_sec = self._wf_float(params.get("hover_sec"), 0.15)
                card_xpath = str(params.get("card_xpath") or "xpath=ancestor::div[1]").strip()

                if not episode or not title_selector or not checkbox_selector:
                    return True

                await page.wait_for_selector(title_selector, timeout=timeout)
                titles = page.locator(title_selector).filter(has_text=episode)
                cnt = await titles.count()
                if cnt <= 0:
                    return True

                for i in range(cnt):
                    tloc = titles.nth(i)
                    card = tloc
                    try:
                        if card_xpath:
                            card = tloc.locator(card_xpath)
                    except Exception:
                        card = tloc

                    try:
                        await card.hover(timeout=timeout)
                    except Exception:
                        pass
                    if hover_sec and hover_sec > 0:
                        await asyncio.sleep(hover_sec)

                    cb = None
                    try:
                        cb = card.locator(checkbox_selector)
                        if await cb.count() == 0:
                            cb = page.locator(checkbox_selector)
                    except Exception:
                        cb = page.locator(checkbox_selector)

                    try:
                        if cb is not None and await cb.count() > 0:
                            await cb.first.click(timeout=timeout)
                    except Exception:
                        try:
                            if cb is not None and await cb.count() > 0:
                                await cb.first.click(timeout=timeout, force=True)
                        except Exception:
                            pass

                if button_selector:
                    try:
                        await page.locator(button_selector).first.click(timeout=timeout)
                    except Exception:
                        try:
                            await page.locator(button_selector).first.click(timeout=timeout, force=True)
                        except Exception:
                            pass
                return True

            if step_type == "fill_scene":
                inline_broll = None
                if "handle_broll" in params:
                    inline_broll = self._wf_bool(params.get("handle_broll"), True)
                elif not has_broll_step:
                    inline_broll = True
                part_title = ""
                try:
                    part_title = str((scenes[0] or {}).get("title") or "")
                except Exception:
                    part_title = ""
                async def _set_title():
                    return await self._apply_part_title(page, part_title)
                await self.perform_step("set_part_title", _set_title, critical=False)
                print(f"\\n📝 Начинаю заполнение {len(scenes)} сцен...")
                success_count = 0
                for idx, scene in enumerate(scenes, 1):
                    try:
                        async def _fill_one():
                            return await self.fill_scene(page, scene['scene_idx'], scene['text'], scene.get('speaker'))
                        safe_sp = self._normalize_speaker_key(scene.get('speaker'))
                        step_name = f"fill_scene_{scene['scene_idx']}" if not safe_sp else f"fill_scene_{scene['scene_idx']}_{safe_sp}"
                        ok = await self.perform_step(step_name, _fill_one, critical=True)
                    except Exception as e:
                        print(f"⚠️ Ошибка заполнения сцены {scene.get('scene_idx')}: {e}")
                        ok = False
                    if ok:
                        success_count += 1
                        try:
                            if self.task_status:
                                self.task_status.metrics.scenes_completed += 1
                        except Exception:
                            pass
                        if inline_broll and str(scene.get('brolls', '')).strip():
                            try:
                                async def _broll_one():
                                    return await self.handle_broll_for_scene(page, scene['scene_idx'], str(scene['brolls']).strip())
                                ok_b = await self.perform_step(f"handle_broll_{scene['scene_idx']}", _broll_one, critical=False)
                                if ok_b:
                                    try:
                                        if self.task_status:
                                            self.task_status.metrics.brolls_inserted += 1
                                    except Exception:
                                        pass
                            except Exception as e:
                                print(f"⚠️ Ошибка обработки brolls для сцены {scene.get('scene_idx')}: {e}")
                                if self.report is not None:
                                    self.report['broll_errors'].append({'scene_idx': scene.get('scene_idx'), 'error': str(e)})
                    if idx < len(scenes):
                        await asyncio.sleep(self.delay_between_scenes)
                print(f"\\n📊 Заполнено сцен: {success_count}/{len(scenes)}")
                return True

            if step_type == "handle_broll":
                for scene in scenes:
                    if str(scene.get('brolls', '')).strip():
                        try:
                            async def _broll_one():
                                return await self.handle_broll_for_scene(page, scene['scene_idx'], str(scene['brolls']).strip())
                            ok_b = await self.perform_step(f"handle_broll_{scene['scene_idx']}", _broll_one, critical=False)
                            if ok_b:
                                try:
                                    if self.task_status:
                                        self.task_status.metrics.brolls_inserted += 1
                                except Exception:
                                    pass
                        except Exception as e:
                            print(f"⚠️ Ошибка обработки brolls для сцены {scene.get('scene_idx')}: {e}")
                            if self.report is not None:
                                self.report['broll_errors'].append({'scene_idx': scene.get('scene_idx'), 'error': str(e)})
                return True

            if step_type == "delete_empty_scenes":
                max_scenes = self._wf_int(params.get("max_scenes"), self.max_scenes)
                await self.delete_empty_scenes(page, len(scenes), max_scenes=max_scenes)
                return True

            if step_type == "save":
                await self.click_save_and_wait(page)
                return True

            if step_type == "reload":
                wait_until = str(params.get("wait_until") or "domcontentloaded").strip() or "domcontentloaded"
                timeout = self._wf_int(params.get("timeout_ms"), self.reload_timeout_ms)
                await page.reload(wait_until=wait_until, timeout=timeout)
                sec = self._wf_float(params.get("post_wait_sec"), self.pre_fill_wait)
                if sec > 0:
                    await asyncio.sleep(sec)
                return True

            if step_type == "reload_and_validate":
                interactive = self._wf_bool(params.get("interactive"), False)
                validation = await self.refresh_and_validate(page, scenes, interactive=interactive)
                if not validation.get('ok', True):
                    print("⚠️ Проверка обнаружила несоответствия")
                return True

            if step_type == "confirm":
                if not self._generation_enabled():
                    return True
                return True

            if step_type == "generate":
                if not self._generation_enabled():
                    return True
                if self._should_block_generation():
                    reason = self._block_generation_reason()
                    await self.notify('HeyGen', f'Генерация заблокирована: {reason}')
                    print("============================================================")
                    print("Генерация заблокирована из-за пропусков/ошибок")
                    if reason:
                        print(f"Причина: {reason}")
                    print("============================================================")
                    if self.task_status:
                        self.task_status.global_status = "failed"
                    return False
                await self.click_generate_button(page)
                return True

            if step_type == "final_submit":
                if not self._generation_enabled():
                    return True
                if self._should_block_generation():
                    reason = self._block_generation_reason()
                    await self.notify('HeyGen', f'Генерация заблокирована: {reason}')
                    print("============================================================")
                    print("Генерация заблокирована из-за пропусков/ошибок")
                    if reason:
                        print(f"Причина: {reason}")
                    print("============================================================")
                    if self.task_status:
                        self.task_status.global_status = "failed"
                    return False
                await self.fill_and_submit_final_window(page, title)
                return True

            if step_type:
                print(f"⚠️ Неизвестный шаг воркфлоу: {step_type}")
            return True
        except Exception as e:
            print(f"❌ Ошибка шага воркфлоу: type={step_type} err={e}")
            return False

    @step("run_workflow")
    async def _run_workflow(self, page: Page, template_url: str, scenes: list, episode_id: str, part_idx: int, steps: list) -> bool:
        print(f"DEBUG: _run_workflow called with {len(steps)} steps")
        self.report = {
            'validation_missing': [],
            'broll_skipped': [],
            'broll_no_results': [],
            'broll_errors': [],
            'manual_intervention': []
        }
        has_broll_step = False
        try:
            for s in steps or []:
                if not isinstance(s, dict):
                    continue
                if "enabled" in s and not self._wf_bool(s.get("enabled"), True):
                    continue
                if str(s.get("type") or "").strip() == "handle_broll":
                    has_broll_step = True
                    break
        except Exception:
            has_broll_step = False
        title = ""
        try:
            title = str((scenes[0] or {}).get("title") or "")
        except Exception:
            title = ""
        ctx = {
            "episode_id": str(episode_id or ""),
            "part_idx": str(part_idx if part_idx is not None else ""),
            "template_url": str(template_url or ""),
            "title": str(title or ""),
            "scenes_count": str(len(scenes or [])),
        }

        for i, raw in enumerate(steps):
            print(f"DEBUG: Processing step {i}")
            if not isinstance(raw, dict):
                continue
            if "enabled" in raw and not self._wf_bool(raw.get("enabled"), True):
                continue
            ok = await self._execute_single_step(page, raw, ctx, template_url, scenes, has_broll_step)
            print(f"DEBUG: Step {i} result: {ok}")
            if not ok:
                return False

        if not self._generation_enabled():
            async def _save_only():
                await self.click_save_and_wait(page)
                return True
            await self.perform_step("save_before_exit", _save_only, critical=False)
            print(f"\n✅ Часть {part_idx} обработана и сохранена без генерации!")
            return True

        print(f"\n✅ Часть {part_idx} обработана и отправлена на генерацию!")
        return True

    async def confirm_before_generation(self) -> bool:
        return True

    async def _take_debug_screenshot(self, page: Page, name: str) -> str | None:
        try:
            ts = int(asyncio.get_event_loop().time() * 1000)
            safe_name = "".join(ch for ch in name if ch.isalnum() or ch in "_-")
            path = f"debug/screenshots/{safe_name}_{ts}.png"
            await page.screenshot(path=path, full_page=True)
            self._emit_notice(f"📸 screenshot: {path}")
            return path
        except Exception:
            return None

    async def _focus_canvas_for_validation(self, page: Page) -> bool:
        try:
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass

            wrapper = page.locator("#editorCanvasWrapper").first
            try:
                if await wrapper.count() > 0:
                    if await human_coordinate_click(page, wrapper):
                        return True
            except Exception:
                pass

            canvas = page.locator("canvas").first
            try:
                if await canvas.count() > 0:
                    return await human_coordinate_click(page, canvas)
            except Exception:
                pass
        except asyncio.CancelledError:
            raise
        except Exception:
            return False
        return False

    async def _detect_broll_state_after_canvas_click(self, page: Page) -> str:
        try:
            await asyncio.sleep(2.0)
            await self._focus_canvas_for_validation(page)
            await asyncio.sleep(0.2)

            ok_btn = page.get_by_role(
                "button",
                name=re.compile(
                    r"^(Detach from BG|Change BG|Detach|Change BG)$",
                    re.I,
                ),
            )
            set_as_bg_btn = page.get_by_role(
                "button",
                name=re.compile(
                    r"^(Set as BG|Set as Background|Set as background|Make background|"
                    r"Сделать фоном|Сделать фон|Установить как фон)$",
                    re.I,
                ),
            )
            set_as_bg_menu = page.get_by_role(
                "menuitem",
                name=re.compile(
                    r"(Set as BG|Set as Background|Set as background|Make background|"
                    r"Сделать фоном|Сделать фон|Установить как фон)",
                    re.I,
                ),
            )
            bg_color_btn = page.get_by_role(
                "button",
                name=re.compile(
                    r"^(BG\s*Color|BG\s*Colour|Цвет\s*BG|BG\s*Цвет)$",
                    re.I,
                ),
            )

            try:
                if await ok_btn.count() > 0 and await ok_btn.first.is_visible():
                    return "ok"
            except Exception:
                pass
            try:
                if await set_as_bg_btn.count() > 0 and await set_as_bg_btn.first.is_visible():
                    return "needs_set_bg"
            except Exception:
                pass
            try:
                if await set_as_bg_menu.count() > 0 and await set_as_bg_menu.first.is_visible():
                    return "needs_set_bg"
            except Exception:
                pass

            try:
                if await bg_color_btn.count() > 0 and await bg_color_btn.first.is_visible():
                    return "empty_canvas"
            except Exception:
                pass

            return "unknown"
        except asyncio.CancelledError:
            raise
        except Exception:
            return "unknown"

    async def _click_set_as_bg_if_present(self, page: Page) -> bool:
        set_as_bg_btn = page.get_by_role(
            "button",
            name=re.compile(
                r"^(Set as BG|Set as Background|Set as background|Make background|"
                r"Сделать фоном|Сделать фон|Установить как фон)$",
                re.I,
            ),
        ).first
        set_as_bg_menu = page.get_by_role(
            "menuitem",
            name=re.compile(
                r"(Set as BG|Set as Background|Set as background|Make background|"
                r"Сделать фоном|Сделать фон|Установить как фон)",
                re.I,
            ),
        ).first
        try:
            if await set_as_bg_btn.count() > 0:
                try:
                    await set_as_bg_btn.click(timeout=4000)
                    return True
                except Exception:
                    try:
                        await set_as_bg_btn.click(timeout=4000, force=True)
                        return True
                    except Exception:
                        return await human_coordinate_click(page, set_as_bg_btn)
        except Exception:
            pass
        try:
            if await set_as_bg_menu.count() > 0:
                try:
                    await set_as_bg_menu.click(timeout=4000)
                    return True
                except Exception:
                    try:
                        await set_as_bg_menu.click(timeout=4000, force=True)
                        return True
                    except Exception:
                        return await human_coordinate_click(page, set_as_bg_menu)
        except Exception:
            pass
        return False

    async def handle_broll_for_scene(self, page: Page, scene_idx: int, query: str) -> bool:
        self._emit_notice(f"🎞️ broll_start: scene={scene_idx} query={query}")
        self._emit_step({"type": "start_broll", "scene": scene_idx})
        if not query or str(query).strip() == '' or str(query).strip().lower() == 'nan':
            self._emit_notice("ℹ️ broll_skip_empty")
            if self.report is not None:
                self.report['broll_skipped'].append({'scene_idx': scene_idx})
            return True

        nano_prompt = parse_nano_banano_prompt(query)
        if nano_prompt:
            self._emit_notice("🧪 nano_banano_generate")
            settings = get_settings()
            out_dir = os.path.join(str(settings.local_storage_path or "./storage"), "nano_banano")
            try:
                text_label = f"text_{scene_idx}"
                span_locator = page.locator('span[data-node-view-content-react]').filter(
                    has_text=re.compile(rf'^\s*{re.escape(text_label)}\s*$')
                )
            except Exception:
                span_locator = None

            async def _select_scene_best_effort_for_nano():
                try:
                    if span_locator is None:
                        return
                    if await span_locator.count() > 0:
                        await span_locator.first.scroll_into_view_if_needed()
                        try:
                            await page.keyboard.press('Escape')
                        except Exception:
                            pass
                        await human_fast_center_click(page, span_locator.first)
                except Exception:
                    return

            last_validation_reason = ""

            for attempt in range(1, 4):
                await self._await_gate()
                await _select_scene_best_effort_for_nano()

                ok, err = await handle_nano_banano(
                    page,
                    nano_prompt,
                    scene_idx,
                    out_dir,
                    episode_id=str(self._current_episode_id or "episode"),
                    part_idx=int(self._current_part_idx or 0),
                    gate_callback=self._await_gate,
                )
                if not ok:
                    self._emit_notice(f"❌ nano_banano_error: {err}")
                    await self._take_error_screenshot(page, f"nano_banano_fail_{scene_idx}")
                    if self.report is not None:
                        self.report.setdefault("nano_banano_errors", []).append(
                            {"scene_idx": scene_idx, "prompt": nano_prompt, "error": str(err or "")}
                        )
                    self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": False})
                    return True

                state = await self._detect_broll_state_after_canvas_click(page)
                if state == "needs_set_bg":
                    self._emit_notice("⚠️ nano_banano_validate: needs_set_bg")
                    clicked_bg = await self._click_set_as_bg_if_present(page)
                    if clicked_bg:
                        state = await self._detect_broll_state_after_canvas_click(page)
                    if state == "needs_set_bg":
                        last_validation_reason = "set_as_bg_still_visible"
                    elif state == "empty_canvas":
                        last_validation_reason = "bg_color_visible_after_set_bg"
                    else:
                        last_validation_reason = ""
                elif state == "empty_canvas":
                    self._emit_notice("⚠️ nano_banano_validate: empty_canvas")
                    last_validation_reason = "bg_color_visible_after_insert"
                else:
                    last_validation_reason = ""

                if state in ["ok", "unknown"]:
                    self._emit_notice(f"✅ nano_banano_done: scene={scene_idx}")
                    await self._take_error_screenshot(page, f"nano_banano_done_{scene_idx}")
                    self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": True})
                    return True

                snap = await self._take_debug_screenshot(page, f"nano_banano_validate_fail_{scene_idx}_try{attempt}")
                if attempt < 3:
                    self._emit_notice(f"⚠️ nano_banano_retry_validation: {attempt}/3 reason={last_validation_reason}")
                    continue

                err_msg = f"валидация Nano Banana не прошла после 3 попыток: {last_validation_reason or 'unknown'}"
                self._emit_notice(f"❌ nano_banano_error: {err_msg}")
                if self.report is not None:
                    self.report.setdefault("nano_banano_errors", []).append(
                        {
                            "scene_idx": scene_idx,
                            "prompt": nano_prompt,
                            "error": err_msg,
                            "attempt": attempt,
                            "reason": last_validation_reason or "unknown",
                            "screenshot": snap or "",
                        }
                    )
                self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": False})
                return True
            return True

        try:
            text_label = f"text_{scene_idx}"
            span_locator = page.locator('span[data-node-view-content-react]').filter(
                has_text=re.compile(rf'^\s*{re.escape(text_label)}\s*$')
            )
        except Exception:
            span_locator = None

        async def _select_scene_best_effort():
            try:
                if span_locator is None:
                    return
                if await span_locator.count() > 0:
                    await span_locator.first.scroll_into_view_if_needed()
                    try:
                        await page.keyboard.press('Escape')
                    except Exception:
                        pass
                    await human_fast_center_click(page, span_locator.first)
            except Exception:
                return

        last_validation_reason = ""

        for attempt in range(1, 4):
            await self._await_gate()
            await _select_scene_best_effort()
            try:
                await prepare_canvas_for_broll(page)
            except Exception:
                pass

            if not await self._open_media_panel(page):
                err = "не удалось открыть панель Медиа"
                self._emit_notice(f"❌ broll_error: {err}")
                await self._take_error_screenshot(page, f"broll_panel_fail_{scene_idx}")
                if self.report is not None:
                    self.report['broll_errors'].append({'scene_idx': scene_idx, 'query': query, 'error': err})
                if self.enable_notifications:
                    await self.notify('HeyGen', f'B-roll: {err} (scene {scene_idx})')
                self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": False})
                return False

            await self._broll_pause(0.2)

            if not await self._select_video_tab(page):
                err = "вкладка Видео/Video не найдена"
                self._emit_notice(f"❌ broll_error: {err}")
                await self._take_error_screenshot(page, f"broll_tab_fail_{scene_idx}")
                if self.report is not None:
                    self.report['broll_errors'].append({'scene_idx': scene_idx, 'query': query, 'error': err})
                if self.enable_notifications:
                    await self.notify('HeyGen', f'B-roll: {err} (scene {scene_idx})')
                self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": False})
                return False
            await self._broll_pause(0.2)

            async def _gate():
                await self._await_gate()
            
            if self.media_source not in ['all', 'все', '']:
                self._emit_notice(f"📂 broll_source: {self.media_source}")
                ok_source = await select_media_source(page, self.media_source, gate_callback=_gate)
                if not ok_source:
                    self._emit_notice(f"⚠️ не удалось выбрать источник: {self.media_source}")

            choice = self.orientation_choice or 'Горизонтальная'
            self._emit_notice(f"📐 broll_orientation: {choice}")
            ok_orient = await select_orientation(page, choice, gate_callback=_gate)
            if not ok_orient:
                self._emit_notice(f"⚠️ не удалось выбрать ориентацию: {choice}")

            await self._broll_pause(0.2)

            self._emit_notice("🔎 broll_search")

            current_query = str(query).strip()
            found = False

            while True:
                await self._await_gate()

                search_input = await self._locate_broll_search_input(page)
                if search_input is None:
                    err = "поле поиска B-roll не найдено"
                    self._emit_notice(f"❌ broll_error: {err}")
                    await self._take_error_screenshot(page, f"broll_search_input_fail_{scene_idx}")
                    if self.report is not None:
                        self.report['broll_errors'].append({'scene_idx': scene_idx, 'query': current_query, 'error': err})
                    if self.enable_notifications:
                        await self.notify('HeyGen', f'B-roll: {err} (scene {scene_idx})')
                    self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": False})
                    return False

                try:
                    await search_input.scroll_into_view_if_needed()
                except Exception:
                    pass
                try:
                    await search_input.click(timeout=3000)
                except Exception:
                    try:
                        await search_input.click(timeout=3000, force=True)
                    except Exception:
                        pass

                await self._await_gate()
                try:
                    await page.keyboard.press('Meta+A')
                    await page.keyboard.press('Backspace')
                    await page.keyboard.insert_text(current_query)
                    await page.keyboard.press('Enter')
                except Exception as e:
                    err = f"не удалось ввести запрос B-roll: {e}"
                    self._emit_notice(f"❌ broll_error: {err}")
                    await self._take_error_screenshot(page, f"broll_search_type_fail_{scene_idx}")
                    if self.report is not None:
                        self.report['broll_errors'].append({'scene_idx': scene_idx, 'query': current_query, 'error': err})
                    self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": False})
                    return False

                await page.wait_for_timeout(3000)

                try:
                    media_header = page.get_by_role(
                        "heading",
                        level=2,
                        name=re.compile(r"^\s*(Медиа|Media)\s*$", re.I),
                    )
                    media_panel = page.locator("aside, section, div").filter(has=media_header).first
                    active_panel = media_panel.locator('[role="tabpanel"][data-state="active"]').first
                    try:
                        if await active_panel.count() == 0:
                            active_panel = media_panel
                    except Exception:
                        active_panel = media_panel

                    no_data = active_panel.locator('div:not(.tw-hidden)').filter(
                        has_text=re.compile(r"\b(No\s+data|No\s+results\s+found)\b", re.I)
                    )
                    has_no_data = await no_data.count() > 0
                except Exception:
                    has_no_data = False

                if has_no_data:
                    words = current_query.split()
                    if len(words) > 1:
                        current_query = ' '.join(words[:-1])
                        self._emit_notice(f"⚠️ broll_retry: сокращаю запрос до '{current_query}'")
                        continue
                    break

                try:
                    imgs = active_panel.locator('div:not(.tw-hidden) .tw-grid-cols-2 img')
                except Exception:
                    imgs = page.locator('div:not(.tw-hidden) .tw-grid-cols-2 img')
                try:
                    await imgs.first.wait_for(state='attached', timeout=20000)
                    first_img = None
                    vs = None
                    try:
                        vs = page.viewport_size
                    except Exception:
                        vs = None
                    if vs and vs.get("width"):
                        vw = float(vs["width"])
                    else:
                        try:
                            vw = float(await page.evaluate("() => window.innerWidth"))
                        except Exception:
                            vw = 0.0
                    try:
                        cnt = await imgs.count()
                    except Exception:
                        cnt = 0
                    for i in range(min(cnt, 60)):
                        cand = imgs.nth(i)
                        try:
                            box = await cand.bounding_box()
                            if not box:
                                continue
                            if vw and float(box.get("x", 0.0)) <= vw * 0.5:
                                continue
                            try:
                                nw = int(await cand.evaluate("el => el.naturalWidth || 0"))
                            except Exception:
                                nw = 0
                            if nw <= 1:
                                continue
                            if await cand.is_visible():
                                first_img = cand
                                break
                        except Exception:
                            continue
                    if first_img is None:
                        raise RuntimeError("no visible broll results")
                except Exception:
                    words = current_query.split()
                    if len(words) > 1:
                        current_query = ' '.join(words[:-1])
                        self._emit_notice(f"⚠️ broll_retry: результатов не видно, сокращаю запрос до '{current_query}'")
                        continue
                    break

                clicked = await human_coordinate_click(page, first_img)
                if clicked:
                    found = True
                    break

                err = "не удалось кликнуть первый результат B-roll"
                self._emit_notice(f"❌ broll_error: {err}")
                await self._take_error_screenshot(page, f"broll_click_result_fail_{scene_idx}")
                if self.report is not None:
                    self.report['broll_errors'].append({'scene_idx': scene_idx, 'query': current_query, 'error': err})
                self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": False})
                return False
            
            if not found:
                err = f"результаты не найдены для запроса '{query}'"
                self._emit_notice(f"❌ broll_no_results: {err}")
                await self._take_error_screenshot(page, f"broll_no_results_{scene_idx}")
                if self.report is not None:
                    self.report['broll_no_results'].append({'scene_idx': scene_idx, 'query': query})
                if self.enable_notifications:
                    await self.notify('HeyGen', f'B-roll без результатов (scene {scene_idx})')
                self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": False})
                return False

            await self._broll_pause(0.25)

            if attempt == 1 and self._wf_bool(self.config.get("broll_validation_force_empty_once"), False):
                try:
                    await self._focus_canvas_for_validation(page)
                    await asyncio.sleep(0.25)
                    await page.keyboard.press("Delete")
                    await asyncio.sleep(0.25)
                except Exception:
                    pass

            if attempt == 1 and self._wf_bool(self.config.get("broll_validation_force_needs_set_bg_once"), False):
                try:
                    await self._focus_canvas_for_validation(page)
                    await asyncio.sleep(0.2)
                    detach_btn = page.get_by_role(
                        "button",
                        name=re.compile(r"^(Detach from BG|Открепить от BG|Открепить от фона)$", re.I),
                    ).first
                    if await detach_btn.count() > 0:
                        try:
                            if await detach_btn.is_visible():
                                await detach_btn.click(timeout=4000)
                                await asyncio.sleep(0.4)
                        except Exception:
                            try:
                                await detach_btn.click(timeout=4000, force=True)
                                await asyncio.sleep(0.4)
                            except Exception:
                                await human_coordinate_click(page, detach_btn)
                                await asyncio.sleep(0.4)
                except Exception:
                    pass

            state = await self._detect_broll_state_after_canvas_click(page)
            if state == "needs_set_bg":
                self._emit_notice("⚠️ broll_validate: needs_set_bg")
                clicked_bg = await self._click_set_as_bg_if_present(page)
                if clicked_bg:
                    state = await self._detect_broll_state_after_canvas_click(page)
                if state == "needs_set_bg":
                    last_validation_reason = "set_as_bg_still_visible"
                elif state == "empty_canvas":
                    last_validation_reason = "bg_color_visible_after_set_bg"
                elif state == "unknown":
                    last_validation_reason = "unknown_after_set_bg"
                else:
                    last_validation_reason = ""
            elif state == "empty_canvas":
                self._emit_notice("⚠️ broll_validate: empty_canvas")
                last_validation_reason = "bg_color_visible_after_insert"
            elif state == "unknown":
                self._emit_notice("⚠️ broll_validate: unknown_state")
                last_validation_reason = "unknown_state"
            else:
                last_validation_reason = ""

            if state == "ok":
                if self.close_media_panel_after_broll:
                    try:
                        close_btn = page.locator('button:has(iconpark-icon[name="close"])')
                        if await close_btn.count() > 0:
                            await close_btn.first.click(timeout=5000)
                            await self._broll_pause(0.2)
                    except Exception:
                        pass

                self._emit_notice(f"✅ broll_done: scene={scene_idx}")
                await self._take_error_screenshot(page, f"broll_done_{scene_idx}")
                self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": True})
                return True

            snap = await self._take_debug_screenshot(page, f"broll_validate_fail_{scene_idx}_try{attempt}")
            if attempt < 3:
                self._emit_notice(f"⚠️ broll_retry_validation: {attempt}/3 reason={last_validation_reason}")
                continue

            err = f"валидация B-roll не прошла после 3 попыток: {last_validation_reason or 'unknown'}"
            self._emit_notice(f"❌ broll_error: {err}")
            if self.report is not None:
                self.report['broll_errors'].append(
                    {
                        'scene_idx': scene_idx,
                        'query': query,
                        'error': err,
                        'kind': 'validation_failed',
                        'attempt': attempt,
                        'reason': last_validation_reason or 'unknown',
                        'screenshot': snap or '',
                    }
                )
            self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": False})
            return False

    async def click_save_and_wait(self, page: Page):
        print("\n💾 Сохраняю изменения перед проверкой...")
        await self._await_gate()
        wait_ms = max(int(self.save_notification_timeout_ms), 40000)

        async def _wait_saved() -> bool:
            try:
                notif_ru = page.locator('div').filter(has_text=re.compile(r'^\s*Сохранено\s*$'))
                if await notif_ru.count() > 0:
                    loc = notif_ru.nth(2) if await notif_ru.count() > 2 else notif_ru.first
                    await loc.wait_for(state='visible', timeout=wait_ms)
                    return True
            except Exception:
                pass
            try:
                notif_en = page.locator('div').filter(has_text=re.compile(r'^\s*Saved\s*$'))
                if await notif_en.count() > 0:
                    loc = notif_en.nth(2) if await notif_en.count() > 2 else notif_en.first
                    await loc.wait_for(state='visible', timeout=wait_ms)
                    return True
            except Exception:
                pass
            return False

        try:
            try:
                await self._await_gate()
                await page.keyboard.press('Meta+S')
            except Exception:
                pass

            saved = await _wait_saved()
            if not saved:
                try:
                    menu_btn = page.get_by_role("button").nth(1)
                    await menu_btn.click(timeout=5000)
                except Exception:
                    pass
                try:
                    save_item = page.locator('div').filter(has_text=re.compile(r'^\s*Сохранить\s*$'))
                    if await save_item.count() > 0:
                        target = save_item.nth(3) if await save_item.count() > 3 else save_item.first
                        await target.click(timeout=5000)
                except Exception:
                    pass
                saved = await _wait_saved()

            if not saved:
                try:
                    btn = page.locator('button:has(iconpark-icon[name="saved"])')
                    if await btn.count() == 0:
                        ico = page.locator('iconpark-icon[name="saved"]')
                        if await ico.count() > 0:
                            btn = ico.first.locator('xpath=ancestor::button[1]')
                    if await btn.count() > 0:
                        await self._await_gate()
                        await btn.first.scroll_into_view_if_needed()
                        await asyncio.sleep(0.1)
                        await self._await_gate()
                        await btn.first.click(timeout=5000)
                        await _wait_saved()
                except Exception:
                    pass

            if saved:
                print("✅ Сохранено — уведомление получено")
            else:
                await self._await_gate()
                await asyncio.sleep(self.save_fallback_wait_sec)
        except Exception as e:
            print(f"⚠️ Ошибка при сохранении: {e}")
            await self._await_gate()
            await asyncio.sleep(self.save_fallback_wait_sec)

    async def bring_terminal_to_front(self):
        try:
            subprocess.Popen(['osascript', '-e', 'tell application "Terminal" to activate'])
        except Exception:
            pass

    async def close_browser(self):
        try:
            page = getattr(self, "_page", None)
            if page is not None:
                try:
                    browser = page.context.browser
                    if browser is not None:
                        await browser.close()
                except Exception:
                    pass
        finally:
            try:
                self._page = None
            except Exception:
                pass

    async def refresh_and_validate(self, page: Page, scenes: list, interactive: bool = True):
        # Обновление страницы
        print("\n🔄 Обновляю страницу для проверки вставленных текстов...")
        try:
            await self._await_gate()
            await self.click_save_and_wait(page)
            await self._await_gate()
            await page.reload(wait_until='domcontentloaded', timeout=self.reload_timeout_ms)
            try:
                await page.wait_for_load_state('networkidle', timeout=self.validation_ready_timeout_ms)
            except Exception:
                pass
            try:
                await page.wait_for_selector('span[data-node-view-content-react]', timeout=self.validation_ready_timeout_ms)
            except Exception:
                await self._await_gate()
                await asyncio.sleep(self.post_reload_wait)
        except Exception as e:
            print(f"⚠️ Ошибка при обновлении страницы: {e}")
            await self._await_gate()
            await asyncio.sleep(self.post_reload_wait)

        # Повторная замена оставшихся плейсхолдеров text_X
        scenes_by_idx = {int(s['scene_idx']): s['text'] for s in scenes}
        changed = False
        try:
            locator = page.locator('span[data-node-view-content-react]')
            texts = await locator.all_inner_texts()
            remaining = []
            for t in texts:
                m = re.fullmatch(r"\s*text_(\d+)\s*", t or "")
                if m:
                    remaining.append(int(m.group(1)))
            if remaining:
                print(f"⚠️ Найдены не заполненные плейсхолдеры: {remaining}")
            for idx in remaining:
                await self._await_gate()
                expected = scenes_by_idx.get(idx)
                if expected:
                    await self.fill_scene(page, idx, expected)
                    await self._await_gate()
                    await asyncio.sleep(0.2)
                    changed = True
        except Exception as e:
            print(f"⚠️ Не удалось выполнить проверку плейсхолдеров: {e}")

        # Проверка наличия ожидаемых текстов
        print("\n🔍 Проверяю наличие ожидаемых текстов из CSV...")
        missing = []
        # Получаем все текущие тексты из страницы один раз
        try:
            locator_all = page.locator('span[data-node-view-content-react]')
            all_texts = [self.normalize_text_for_compare(t) for t in await locator_all.all_inner_texts()]
        except Exception:
            all_texts = []
        for s in scenes:
            await self._await_gate()
            expected_text = self.normalize_text_for_compare(s['text'])
            scene_idx = int(s['scene_idx'])
            present = expected_text and (expected_text in all_texts)
            if not present:
                # Попытка автоисправления: placeholder text_X
                auto_fixed = False
                try:
                    ph = page.locator('span[data-node-view-content-react]').filter(has_text=re.compile(rf'^\s*text_{scene_idx}\s*$'))
                    if await ph.count() > 0:
                        await self.fill_scene(page, scene_idx, s['text'])
                        await self._await_gate()
                        await asyncio.sleep(0.2)
                        auto_fixed = True
                except Exception:
                    pass
                
                # Удален опасный фолбэк по индексу, который перезаписывал заполненные сцены.
                # Теперь мы полагаемся только на явное наличие text_N (auto_fixed).
                
                if auto_fixed:
                    try:
                        locator_all2 = page.locator('span[data-node-view-content-react]')
                        all_texts = [self.normalize_text_for_compare(t) for t in await locator_all2.all_inner_texts()]
                    except Exception:
                        pass
                    changed = True
                    present = expected_text and (expected_text in all_texts)
                if not present:
                    print(f"\n========================================")
                    print(f"❌ Текст отсутствует после автоисправления: scene_idx={scene_idx}")
                    print(f"========================================\n")
                    missing.append(scene_idx)
        if not missing:
            print("✅ Все ожидаемые тексты обнаружены на странице")
        else:
            print(f"⚠️ Остались несоответствия в сценах: {missing}")

        # Поиск подозрительных текстов, которых нет в CSV
        try:
            locator = page.locator('span[data-node-view-content-react]')
            all_texts = [self.normalize_text_for_compare(t) for t in await locator.all_inner_texts()]
            expected_set = {self.normalize_text_for_compare(s['text']) for s in scenes}
            unknown = [t for t in all_texts if t and not re.fullmatch(r'text_\d+', t) and t not in expected_set]
            if unknown:
                print(f"⚠️ Обнаружены незнакомые тексты (возможные фантомы): {unknown}")
        except Exception:
            pass

        # Не прерываем процесс, даже если остались несоответствия
        abort_on_fail = bool(self.config.get('abort_on_validation_failure', False))
        ok = (not missing) or (not abort_on_fail)
        if self.enable_notifications and missing:
            await self.notify('HeyGen', f'Несоответствия: {missing}')
        if self.report is not None and missing:
            for m in missing:
                self.report['validation_missing'].append({'scene_idx': m})
        return {'ok': ok, 'changed': changed, 'missing': missing}

    def print_final_report(self):
        if not self.report:
            return
        print("\n🧾 Финальный отчёт")
        if self.report['validation_missing']:
            print(f" - Несоответствия после проверки: {self.report['validation_missing']}")
        if self.report['broll_skipped']:
            print(f" - B-roll пропущен (пустой запрос): {self.report['broll_skipped']}")
        if self.report['broll_no_results']:
            print(f" - B-roll без результатов: {self.report['broll_no_results']}")
        if self.report['broll_errors']:
            print(f" - Ошибки B-roll: {self.report['broll_errors']}")
        if self.report['manual_intervention']:
            print(f" - Ручные подтверждения: {self.report['manual_intervention']}")

    async def notify(self, title: str, message: str):
        if not self.enable_notifications:
            return
        try:
            subprocess.Popen(['osascript', '-e', f'display notification "{message}" with title "{title}"'])
        except Exception:
            pass

    async def process_many(self, episodes: list):
        if not episodes:
            return False
        ok = True
        for ep in episodes:
            parts = self.get_all_episode_parts(ep)
            for part_idx in parts:
                res = await self.process_episode_part(ep, part_idx)
                ok = ok and bool(res)
        return ok
    
    async def process_full_episode(self, episode_id: str):
        """
        Обработать все части эпизода автоматически
        
        Args:
            episode_id: ID эпизода (например, 'ep_1')
        """
        # Получаем все части эпизода
        parts = self.get_all_episode_parts(episode_id)
        
        if not parts:
            print(f"❌ Нет частей для эпизода {episode_id}")
            return False
        
        print(f"\n{'='*60}")
        print(f"📺 Обработка эпизода: {episode_id}")
        print(f"📋 Найдено частей: {len(parts)} - {parts}")
        print(f"{'='*60}\n")
        
        # Обрабатываем каждую часть
        ok_all = True
        for i, part_idx in enumerate(parts, 1):
            print(f"\n{'='*60}")
            print(f"🎬 Обрабатываю {episode_id}, часть {part_idx} ({i}/{len(parts)})")
            print(f"{'='*60}\n")
            
            success = await self.process_episode_part(episode_id, part_idx)
            ok_all = ok_all and bool(success)
            if success:
                print(f"✅ Часть {part_idx} успешно обработана и отправлена на генерацию!")
            else:
                print(f"⚠️ Часть {part_idx} завершена с ошибками")
            
            # Пауза между частями (кроме последней)
            if i < len(parts):
                wait_time = 5
                print(f"\n⏳ Пауза {wait_time} секунд перед следующей частью...")
                await asyncio.sleep(wait_time)
        
        print(f"\n{'='*60}")
        print(f"🎉 ВСЕ ЧАСТИ ЭПИЗОДА {episode_id} ОБРАБОТАНЫ!")
        print(f"{'='*60}\n")
        
        return ok_all


async def main():
    """
    Основная функция для тестирования
    """
    print("=" * 60)
    print("🎬 HeyGen Automation Script")
    print("=" * 60)
    
    # Загружаем конфигурацию
    config_path = "config.json"
    
    if not os.path.exists(config_path):
        print(f"❌ Файл конфигурации {config_path} не найден!")
        print("   Создай файл config.json по инструкции")
        return
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Ошибка чтения конфигурации: {e}")
        return
    
    # Получаем параметры из конфига
    csv_path = config.get('csv_file', 'scenarios.csv')
    browser_mode = (config.get('browser') or 'chrome').lower()
    profiles = config.get('profiles') or {}
    profile_to_use = (config.get('profile_to_use') or '').strip()

    # CLI-параметры
    try:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('--profile', type=str)
        args, _ = parser.parse_known_args()
        if args.profile:
            config['profile_to_use'] = args.profile
            profile_to_use = args.profile
    except Exception:
        pass
    
    print(f"\n📋 Конфигурация:")
    print(f"   CSV файл: {csv_path}")
    print(f"   Макс. сцен в шаблоне: {config.get('max_scenes', 15)}")
    print(f"   Браузер: {browser_mode}")
    if browser_mode == 'chrome' and profiles:
        keys = list(profiles.keys())
        print("   Доступные профили Chrome:")
        for i, k in enumerate(keys, 1):
            print(f"     {i}. {k}")
        if not profile_to_use or profile_to_use not in profiles or profile_to_use == 'ask':
            try:
                choice = input("   Выбери профиль (номер или имя): ").strip()
                selected = None
                if choice.isdigit():
                    idx = int(choice)
                    if 1 <= idx <= len(keys):
                        selected = keys[idx - 1]
                elif choice in profiles:
                    selected = choice
                if selected:
                    config['profile_to_use'] = selected
                    print(f"   ✅ Выбран профиль: {selected}")
                else:
                    print("   ⚠️ Некорректный выбор, будет использован дефолтный CDP URL")
            except Exception:
                print("   ⚠️ Не удалось получить ввод, будет использован дефолтный CDP URL")
    
    # Проверяем существование CSV файла
    if not os.path.exists(csv_path):
        print(f"\n❌ CSV файл {csv_path} не найден!")
        print(f"   Положи файл в папку: {os.getcwd()}")
        return
    
    # Создаем объект автоматизации
    automation = HeyGenAutomation(csv_path, config)
    
    # Загружаем данные
    automation.load_data()
    
    # Определяем список эпизодов для обработки
    episodes = config.get('episodes_to_process') or []
    if not episodes:
        try:
            episodes = sorted([str(e) for e in automation.df['episode_id'].dropna().unique()])
        except Exception:
            episodes = []
    
    if not episodes:
        print("\n❌ В CSV не найдены эпизоды (episode_id)")
        return
    
    # Обрабатываем все найденные эпизоды
    print("\n" + "=" * 60)
    print(f"🚀 Запускаю обработку эпизодов: {episodes}")
    print("=" * 60 + "\n")
    
    await automation.process_many(episodes)


if __name__ == "__main__":
    asyncio.run(main())
