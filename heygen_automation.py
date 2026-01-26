import asyncio
import pandas as pd
import random
from playwright.async_api import async_playwright, Page
import os
import json
import re
import argparse
import subprocess

class HeyGenAutomation:
    def __init__(self, csv_path: str, config: dict):
        """
        Инициализация автоматизации HeyGen
        
        Args:
            csv_path: Путь к CSV файлу со сценариями
        """
        self.csv_path = csv_path
        self.df = None
        self.config = config or {}
        self.max_scenes = int(self.config.get('max_scenes', 15))
        self.pre_fill_wait = float(self.config.get('pre_fill_wait', 1.0))
        self.delay_between_scenes = float(self.config.get('delay_between_scenes', 2.5))
        
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

    def _block_generation_reason(self) -> str:
        if not self.report:
            return ""
        reasons = []
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
        return "; ".join(reasons)

    def _should_block_generation(self) -> bool:
        if not self.report:
            return False
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

    async def _open_media_panel(self, page: Page) -> bool:
        try:
            panel_header = page.locator('h2').filter(has_text=re.compile(r'^\s*(Медиа|Media)\s*$'))
            if await panel_header.count() > 0:
                return True
        except Exception:
            pass

        candidates = []
        try:
            media_icon = page.locator('iconpark-icon[name="media2"]')
            if await media_icon.count() > 0:
                candidates.append(media_icon.first.locator('xpath=ancestor::button[1]'))
        except Exception:
            pass
        try:
            candidates.append(page.get_by_role('button', name=re.compile(r'^\s*(Медиа|Media)\s*$', re.I)))
        except Exception:
            pass
        try:
            candidates.append(page.locator('button').filter(has_text=re.compile(r'^\s*(Медиа|Media)\s*$', re.I)).first)
        except Exception:
            pass

        for btn in candidates:
            try:
                if await btn.count() == 0:
                    continue
            except Exception:
                continue
            ok = await self._try_click(btn, page, timeout_ms=10000)
            await self._broll_pause(0.2)
            try:
                panel_header = page.locator('h2').filter(has_text=re.compile(r'^\s*(Медиа|Media)\s*$'))
                if ok and await panel_header.count() > 0:
                    return True
            except Exception:
                pass

        return False

    async def _select_video_tab(self, page: Page) -> bool:
        for name in ("Видео", "Video"):
            try:
                tab = page.get_by_role('tab', name=name)
                if await tab.count() > 0:
                    if await self._try_click(tab.first, page, timeout_ms=8000):
                        await self._broll_pause(0.15)
                        return True
            except Exception:
                pass
        try:
            vid_tab = page.locator('button[role="tab"]').filter(has_text=re.compile(r'^\s*(Видео|Video)\s*$'))
            if await vid_tab.count() > 0:
                if await self._try_click(vid_tab.first, page, timeout_ms=8000):
                    await self._broll_pause(0.15)
                    return True
        except Exception:
            pass
        return False

    async def _locate_broll_search_input(self, page: Page):
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

    async def _confirm_broll_added(self, page: Page, min_wait_sec: float = 0.0) -> bool:
        try:
            if min_wait_sec and min_wait_sec > 0:
                await self._broll_pause(float(min_wait_sec))
            for _ in range(50):
                busy = page.locator('[aria-busy="true"], .tw-animate-spin, svg.tw-animate-spin')
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
    
    async def fill_scene(self, page: Page, scene_number: int, text: str):
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
                self._emit_notice(f"⚠️ scene_field_missing: scene={scene_number} label={text_label}")
                self._emit_step({"type": "finish_scene", "scene": scene_number, "ok": False})
                return False
            
            # Кликаем на span с устойчивыми попытками
            await self._await_gate()
            await span_locator.first.scroll_into_view_if_needed()
            await asyncio.sleep(0.05)
            try:
                await page.keyboard.press('Escape')
            except Exception:
                pass
            try:
                await span_locator.first.click(timeout=3000)
            except Exception:
                try:
                    await span_locator.first.click(timeout=3000, force=True)
                except Exception:
                    try:
                        box = await span_locator.first.bounding_box()
                        if box:
                            await page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
                    except Exception:
                        self._emit_notice(f"❌ scene_focus_failed: scene={scene_number} label={text_label}")
                        self._emit_step({"type": "finish_scene", "scene": scene_number, "ok": False})
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
            
            # Очищаем содержимое
            await self._await_gate()
            await page.keyboard.press('Meta+A')
            await asyncio.sleep(0.05)
            await page.keyboard.press('Backspace')
            await asyncio.sleep(random.uniform(0.05, 0.1))
            
            # Вставляем текст
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
            try:
                current_text = await span_locator.first.inner_text(timeout=1500)
                if current_text.strip() != text.strip():
                    for _ in range(2):
                        await span_locator.first.click()
                        await asyncio.sleep(0.1)
                        await page.keyboard.press('Meta+A')
                        await asyncio.sleep(0.05)
                        await page.keyboard.press('Backspace')
                        await asyncio.sleep(0.05)
                        await page.keyboard.insert_text(text)
                        await asyncio.sleep(0.1)
                        await page.keyboard.press('Tab')
                        await asyncio.sleep(0.2)
                        current_text = await span_locator.first.inner_text()
                        if current_text.strip() == text.strip():
                            break
            except asyncio.CancelledError:
                raise
            except Exception:
                pass

            # Дополнительно: нажать кнопку усиления голоса, если доступна
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
            try:
                s_over = (self.config.get('step_overrides') or {}).get('fill_scene') or {}
                check = s_over.get('check')
                if bool(check):
                    cur = await span_locator.first.inner_text()
                    if self.normalize_text_for_compare(cur) != self.normalize_text_for_compare(text):
                        self._emit_notice(f"❌ scene_check_failed: scene={scene_number}")
                        self._emit_step({"type": "finish_scene", "scene": scene_number, "ok": False})
                        return False
            except asyncio.CancelledError:
                raise
            except Exception:
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
            submit_button = page.locator('button:has-text("Отправить")')
            
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
            print(f"❌ Нет данных для обработки")
            return False
        
        p = None
        try:
            p = await async_playwright().start()
            print("\n🌐 Подключаюсь к браузеру через CDP...")
            browser_mode = (self.config.get('browser') or 'chrome').lower()
            chrome_cdp_url = self.config.get('chrome_cdp_url') or 'http://localhost:9222'
            multilogin_cdp_url = self.config.get('multilogin_cdp_url')
            profiles = self.config.get('profiles') or {}
            profile_to_use = (self.config.get('profile_to_use') or '').strip()

            try:
                if browser_mode == 'multilogin':
                    if not multilogin_cdp_url:
                        print("❌ Не задан 'multilogin_cdp_url' в config.json")
                        return False
                    browser = await p.chromium.connect_over_cdp(multilogin_cdp_url)
                    print("✅ Подключился к Multilogin по CDP!")
                else:
                    chosen_cdp = chrome_cdp_url
                    profile_path = str(self.config.get('chrome_profile_path', '~/chrome_automation'))
                    if profiles and profile_to_use and profile_to_use in profiles:
                        pconf = profiles[profile_to_use] or {}
                        if pconf.get('cdp_url'):
                            chosen_cdp = pconf['cdp_url']
                            print(f"✅ Выбран профиль Chrome: {profile_to_use}")
                        if pconf.get('profile_path'):
                            profile_path = pconf['profile_path']
                    elif profiles and profile_to_use and profile_to_use not in profiles:
                        print(f"⚠️ Профиль '{profile_to_use}' не найден в config['profiles'], использую {chrome_cdp_url}")
                    try:
                        browser = await p.chromium.connect_over_cdp(chosen_cdp)
                    except Exception:
                        port = 9222
                        m = re.match(r'.*:(\d+)$', chosen_cdp)
                        if m:
                            try:
                                port = int(m.group(1))
                            except Exception:
                                port = 9222
                        chrome_bin = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
                        subprocess.Popen([chrome_bin, f'--remote-debugging-port={port}', f'--user-data-dir={os.path.expanduser(profile_path)}'])
                        await asyncio.sleep(3)
                        browser = await p.chromium.connect_over_cdp(chosen_cdp)
                    print("✅ Подключился к Chrome!")

                contexts = browser.contexts
                if not contexts:
                    print("❌ Нет открытых окон в целевом браузере")
                    return False
                context = contexts[0]
                page = await context.new_page()
                try:
                    page.set_default_timeout(float(self.config.get('playwright_timeout_ms', 5000)))
                except Exception:
                    pass
            except Exception as e:
                print(f"❌ Не могу подключиться к браузеру: {e}")
                if browser_mode == 'chrome':
                    port = 9222
                    profile_path = str(self.config.get('chrome_profile_path', '~/chrome_automation'))
                    url = chrome_cdp_url
                    if profiles and profile_to_use and profile_to_use in profiles:
                        url = (profiles[profile_to_use] or {}).get('cdp_url', url)
                        profile_path = (profiles[profile_to_use] or {}).get('profile_path', profile_path)
                    m = re.match(r'.*:(\d+)$', url)
                    if m:
                        try:
                            port = int(m.group(1))
                        except Exception:
                            port = 9222
                    chrome_bin = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
                    try:
                        subprocess.Popen([chrome_bin, f'--remote-debugging-port={port}', f'--user-data-dir={os.path.expanduser(profile_path)}'])
                        await asyncio.sleep(3)
                        browser = await p.chromium.connect_over_cdp(url)
                        contexts = browser.contexts
                        if not contexts:
                            print("❌ Нет открытых окон в целевом браузере")
                            return False
                        context = contexts[0]
                        page = await context.new_page()
                        print("✅ Профиль Chrome запущен и подключение выполнено")
                    except Exception:
                        print("\n💡 Не удалось автоматически запустить Chrome, проверь команду запуска:")
                        print(f"   /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port={port} --user-data-dir={profile_path}")
                        return False
                else:
                    print("\n💡 Проверь, что профиль Multilogin запущен и CDP URL корректен")
                    return False

            wf_steps = self.config.get("workflow_steps") or []
            if isinstance(wf_steps, list) and len(wf_steps) > 0:
                ok = await self._run_workflow(page, template_url, scenes, episode_id, part_idx, wf_steps)
                try:
                    await page.close()
                except Exception:
                    pass
                return bool(ok)
            
            # Переходим на страницу шаблона
            print(f"📄 Открываю шаблон: {template_url}")
            await page.goto(template_url, wait_until='domcontentloaded', timeout=120000)
            
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
                success = await self.fill_scene(
                    page, 
                    scene['scene_idx'], 
                    scene['text']
                )
                if success:
                    success_count += 1
                    # Обработка B-rolls, если заданы в CSV
                    if str(scene.get('brolls', '')).strip():
                        try:
                            await self._await_gate()
                            await self.handle_broll_for_scene(page, scene['scene_idx'], str(scene['brolls']).strip())
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

            # Первая проверка: сохранить → перезагрузить → валидировать
            validation = await self.refresh_and_validate(page, scenes, interactive=False)
            if not validation.get('ok', True):
                print("⚠️ Проверка после обновления страницы обнаружила несоответствия")

            # Удаляем пустые сцены перед вторым циклом
            await self.delete_empty_scenes(page, len(scenes), max_scenes=self.max_scenes)

            # Вторая проверка: сохранить → перезагрузить → валидировать
            print("🔁 Выполняю вторую проверку после внесённых исправлений...")
            try:
                await self.click_save_and_wait(page)
                await page.reload(wait_until='domcontentloaded', timeout=self.reload_timeout_ms)
                await asyncio.sleep(self.pre_fill_wait)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            validation2 = await self.refresh_and_validate(page, scenes, interactive=True)
            if not validation2.get('ok', True):
                print("\n🚨 ВНИМАНИЕ: НЕСООТВЕТСТВИЯ ПОСЛЕ ВТОРОЙ ПРОВЕРКИ")
                await self.notify('HeyGen', 'Несоответствия после второй проверки — требуется вмешательство')
                await self.bring_terminal_to_front()
                print("============================================================")
                print("Исправь несоответствия на странице HeyGen и нажми Enter здесь")
                print("Ожидаю без таймаута — продолжу после Enter")
                print("============================================================")
                fut = asyncio.to_thread(input, "")
                await fut
                # Финальная попытка проверки
                validation3 = await self.refresh_and_validate(page, scenes)
                if not validation3.get('ok', True):
                    print("⚠️ Продолжаю несмотря на оставшиеся несоответствия по настройке abort_on_validation_failure=false")
            # Дополнительное удаление пустых сцен после второй проверки
            await self.delete_empty_scenes(page, len(scenes), max_scenes=self.max_scenes)
            
            # Подтверждение перед генерацией (с таймаутом)
            self.print_final_report()
            # Блокируем генерацию, если есть несоответствия
            mismatch_count = len(self.report['validation_missing']) if self.report else 0
            if mismatch_count > 0:
                await self.notify('HeyGen', 'Финальная проверка: есть несоответствия — генерация заблокирована')
                await self.bring_terminal_to_front()
                print("============================================================")
                print("Финальный отчёт содержит несоответствия — генерация заблокирована")
                print("Исправь сцены в HeyGen и нажми Enter здесь")
                print("============================================================")
                fut = asyncio.to_thread(input, "")
                await fut
                # Повторная проверка после вмешательства и удаление пустых сцен
                validation4 = await self.refresh_and_validate(page, scenes, interactive=False)
                await self.delete_empty_scenes(page, len(scenes), max_scenes=self.max_scenes)
                self.print_final_report()
                mismatch_count = len(self.report['validation_missing']) if self.report else 0
                if mismatch_count > 0:
                    print("⚠️ Есть несоответствия даже после вмешательства, продолжаю по настройке abort_on_validation_failure=false")
            if self._should_block_generation():
                reason = self._block_generation_reason()
                await self.notify('HeyGen', f'Генерация заблокирована: {reason}')
                await self.bring_terminal_to_front()
                print("============================================================")
                print("B-roll не добавлен корректно — генерация заблокирована")
                if reason:
                    print(f"Причина: {reason}")
                print("Проверь и исправь сцену в HeyGen вручную и отправь на генерацию сам")
                print("============================================================")
                return False
            await self._await_gate()
            proceed = await self.confirm_before_generation()
            if not proceed:
                print("⏸️ Генерация приостановлена пользователем")
                # Ждём повторного подтверждения
                try:
                    input("Нажми Enter, чтобы продолжить отправку на генерацию...")
                except Exception:
                    pass
            
            # Нажимаем кнопку "Сгенерировать"
            await self.click_generate_button(page)
            
            # Заполняем финальное окно и отправляем
            title = scenes[0]['title']
            await self.fill_and_submit_final_window(page, title)
            
            # Вкладка автоматически закроется после обработки
            print(f"\n✅ Часть {part_idx} обработана и отправлена на генерацию!")
            
            # Закрываем вкладку
            await page.close()
            print(f"🔒 Вкладка закрыта\n")
            
            return True
        except asyncio.CancelledError:
            print("⛔ Задача отменена")
            raise
        except Exception as e:
            print(f"❌ Ошибка обработки части эпизода {episode_id} part={part_idx}: {e}")
            return False
        finally:
            try:
                if 'page' in locals() and page is not None:
                    await page.close()
            except Exception:
                pass
            try:
                if p is not None:
                    await p.stop()
            except Exception:
                pass
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

    async def _run_workflow(self, page: Page, template_url: str, scenes: list, episode_id: str, part_idx: int, steps: list) -> bool:
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

        for raw in steps:
            if not isinstance(raw, dict):
                continue
            if "enabled" in raw and not self._wf_bool(raw.get("enabled"), True):
                continue
            step_type = str(raw.get("type") or "").strip()
            params = raw.get("params") if isinstance(raw.get("params"), dict) else {}
            try:
                if step_type in ("navigate_to_template", "navigate"):
                    url = self._wf_render(params.get("url") or template_url, ctx).strip()
                    wait_until = self._wf_render(params.get("wait_until") or "domcontentloaded", ctx).strip() or "domcontentloaded"
                    timeout = self._wf_int(params.get("timeout_ms"), 120000)
                    print(f"📄 Открываю: {url}")
                    await page.goto(url, wait_until=wait_until, timeout=timeout)
                    continue

                if step_type in ("wait_for", "wait_for_selector"):
                    sel = self._wf_render(params.get("selector") or "", ctx).strip()
                    if not sel:
                        continue
                    timeout = self._wf_int(params.get("timeout_ms"), 30000)
                    state = self._wf_render(params.get("state") or "visible", ctx).strip() or "visible"
                    await page.wait_for_selector(sel, timeout=timeout, state=state)
                    continue

                if step_type in ("wait", "sleep"):
                    sec = self._wf_float(params.get("sec"), self.pre_fill_wait)
                    await asyncio.sleep(sec)
                    continue

                if step_type == "click":
                    sel = self._wf_render(params.get("selector") or "", ctx).strip()
                    if not sel:
                        continue
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
                    continue

                if step_type == "fill":
                    sel = self._wf_render(params.get("selector") or "", ctx).strip()
                    text = self._wf_render(params.get("text") or "", ctx).replace("\\n", "\n")
                    if not sel:
                        continue
                    await page.locator(sel).fill(text)
                    continue

                if step_type == "press":
                    sel = self._wf_render(params.get("selector") or "", ctx).strip()
                    key = self._wf_render(params.get("key") or "", ctx).strip()
                    if not sel or not key:
                        continue
                    await page.press(sel, key)
                    continue

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
                    card_xpath = str(params.get("card_xpath") or 'xpath=ancestor::div[contains(@class,"tw-relative")][1]').strip()

                    if not episode or not title_selector or not checkbox_selector:
                        continue

                    await page.wait_for_selector(title_selector, timeout=timeout)
                    titles = page.locator(title_selector).filter(has_text=episode)
                    cnt = await titles.count()
                    if cnt <= 0:
                        continue

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
                    continue

                if step_type == "fill_scene":
                    inline_broll = None
                    if "handle_broll" in params:
                        inline_broll = self._wf_bool(params.get("handle_broll"), True)
                    elif not has_broll_step:
                        inline_broll = True
                    print(f"\n📝 Начинаю заполнение {len(scenes)} сцен...")
                    success_count = 0
                    for idx, scene in enumerate(scenes, 1):
                        try:
                            ok = await self.fill_scene(page, scene['scene_idx'], scene['text'])
                        except Exception as e:
                            print(f"⚠️ Ошибка заполнения сцены {scene.get('scene_idx')}: {e}")
                            ok = False
                        if ok:
                            success_count += 1
                            if inline_broll and str(scene.get('brolls', '')).strip():
                                try:
                                    await self.handle_broll_for_scene(page, scene['scene_idx'], str(scene['brolls']).strip())
                                except Exception as e:
                                    print(f"⚠️ Ошибка обработки brolls для сцены {scene.get('scene_idx')}: {e}")
                                    if self.report is not None:
                                        self.report['broll_errors'].append({'scene_idx': scene.get('scene_idx'), 'error': str(e)})
                        if idx < len(scenes):
                            await asyncio.sleep(self.delay_between_scenes)
                    print(f"\n📊 Заполнено сцен: {success_count}/{len(scenes)}")
                    continue

                if step_type == "handle_broll":
                    for scene in scenes:
                        if str(scene.get('brolls', '')).strip():
                            try:
                                await self.handle_broll_for_scene(page, scene['scene_idx'], str(scene['brolls']).strip())
                            except Exception as e:
                                print(f"⚠️ Ошибка обработки brolls для сцены {scene.get('scene_idx')}: {e}")
                                if self.report is not None:
                                    self.report['broll_errors'].append({'scene_idx': scene.get('scene_idx'), 'error': str(e)})
                    continue

                if step_type == "delete_empty_scenes":
                    max_scenes = self._wf_int(params.get("max_scenes"), self.max_scenes)
                    await self.delete_empty_scenes(page, len(scenes), max_scenes=max_scenes)
                    continue

                if step_type == "save":
                    await self.click_save_and_wait(page)
                    continue

                if step_type == "reload":
                    wait_until = str(params.get("wait_until") or "domcontentloaded").strip() or "domcontentloaded"
                    timeout = self._wf_int(params.get("timeout_ms"), self.reload_timeout_ms)
                    await page.reload(wait_until=wait_until, timeout=timeout)
                    sec = self._wf_float(params.get("post_wait_sec"), self.pre_fill_wait)
                    if sec > 0:
                        await asyncio.sleep(sec)
                    continue

                if step_type == "reload_and_validate":
                    interactive = self._wf_bool(params.get("interactive"), False)
                    validation = await self.refresh_and_validate(page, scenes, interactive=interactive)
                    if not validation.get('ok', True):
                        print("⚠️ Проверка обнаружила несоответствия")
                    continue

                if step_type == "confirm":
                    proceed = await self.confirm_before_generation()
                    if not proceed:
                        try:
                            input("Нажми Enter, чтобы продолжить отправку на генерацию...")
                        except Exception:
                            pass
                    continue

                if step_type == "generate":
                    if self._should_block_generation():
                        reason = self._block_generation_reason()
                        await self.notify('HeyGen', f'Генерация заблокирована: {reason}')
                        print("============================================================")
                        print("B-roll не добавлен корректно — генерация заблокирована")
                        if reason:
                            print(f"Причина: {reason}")
                        print("Проверь и исправь сцену в HeyGen вручную и отправь на генерацию сам")
                        print("============================================================")
                        return False
                    await self.click_generate_button(page)
                    continue

                if step_type == "final_submit":
                    if self._should_block_generation():
                        reason = self._block_generation_reason()
                        await self.notify('HeyGen', f'Генерация заблокирована: {reason}')
                        print("============================================================")
                        print("B-roll не добавлен корректно — генерация заблокирована")
                        if reason:
                            print(f"Причина: {reason}")
                        print("Проверь и исправь сцену в HeyGen вручную и отправь на генерацию сам")
                        print("============================================================")
                        return False
                    await self.fill_and_submit_final_window(page, title)
                    continue

                if step_type:
                    print(f"⚠️ Неизвестный шаг воркфлоу: {step_type}")
            except Exception as e:
                print(f"❌ Ошибка шага воркфлоу: type={step_type} err={e}")
                return False

            print(f"\n✅ Часть {part_idx} обработана и отправлена на генерацию!")
            return True

    async def confirm_before_generation(self) -> bool:
        print(f"\n============================================================")
        print(f"❓ Отправка на генерацию через {self.confirm_timeout_sec} сек.")
        print(f"👉 Нажми Enter СЕЙЧАС, чтобы поставить на паузу.")
        print(f"============================================================")
        await self.notify('HeyGen', 'Подтверждение: отправить на генерацию?')
        await self.bring_terminal_to_front()
        try:
            fut = asyncio.to_thread(input, "")
            await asyncio.wait_for(fut, timeout=self.confirm_timeout_sec)
            return False
        except asyncio.TimeoutError:
            print("▶️ Продолжаю: таймаут подтверждения истёк")
            return True
        except Exception:
            return True

    async def handle_broll_for_scene(self, page: Page, scene_idx: int, query: str) -> bool:
        self._emit_notice(f"🎞️ broll_start: scene={scene_idx} query={query}")
        self._emit_step({"type": "start_broll", "scene": scene_idx})
        if not query or str(query).strip() == '' or str(query).strip().lower() == 'nan':
            self._emit_notice("ℹ️ broll_skip_empty")
            if self.report is not None:
                self.report['broll_skipped'].append({'scene_idx': scene_idx})
            return True

        try:
            text_label = f"text_{scene_idx}"
            span_locator = page.locator('span[data-node-view-content-react]').filter(
                has_text=re.compile(rf'^\s*{re.escape(text_label)}\s*$')
            )
            if await span_locator.count() > 0:
                await span_locator.first.scroll_into_view_if_needed()
                await self._broll_pause(0.05)
                try:
                    await page.keyboard.press('Escape')
                except Exception:
                    pass
                try:
                    await span_locator.first.click(timeout=6000)
                except Exception:
                    try:
                        await span_locator.first.click(timeout=6000, force=True)
                    except Exception:
                        box = await span_locator.first.bounding_box()
                        if box:
                            await page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
                await self._broll_pause(0.15)
        except Exception:
            pass

        if not await self._open_media_panel(page):
            err = "не удалось открыть панель Медиа"
            self._emit_notice(f"❌ broll_error: {err}")
            if self.report is not None:
                self.report['broll_errors'].append({'scene_idx': scene_idx, 'query': query, 'error': err})
            if self.enable_notifications:
                await self.notify('HeyGen', f'B-roll: {err} (scene {scene_idx})')
            self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": False})
            return False

        await self._broll_pause(0.2)

        # Вкладка "Видео"/"Video" (сначала активируем вкладку)
        if not await self._select_video_tab(page):
            err = "вкладка Видео/Video не найдена"
            self._emit_notice(f"❌ broll_error: {err}")
            if self.report is not None:
                self.report['broll_errors'].append({'scene_idx': scene_idx, 'query': query, 'error': err})
            if self.enable_notifications:
                await self.notify('HeyGen', f'B-roll: {err} (scene {scene_idx})')
            self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": False})
            return False
        await self._broll_pause(0.2)

        # Источник (Sources)
        try:
            if self.media_source not in ['all', 'все', '']:
                # Находим кнопку комбобокса по вложенному span с текстом
                src_span = page.locator('div[data-selected-value="true"] > span').filter(has_text=re.compile(r'^\s*(Источники|Sources)\s*$'))
                if await src_span.count() > 0:
                    src_btn = src_span.first.locator('xpath=ancestor::button[1]')
                    await src_btn.click(timeout=5000)
                else:
                    try:
                        await page.get_by_role('combobox', name='Источники').click(timeout=5000)
                    except Exception:
                        try:
                            await page.get_by_role('combobox', name='Sources').click(timeout=5000)
                        except Exception:
                            src_btn = page.locator('button[role="combobox"]').filter(has_text=re.compile(r'^\s*(Источники|Sources)\s*$'))
                            if await src_btn.count() > 0:
                                await src_btn.first.click(timeout=5000)
                await asyncio.sleep(0.1)
                src_map = {
                    'all': ['Все', 'All'],
                    'getty': ['Getty'],
                    'storyblocks': ['Storyblocks', 'Storyblock'],
                    'pexels': ['Pexels']
                }
                targets = src_map.get(self.media_source, [])
                picked = False
                # Попытка через aria-controls портала Radix
                try:
                    ctrl_btn = src_span.first.locator('xpath=ancestor::button[1]') if await src_span.count() > 0 else page.locator('button[role="combobox"]').filter(has_text=re.compile(r'^\s*(Источники|Sources)\s*$')).first
                    ctrl_id = await ctrl_btn.get_attribute('aria-controls')
                except Exception:
                    ctrl_id = None
                if ctrl_id:
                    esc = ctrl_id.replace(':', '\\:')
                    for t in targets:
                        opt = page.locator(f'#{esc}').locator(f'text={t}')
                        if await opt.count() > 0:
                            await opt.first.click(timeout=5000)
                            picked = True
                            break
                if not picked:
                    for t in targets:
                        opt2 = page.locator('[role="option"]').filter(has_text=re.compile(rf'^\s*{re.escape(t)}\s*$'))
                        if await opt2.count() > 0:
                            await opt2.first.click(timeout=5000)
                            picked = True
                            break
                try:
                    await page.keyboard.press('Escape')
                except Exception:
                    pass
        except Exception as e:
            print(f"⚠️ Не удалось выбрать источник: {e}")

        # Ориентация → выбор по локали
        try:
            await page.get_by_role('combobox', name='Ориентация').click(timeout=5000)
        except Exception:
            try:
                combo = page.locator('button[role="combobox"]').filter(has_text=re.compile(r'Ориентация'))
                if await combo.count() > 0:
                    await combo.first.click(timeout=5000)
                else:
                    print("⚠️ Комбобокс 'Ориентация' не найден")
            except Exception as e:
                print(f"⚠️ Не удалось открыть комбобокс 'Ориентация': {e}")
        try:
            await asyncio.sleep(0.1)
            combo_open = page.locator('button[role="combobox"][data-state="open"]')
            if await combo_open.count() == 0:
                await asyncio.sleep(0.1)
            target_ru = None
            try:
                ctrl_id = await page.locator('button[role="combobox"]').filter(has_text=re.compile(r'Ориентация')).first.get_attribute('aria-controls')
            except Exception:
                ctrl_id = None
            if ctrl_id:
                esc = ctrl_id.replace(':', '\\:')
                choice = self.orientation_choice or 'Горизонтальная'
                overlay_ru = page.locator(f'#{esc} >> text={choice}')
                if await overlay_ru.count() > 0:
                    target_ru = overlay_ru.first
            if target_ru:
                await target_ru.click(timeout=5000)
            else:
                opt_ru = page.locator('[role="option"]').filter(has_text=re.compile(rf'^\s*{re.escape(self.orientation_choice or "Горизонтальная")}\s*$'))
                if await opt_ru.count() > 0:
                    await opt_ru.first.click(timeout=5000)
                else:
                    opt_en = page.locator('[role="option"]').filter(has_text=re.compile(r'^\s*Landscape\s*$'))
                    if await opt_en.count() > 0:
                        await opt_en.first.click(timeout=5000)
                    else:
                        try:
                            await page.keyboard.press('ArrowDown')
                            await asyncio.sleep(0.05)
                            await page.keyboard.press('ArrowDown')
                            await asyncio.sleep(0.05)
                            await page.keyboard.press('Enter')
                        except Exception:
                            print("⚠️ Опция ориентации не найдена")
            try:
                await page.keyboard.press('Escape')
            except Exception:
                pass
            try:
                selected = page.locator('button[role="combobox"]').locator('div[data-selected-value="true"] span')
                val = (await selected.first.inner_text()).strip()
                if val not in ['Landscape', 'Горизонтальная']:
                    print(f"⚠️ Ориентация выбрана, но текущее значение: '{val}'")
            except Exception:
                pass
        except Exception as e:
            print(f"⚠️ Не удалось выбрать ориентацию: {e}")

        await self._broll_pause(0.2)

        # Поле поиска → ввести запрос
        search_input = None
        try:
            self._emit_notice("🔎 broll_search")
            search_input = await self._locate_broll_search_input(page)
            if not search_input:
                raise RuntimeError("поисковое поле не найдено")
            try:
                await search_input.focus(timeout=6000)
            except Exception:
                try:
                    await search_input.click(timeout=6000)
                except Exception:
                    pass
            await self._broll_pause(0.1)
            try:
                await search_input.fill(query, timeout=6000)
            except Exception:
                try:
                    await search_input.click(timeout=6000)
                except Exception:
                    pass
                try:
                    await page.keyboard.press('Meta+A')
                    await self._broll_pause(0.05)
                    await page.keyboard.press('Backspace')
                    await self._broll_pause(0.05)
                    await page.keyboard.insert_text(query)
                except Exception:
                    pass
            await self._broll_pause(0.15)
            try:
                await page.keyboard.press('Enter')
            except Exception:
                pass
        except Exception as e:
            err = f"не удалось выполнить поиск: {e}"
            self._emit_notice(f"❌ broll_error: {err}")
            if self.report is not None:
                self.report['broll_errors'].append({'scene_idx': scene_idx, 'query': query, 'error': err})
            if self.enable_notifications:
                await self.notify('HeyGen', f'B-roll: поиск не выполнен (scene {scene_idx})')
            self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": False})
            return False

        # Ожидание результатов до 5 сек или до появления карточек
        results_selector = 'div.tw-group.tw-relative.tw-overflow-hidden.tw-rounded-md'
        try:
            await page.wait_for_selector(results_selector, timeout=self.search_results_timeout_ms)
        except Exception:
            # Сокращаем запрос по последнему слову до 2 слов
            try:
                words = query.split()
                while len(words) > 2:
                    words = words[:-1]
                    q2 = ' '.join(words)
                    if search_input:
                        await self._try_click(search_input, page, timeout_ms=6000)
                    await page.keyboard.press('Meta+A')
                    await page.keyboard.press('Backspace')
                    await page.keyboard.insert_text(q2)
                    await page.keyboard.press('Enter')
                    try:
                        await page.wait_for_selector(results_selector, timeout=self.search_results_timeout_ms)
                        query = q2
                        break
                    except Exception:
                        continue
                else:
                    err = f"результаты не найдены для запроса '{query}'"
                    self._emit_notice(f"❌ broll_no_results: {err}")
                    if self.report is not None:
                        self.report['broll_no_results'].append({'scene_idx': scene_idx, 'query': query})
                    if self.enable_notifications:
                        await self.notify('HeyGen', f'B-roll без результатов (scene {scene_idx})')
                    self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": False})
                    return False
            except Exception as e2:
                err = f"ошибка при повторном поиске: {e2}"
                self._emit_notice(f"❌ broll_error: {err}")
                if self.report is not None:
                    self.report['broll_errors'].append({'scene_idx': scene_idx, 'query': query, 'error': err})
                if self.enable_notifications:
                    await self.notify('HeyGen', f'B-roll: ошибка поиска (scene {scene_idx})')
                self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": False})
                return False

        # Выбрать первый видео-результат
        try:
            self._emit_notice("🧩 broll_pick_first")
            first_card = page.locator(results_selector).first
            try:
                await first_card.click(timeout=8000, force=True)
            except Exception:
                box = await first_card.bounding_box()
                if box:
                    await page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
            await self._broll_pause(float(self.broll_before_make_bg_wait_sec))
        except Exception as e:
            err = f"не удалось выбрать первый результат: {e}"
            self._emit_notice(f"❌ broll_error: {err}")
            if self.report is not None:
                self.report['broll_errors'].append({'scene_idx': scene_idx, 'query': query, 'error': err})
            if self.enable_notifications:
                await self.notify('HeyGen', f'B-roll: не удалось выбрать результат (scene {scene_idx})')
            self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": False})
            return False

        # Нажать "Сделать фоном"
        broll_applied = False
        try:
            self._emit_notice("🖼️ broll_make_background")
            did_click = False
            for attempt in range(1, 4):
                self._emit_notice(f"🖼️ broll_make_background_try: {attempt}/3")
                if not did_click:
                    clicked_this_attempt = False
                    make_bg_btn = page.locator("button").filter(
                        has_text=re.compile(r"(Сделать фоном|Сделать фон|Set as background|Make background)", re.I)
                    )
                    if await make_bg_btn.count() > 0:
                        clicked_this_attempt = await self._try_click(make_bg_btn.first, page, timeout_ms=12000)
                    if not clicked_this_attempt:
                        try:
                            alt_btns = page.locator('button:has(iconpark-icon[name="detachfromframe"])')
                            c = await alt_btns.count()
                            if c > 0:
                                clicked_this_attempt = await self._try_click(alt_btns.last, page, timeout_ms=12000)
                        except Exception:
                            clicked_this_attempt = False
                    if not clicked_this_attempt:
                        try:
                            menu_item = page.locator("[role='menuitem']").filter(
                                has_text=re.compile(r"(Сделать фоном|Set as background|Make background)", re.I)
                            )
                            if await menu_item.count() > 0:
                                clicked_this_attempt = await self._try_click(menu_item.first, page, timeout_ms=12000)
                        except Exception:
                            pass
                    if not clicked_this_attempt:
                        try:
                            inside = first_card.locator("button").filter(
                                has_text=re.compile(r"(Сделать фоном|Set as background|Make background)", re.I)
                            )
                            if await inside.count() > 0:
                                clicked_this_attempt = await self._try_click(inside.first, page, timeout_ms=12000)
                        except Exception:
                            pass
                    if not clicked_this_attempt:
                        try:
                            inside_detach = first_card.locator('iconpark-icon[name="detachfromframe"]').first.locator(
                                "xpath=ancestor::button[1]"
                            )
                            if await inside_detach.count() > 0:
                                clicked_this_attempt = await self._try_click(inside_detach.first, page, timeout_ms=12000)
                        except Exception:
                            pass
                    if not clicked_this_attempt:
                        try:
                            self._emit_notice("🖼️ broll_make_background_focus_scene")
                            if await self._click_scene_center(page):
                                await self._broll_pause(0.25)
                            make_bg_btn2 = page.locator("button").filter(
                                has_text=re.compile(r"(Сделать фоном|Сделать фон|Set as background|Make background)", re.I)
                            )
                            if await make_bg_btn2.count() > 0:
                                clicked_this_attempt = await self._try_click(make_bg_btn2.first, page, timeout_ms=12000)
                        except Exception:
                            pass
                    did_click = bool(clicked_this_attempt)

                if did_click:
                    broll_applied = await self._confirm_broll_added(page, min_wait_sec=self.broll_after_make_bg_min_wait_sec)
                    if broll_applied:
                        break
                await self._broll_pause(0.35)
            if not did_click:
                try:
                    self._emit_notice("⚠️ broll_skip_make_background: button_not_found")
                    if self.report is not None:
                        self.report['broll_skipped'].append({'scene_idx': scene_idx, 'query': query, 'reason': 'make_bg_btn_missing'})
                except Exception:
                    pass
                self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": False})
                return True
        except Exception as e:
            err = f"не удалось нажать 'Сделать фоном': {e}"
            self._emit_notice(f"❌ broll_error: {err}")
            if self.report is not None:
                self.report['broll_errors'].append({'scene_idx': scene_idx, 'query': query, 'error': err})
            if self.enable_notifications:
                await self.notify('HeyGen', f'B-roll: не удалось сделать фоном (scene {scene_idx})')
            self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": False})
            return False

        await self._broll_pause(0.25)

        if not broll_applied:
            err = "не удалось подтвердить добавление B-roll"
            self._emit_notice(f"❌ broll_error: {err}")
            if self.report is not None:
                self.report['broll_errors'].append({'scene_idx': scene_idx, 'query': query, 'error': err})
            if self.enable_notifications:
                await self.notify('HeyGen', f'B-roll: не добавился (scene {scene_idx})')
            self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": False})
            return False

        self._emit_notice("🗑️ broll_delete_foreground")
        deleted = False
        for attempt in range(1, 4):
            self._emit_notice(f"🗑️ broll_delete_foreground_try: {attempt}/3")
            deleted = await self._try_delete_foreground(page)
            if deleted:
                break
            await self._broll_pause(0.25)
        if not deleted:
            err = "не удалось удалить передний слой"
            self._emit_notice(f"❌ broll_error: {err}")
            if self.report is not None:
                self.report['broll_errors'].append({'scene_idx': scene_idx, 'query': query, 'error': err})
            if self.enable_notifications:
                await self.notify('HeyGen', f'B-roll: не удалился слой (scene {scene_idx})')
            self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": False})
            return False

        if self.close_media_panel_after_broll:
            try:
                close_btn = page.locator('button:has(iconpark-icon[name="close"])')
                if await close_btn.count() > 0:
                    await close_btn.first.click(timeout=5000)
                    await self._broll_pause(0.2)
            except Exception:
                pass

        # Без ручной проверки: продолжаем по тайм-аутам
        self._emit_notice(f"✅ broll_done: scene={scene_idx}")
        self._emit_step({"type": "finish_broll", "scene": scene_idx, "ok": True})
        return True

    async def click_save_and_wait(self, page: Page):
        print("\n💾 Сохраняю изменения перед проверкой...")
        await self._await_gate()
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
            else:
                print("⚠️ Кнопка сохранения не найдена — выполняю Cmd+S")
                try:
                    await self._await_gate()
                    await page.keyboard.press('Meta+S')
                except Exception:
                    pass
            try:
                notif_ru = page.get_by_text('Сохранено', exact=True)
                notif_en = page.get_by_text('Saved', exact=True)
                try:
                    await notif_ru.wait_for(state='visible', timeout=self.save_notification_timeout_ms)
                except Exception:
                    await notif_en.wait_for(state='visible', timeout=self.save_notification_timeout_ms)
                print("✅ Сохранено — уведомление получено")
            except Exception:
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
                # Осторожный фолбэк по индексу, только если структура сцены выглядит последовательной
                if not auto_fixed:
                    try:
                        spans = page.locator('span[data-node-view-content-react]')
                        total = await spans.count()
                        if scene_idx - 1 < total:
                            candidate = spans.nth(scene_idx - 1)
                            t = await candidate.inner_text()
                            norm_t = self.normalize_text_for_compare(t)
                            # Пишем только если текст действительно отличается от ожидаемого
                            if norm_t != expected_text:
                                await candidate.scroll_into_view_if_needed()
                                await self._await_gate()
                                await asyncio.sleep(0.05)
                                try:
                                    await page.keyboard.press('Escape')
                                except Exception:
                                    pass
                                try:
                                    await candidate.click(timeout=2000)
                                except Exception:
                                    try:
                                        await candidate.click(timeout=2000, force=True)
                                    except Exception:
                                        box = await candidate.bounding_box()
                                        if box:
                                            await page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
                                await self._await_gate()
                                await asyncio.sleep(0.05)
                                await page.keyboard.press('Meta+A')
                                await self._await_gate()
                                await asyncio.sleep(0.05)
                                await page.keyboard.press('Backspace')
                                await self._await_gate()
                                await asyncio.sleep(0.05)
                                await page.keyboard.insert_text(s['text'])
                                await self._await_gate()
                                await asyncio.sleep(0.1)
                                await page.keyboard.press('Tab')
                                await self._await_gate()
                                await asyncio.sleep(0.1)
                                auto_fixed = True
                    except Exception:
                        pass
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
                # Интерактивная пауза для ручной проверки
                do_interact = interactive
                try:
                    do_interact = do_interact and bool(self.config.get('interactive_on_mismatch', True))
                except Exception:
                    pass
                if do_interact:
                    pressed = False
                    try:
                        await self._await_gate()
                        await self.notify('HeyGen', f'Требуется проверка сцены {scene_idx}')
                        await self.bring_terminal_to_front()
                        print(f"\n🚨 ВНИМАНИЕ: ТРЕБУЕТСЯ ВМЕШАТЕЛЬСТВО ПОЛЬЗОВАТЕЛЯ 🚨")
                        print(f"👉 Проверь сцену {scene_idx} вручную на странице HeyGen.")
                        print(f"👉 После исправления нажми Enter в этом окне (таймаут {self.confirm_timeout_sec} c)")
                        print(f"============================================================\n")
                        fut = asyncio.to_thread(input, "")
                        await asyncio.wait_for(fut, timeout=self.confirm_timeout_sec)
                        pressed = True
                    except asyncio.TimeoutError:
                        pass
                    except Exception:
                        pass
                    try:
                        cnt2 = await page.get_by_text(re.compile(re.escape(expected_text))).count()
                        if cnt2 > 0:
                            print(f"✅ Сцена {scene_idx} подтверждена {'вручную' if pressed else 'по таймауту'}")
                            missing.pop()
                            changed = True
                            if pressed and self.report is not None:
                                self.report['manual_intervention'].append({'scene_idx': scene_idx, 'step': 'text_confirm'})
                    except Exception:
                        pass
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
        for i, part_idx in enumerate(parts, 1):
            print(f"\n{'='*60}")
            print(f"🎬 Обрабатываю {episode_id}, часть {part_idx} ({i}/{len(parts)})")
            print(f"{'='*60}\n")
            
            success = await self.process_episode_part(episode_id, part_idx)
            
            if not success:
                print(f"❌ Ошибка при обработке части {part_idx}, останавливаюсь")
                return False
            
            print(f"✅ Часть {part_idx} успешно обработана и отправлена на генерацию!")
            
            # Пауза между частями (кроме последней)
            if i < len(parts):
                wait_time = 5
                print(f"\n⏳ Пауза {wait_time} секунд перед следующей частью...")
                await asyncio.sleep(wait_time)
        
        print(f"\n{'='*60}")
        print(f"🎉 ВСЕ ЧАСТИ ЭПИЗОДА {episode_id} ОБРАБОТАНЫ!")
        print(f"{'='*60}\n")
        
        return True


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
