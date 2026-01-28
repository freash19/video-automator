"""
B-roll handling for HeyGen automation.

Manages media panel interaction, video search, and background insertion.
Includes support for Nano Banano AI-generated images.
"""

import asyncio
import json
import os
import re
import time
from typing import TYPE_CHECKING, Optional, Callable, Awaitable, List, Tuple, Iterable

from ui.logger import logger
from core.browser import safe_click, random_delay, click_canvas_center
from utils.clipboard import parse_nano_banano_prompt, generate_image, copy_image_to_clipboard

if TYPE_CHECKING:
    from playwright.async_api import Page, Locator


async def _dump_ui_candidates(page: "Page", tag: str) -> None:
    try:
        os.makedirs("debug/inspection", exist_ok=True)
        ts = int(time.time() * 1000)
        safe = "".join(ch for ch in str(tag) if ch.isalnum() or ch in "_-")
        out_path = f"debug/inspection/{safe}_{ts}.json"

        buttons = []
        try:
            loc = page.locator("button")
            cnt = await loc.count()
            for i in range(min(cnt, 120)):
                b = loc.nth(i)
                try:
                    if not await b.is_visible():
                        continue
                except Exception:
                    continue
                try:
                    text = (await b.inner_text()) or ""
                except Exception:
                    text = ""
                try:
                    aria = (await b.get_attribute("aria-label")) or ""
                except Exception:
                    aria = ""
                try:
                    role = (await b.get_attribute("role")) or ""
                except Exception:
                    role = ""
                if text.strip() or aria.strip():
                    buttons.append({"text": text.strip(), "aria_label": aria.strip(), "role": role})
        except Exception:
            pass

        menuitems = []
        try:
            loc = page.locator('[role="menuitem"]')
            cnt = await loc.count()
            for i in range(min(cnt, 80)):
                m = loc.nth(i)
                try:
                    if not await m.is_visible():
                        continue
                except Exception:
                    continue
                try:
                    text = (await m.inner_text()) or ""
                except Exception:
                    text = ""
                if text.strip():
                    menuitems.append(text.strip())
        except Exception:
            pass

        icons = []
        try:
            loc = page.locator("iconpark-icon[name]")
            cnt = await loc.count()
            for i in range(min(cnt, 200)):
                ic = loc.nth(i)
                try:
                    name = (await ic.get_attribute("name")) or ""
                except Exception:
                    name = ""
                if name:
                    icons.append(name)
        except Exception:
            pass

        data = {"url": page.url, "tag": tag, "buttons": buttons[:120], "menuitems": menuitems[:80], "icons": icons[:200]}
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"[broll] ui dump saved: {out_path}")
    except Exception as e:
        logger.warning(f"[broll] ui dump failed: {e}")


# Media panel selectors
MEDIA_ICON_SELECTOR = 'iconpark-icon[name="media2"]'
MEDIA_PANEL_HEADER = 'h2'
VIDEO_TAB_NAMES = ['Видео', 'Video']
SOURCE_COMBO_NAMES = ['Источники', 'Sources', 'All', 'Все', 'Getty', 'Storyblocks', 'Pexels']
ORIENTATION_COMBO_NAMES = ['Ориентация', 'Orientation', 'Landscape', 'Горизонтальная', 'Vertical', 'Вертикальная']

SOURCE_MAP = {
    'all': ['Все', 'All'],
    'все': ['Все', 'All'],
    'getty': ['Getty'],
    'storyblocks': ['Storyblocks', 'Storyblock'],
    'pexels': ['Pexels']
}

ORIENTATION_MAP = {
    'horizontal': ['Горизонтальная', 'Horizontal', 'Landscape'],
    'горизонтальная': ['Горизонтальная', 'Horizontal', 'Landscape'],
    'landscape': ['Горизонтальная', 'Horizontal', 'Landscape'],
    'vertical': ['Вертикальная', 'Vertical', 'Portrait'],
    'вертикальная': ['Вертикальная', 'Vertical', 'Portrait'],
    'portrait': ['Вертикальная', 'Vertical', 'Portrait'],
    'square': ['Квадратная', 'Square'],
    'квадратная': ['Квадратная', 'Square']
}

SEARCH_INPUT_SELECTORS = [
    'input[placeholder*="Искать"][placeholder*="онлайн"]',
    'input[placeholder="Искать видео онлайн"]',
    'input[placeholder="Искать Изображение онлайн"]',
    'input[placeholder*="Search"][placeholder*="online"]',
    'input[placeholder="Search videos online"]',
    'input[type="search"]',
    'input[aria-label="Search"]',
    'input[aria-label="Поиск"]',
    'input[placeholder="Search"]',
    'input[placeholder="Поиск"]',
    'input[placeholder="Search assets"]',
    'input[placeholder="Search..."]',
    'input[placeholder*="Search"]',
    'input[placeholder*="Искать"]'
]
RESULT_CARD_SELECTORS = [
    '[role="option"]',
    '[role="listitem"]',
    '[role="button"][aria-label*="video" i]',
    '[role="button"][aria-label*="видео" i]',
]

LEGACY_RESULTS_CARD_SELECTOR = "div.tw-group.tw-relative.tw-overflow-hidden.tw-rounded-md"


def _build_name_regex(names: Iterable[str], *, exact: bool) -> re.Pattern:
    vals = [str(x).strip() for x in (names or []) if str(x).strip()]
    if not vals:
        return re.compile(r"^$\b")
    inner = "|".join(re.escape(v) for v in vals)
    if exact:
        return re.compile(rf"^\s*(?:{inner})\s*$", re.I)
    # Prefix match: allows UI variants like "Landscape (16:9)" or "Getty Images".
    return re.compile(rf"^\s*(?:{inner})(?:\b|\s|$)", re.I)


async def _first_visible(loc) -> Optional["Locator"]:
    try:
        cnt = await loc.count()
    except Exception:
        return None
    for i in range(min(cnt, 40)):
        try:
            cand = loc.nth(i)
            if await cand.is_visible():
                return cand
        except Exception:
            continue
    return None


async def _media_panel_scope(page: "Page") -> "Page | Locator":
    """Try to scope searches to the Media panel container (best-effort)."""
    try:
        header = page.locator(MEDIA_PANEL_HEADER).filter(
            has_text=re.compile(r"^\s*(Медиа|Media)\s*$", re.I)
        )
        if await header.count() == 0:
            return page
        h = header.first
        # Closest reasonable container.
        panel = h.locator(
            "xpath=ancestor::*[self::aside or self::section or self::div][1]"
        )
        if await panel.count() > 0:
            return panel.first
    except Exception:
        pass
    return page


async def _select_from_combobox(
    page: "Page",
    combo_label_names: List[str],
    option_names: List[str],
    what: str,
    gate_callback: Optional[Callable[[], Awaitable[None]]] = None,
) -> bool:
    """Select an option from a labeled combobox using role=combobox + role=listbox.

    Strategy:
    - Locate combobox by accessible name (label) OR by proximity to label text.
    - Open it, wait for a visible listbox.
    - Click option by role=option (preferred), then by text as fallback.
    """
    scope = await _media_panel_scope(page)
    label_re = _build_name_regex(combo_label_names, exact=False)
    option_re = _build_name_regex(option_names, exact=False)
    option_exact_re = _build_name_regex(option_names, exact=True)

    # 1) Preferred: match by visible text on the combobox (most reliable in HeyGen UI).
    combo = None
    try:
        combo = await _first_visible(page.get_by_role("combobox").filter(has_text=label_re))
    except Exception:
        combo = None

    # 2) Next: accessible name matches the label (if it exists).
    if combo is None:
        try:
            combo = await _first_visible(page.get_by_role("combobox", name=label_re))
        except Exception:
            combo = None

    # 3) Fallback: find label text and then the nearest ancestor containing a combobox.
    if combo is None:
        try:
            label_nodes = page.get_by_text(label_re)
            ln_count = await label_nodes.count()
            for i in range(min(ln_count, 6)):
                node = label_nodes.nth(i)
                container = node.locator(
                    "xpath=ancestor::*[.//*[@role='combobox'] or .//button[@role='combobox']][1]"
                )
                cand = container.locator("[role='combobox'], button[role='combobox']")
                combo = await _first_visible(cand)
                if combo is not None:
                    break
        except Exception:
            combo = None

    # 4) Last resort: any visible combobox (prefer panel scope, then full page).
    if combo is None:
        try:
            combo = await _first_visible(scope.get_by_role("combobox"))
        except Exception:
            combo = None
    if combo is None:
        try:
            combo = await _first_visible(page.get_by_role("combobox"))
        except Exception:
            combo = None

    if combo is None:
        logger.warning(f"[broll] {what} combobox not found")
        return False

    # Open combobox and select option.
    for attempt in range(3):
        try:
            if gate_callback:
                await gate_callback()

            listbox_id = None
            try:
                listbox_id = (await combo.get_attribute("aria-controls")) or (await combo.get_attribute("aria-owns"))
                if listbox_id:
                    listbox_id = str(listbox_id).strip()
            except Exception:
                listbox_id = None

            try:
                combo_text = ""
                try:
                    combo_text = (await combo.inner_text()) or ""
                except Exception:
                    combo_text = ""
                logger.info(f"[broll] {what} combobox click: text={combo_text.strip()!r} aria_controls={listbox_id!r}")
            except Exception:
                pass

            if not await safe_click(combo, page, timeout_ms=3500):
                continue

            listbox = None
            if listbox_id:
                try:
                    lb = page.locator(f'[role="listbox"][id="{listbox_id}"]')
                    await lb.first.wait_for(state="visible", timeout=2500)
                    listbox = await _first_visible(lb)
                except Exception:
                    listbox = None

            if listbox is None:
                try:
                    await page.get_by_role("listbox").first.wait_for(state="attached", timeout=2000)
                except Exception:
                    pass
                listbox = await _first_visible(page.get_by_role("listbox"))

            # If we still don't have a listbox, try selecting option by role=option directly.
            if listbox is None:
                opt = await _first_visible(page.get_by_role("option", name=option_re))
                if opt is not None and await safe_click(opt, page, timeout_ms=5000):
                    await random_delay(0.15, 0.25, gate_callback)
                    return True

                opt = await _first_visible(page.locator("div").filter(has_text=option_exact_re))
                if opt is None:
                    opt = await _first_visible(page.locator("div").filter(has_text=option_re))
                if opt is not None and await safe_click(opt, page, timeout_ms=5000):
                    await random_delay(0.15, 0.25, gate_callback)
                    return True

                logger.warning(f"[broll] {what} listbox not visible (attempt {attempt + 1})")
                continue

            # Preferred: role=option within the visible listbox.
            opt = await _first_visible(listbox.get_by_role("option", name=option_re))
            if opt is None:
                # Fallback: text inside listbox.
                try:
                    opt = await _first_visible(listbox.get_by_text(option_re))
                except Exception:
                    opt = None
            if opt is None:
                try:
                    opt = await _first_visible(listbox.locator("div").filter(has_text=option_exact_re))
                except Exception:
                    opt = None
            if opt is None:
                try:
                    opt = await _first_visible(listbox.locator("div").filter(has_text=option_re))
                except Exception:
                    opt = None
            if opt is None:
                opt = await _first_visible(page.locator("div").filter(has_text=option_exact_re))
            if opt is None:
                opt = await _first_visible(page.locator("div").filter(has_text=option_re))

            if opt is None:
                logger.warning(f"[broll] {what} option not found: {option_names}")
                try:
                    items = await listbox.locator("div").all_inner_texts()
                    items = [x.strip() for x in items if str(x).strip()]
                    if items:
                        logger.info(f"[broll] {what} listbox items: {items[:30]}")
                except Exception:
                    pass
                try:
                    await page.keyboard.press("Escape")
                except Exception:
                    pass
                continue

            if await safe_click(opt, page, timeout_ms=5000):
                await random_delay(0.15, 0.25, gate_callback)
                return True
        except Exception as e:
            logger.warning(f"[broll] {what} selection attempt {attempt + 1} failed: {e}")

    try:
        await page.keyboard.press("Escape")
    except Exception:
        pass
    return False


async def open_media_panel(
    page: "Page",
    gate_callback: Optional[Callable[[], Awaitable[None]]] = None,
) -> bool:
    """
    Open the media panel in HeyGen editor.
    
    Args:
        page: Playwright Page object
        gate_callback: Optional pause/cancel callback
        
    Returns:
        True if panel is open or was successfully opened
    """
    # Check if already open
    try:
        panel_header = page.locator(MEDIA_PANEL_HEADER).filter(
            has_text=re.compile(r'^\s*(Медиа|Media)\s*$')
        )
        if await panel_header.count() > 0:
            return True
    except Exception:
        pass
    
    # Try different button candidates
    candidates = []
    
    # Media icon button
    try:
        media_icon = page.locator(MEDIA_ICON_SELECTOR)
        if await media_icon.count() > 0:
            candidates.append(media_icon.first.locator('xpath=ancestor::button[1]'))
    except Exception:
        pass
    
    # Button by role
    try:
        candidates.append(page.get_by_role('button', name=re.compile(r'^\s*(Медиа|Media)\s*$', re.I)))
    except Exception:
        pass
    
    # Button by text
    try:
        candidates.append(page.locator('button').filter(
            has_text=re.compile(r'^\s*(Медиа|Media)\s*$', re.I)
        ).first)
    except Exception:
        pass
    
    for btn in candidates:
        try:
            if await btn.count() == 0:
                continue
        except Exception:
            continue
        
        # Retry logic for clicking the media button
        for attempt in range(2):
            ok = await safe_click(btn, page, timeout_ms=5000)
            
            if gate_callback:
                await gate_callback()
            
            await random_delay(0.2, 0.3, gate_callback)
            
            try:
                panel_header = page.locator(MEDIA_PANEL_HEADER).filter(
                    has_text=re.compile(r'^\s*(Медиа|Media)\s*$')
                )
                if ok and await panel_header.count() > 0:
                    return True
            except Exception:
                pass
    
    return False


async def select_video_tab(
    page: "Page",
    gate_callback: Optional[Callable[[], Awaitable[None]]] = None,
) -> bool:
    """
    Select the Video tab in the media panel.
    
    Args:
        page: Playwright Page object
        gate_callback: Optional pause/cancel callback
        
    Returns:
        True if Video tab is selected
    """
    # Strict verification loop
    # Updated selector to target the tab role specifically
    tab_locator = page.get_by_role("tab", name=re.compile(r"^Video$|^Видео$", re.I))
    
    for attempt in range(3):
        try:
            if gate_callback:
                await gate_callback()
            
            # Wait for tab to be present
            try:
                await tab_locator.first.wait_for(state="attached", timeout=2000)
            except Exception:
                pass
                
            if await tab_locator.count() > 0:
                tab = tab_locator.first
                
                # Check aria-selected first
                is_selected = await tab.get_attribute("aria-selected")
                if is_selected and str(is_selected).lower() == "true":
                    return True
                
                # Click if not selected
                # Using force=True as requested to bypass overlays
                try:
                    await tab.click(timeout=5000, force=True)
                except Exception:
                    await safe_click(tab, page, timeout_ms=5000)
                    
                await asyncio.sleep(1.0) # Wait for UI reaction
                
                # Verify again
                is_selected = await tab.get_attribute("aria-selected")
                if is_selected and str(is_selected).lower() == "true":
                    return True
            else:
                logger.warning(f"[broll] video tab not found, attempt {attempt+1}")
                # Fallback to button if tab role fails
                alt_tab = page.locator("button").filter(
                    has_text=re.compile(r"^Video$|^Видео$", re.I)
                )
                if await alt_tab.count() > 0:
                    await safe_click(alt_tab.first, page, timeout_ms=3000)
                    await asyncio.sleep(1.0)
                
        except Exception as e:
            logger.error(f"[broll] select_video_tab attempt {attempt+1} error: {e}")
            await asyncio.sleep(1.0)
            
    return False


async def select_media_source(
    page: "Page",
    source: str = "all",
    gate_callback: Optional[Callable[[], Awaitable[None]]] = None,
) -> bool:
    """
    Select media source (e.g., Getty, Storyblocks) in the media panel.
    
    Args:
        page: Playwright Page object
        source: Source name ('all', 'getty', 'storyblocks', 'pexels')
        gate_callback: Optional pause/cancel callback
        
    Returns:
        True if source was selected
    """
    if not source or source.lower() in ['all', 'все', '']:
        return True

    key = str(source).strip().lower()
    option_names = SOURCE_MAP.get(key) or [str(source).strip()]
    # Some UIs show only provider names in the dropdown; keep it tight.
    return await _select_from_combobox(
        page=page,
        combo_label_names=SOURCE_COMBO_NAMES,
        option_names=option_names,
        what="Sources",
        gate_callback=gate_callback,
    )


async def select_orientation(
    page: "Page",
    orientation: str = "horizontal",
    gate_callback: Optional[Callable[[], Awaitable[None]]] = None,
) -> bool:
    """
    Select video orientation (Horizontal, Vertical, Square) in the media panel.
    
    Args:
        page: Playwright Page object
        orientation: Orientation ('horizontal', 'vertical', 'square' or raw text)
        gate_callback: Optional pause/cancel callback
        
    Returns:
        True if orientation was selected
    """
    key = str(orientation).strip().lower()
    option_names = ORIENTATION_MAP.get(key) or [str(orientation).strip()]
    return await _select_from_combobox(
        page=page,
        combo_label_names=ORIENTATION_COMBO_NAMES,
        option_names=option_names,
        what="Orientation",
        gate_callback=gate_callback,
    )


async def locate_search_input(page: "Page") -> Optional["Locator"]:
    """
    Find the B-roll search input field.
    
    Args:
        page: Playwright Page object
        
    Returns:
        Locator for the search input, or None if not found
    """
    # Try by role first
    try:
        inp = page.get_by_role("textbox", name=re.compile(
            r"(Искать видео онлайн|Search videos online|Search|Поиск)", re.I
        ))
        if await inp.count() > 0:
            return inp.first
    except Exception:
        pass
    
    # Try various selectors
    for sel in SEARCH_INPUT_SELECTORS:
        try:
            loc = page.locator(sel)
            if await loc.count() > 0:
                return loc.first
        except Exception:
            continue
            
    # Generic fallback for input in the panel
    try:
        # Search inside the Media panel container if possible, or generally on page
        # Usually it has type='text' and is near the top of the panel
        inputs = page.locator('div[role="dialog"] input[type="text"], div[class*="panel"] input[type="text"]').first
        if await inputs.count() > 0:
             return inputs
             
        # Broader fallback
        inputs = page.locator('input[type="text"]').filter(has_text=re.compile(r"Search|Искать", re.I))
        if await inputs.count() > 0:
             return inputs.first
    except Exception:
        pass
    
    return None


async def locate_result_card(page: "Page") -> Optional["Locator"]:
    """
    Find the first B-roll result card.
    
    Args:
        page: Playwright Page object
        
    Returns:
        Locator for a result card, or None if not found
    """
    for sel in RESULT_CARD_SELECTORS:
        try:
            loc = page.locator(sel)
            if await loc.count() > 0:
                return loc.first
        except Exception:
            continue
    
    # Fallback: div with image/video
    try:
        loc = page.locator('div.tw-group').filter(has=page.locator('img, video'))
        if await loc.count() > 0:
            return loc.first
    except Exception:
        pass
    
    try:
        loc = page.locator('[role="button"]').filter(has=page.locator('img, video'))
        if await loc.count() > 0:
            return loc.first
    except Exception:
        pass
    
    return None


async def search_and_select_broll(
    page: "Page",
    query: str,
    timeout_ms: int = 5000,
    gate_callback: Optional[Callable[[], Awaitable[None]]] = None,
) -> bool:
    """
    Search for B-roll and select the first result.
    
    Args:
        page: Playwright Page object
        query: Search query
        timeout_ms: Timeout for results to appear
        gate_callback: Optional pause/cancel callback
        
    Returns:
        True if a result was selected
    """
    search_input = await locate_search_input(page)
    if search_input is None:
        logger.warning("[broll] search input not found")
        return False
    
    # Clear and fill search
    try:
        await search_input.click(timeout=3000)
    except Exception:
        try:
            await search_input.click(timeout=3000, force=True)
        except Exception:
            pass
    
    if gate_callback:
        await gate_callback()
    
    try:
        await page.keyboard.press('Meta+A')
        await asyncio.sleep(0.05)
        await page.keyboard.press('Backspace')
        await asyncio.sleep(0.05)
        await page.keyboard.insert_text(query)
        await asyncio.sleep(0.1)
        await page.keyboard.press('Enter')
    except Exception as e:
        logger.error(f"[broll] search input failed: {e}")
        return False
    
    # Wait for loading state to finish. Wait for `div.tw-grid img` to be visible.
    try:
        # Wait for the grid to appear first
        await page.locator('.tw-grid').first.wait_for(state="visible", timeout=10000)
        # Wait for images to populate
        await page.locator('.tw-grid img').first.wait_for(state="visible", timeout=10000)
    except Exception:
        logger.warning(f"[broll] timed out waiting for results for query: {query}")
        return False
        
    # Add delay after finding results before clicking to ensure UI stability.
    await asyncio.sleep(2.0)
    
    # Click the first result
    try:
        legacy_card = page.locator(LEGACY_RESULTS_CARD_SELECTOR).first
        if await legacy_card.count() > 0:
            logger.info("[broll] clicking first result (legacy tw-group card)")
            try:
                await legacy_card.click(timeout=8000, force=True)
                await random_delay(0.5, 1.0, gate_callback)
                return True
            except Exception:
                try:
                    box = await legacy_card.bounding_box()
                    if box:
                        await page.mouse.click(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5)
                        await random_delay(0.5, 1.0, gate_callback)
                        return True
                except Exception:
                    pass

        grid = page.locator(".tw-grid").first
        thumb = grid.locator('img[draggable="false"][src]').first
        if await thumb.count() > 0:
            logger.info("[broll] clicking first result thumbnail img")
            if await safe_click(thumb, page, timeout_ms=5000):
                await random_delay(0.5, 1.0, gate_callback)
                return True

        if False:
            try:
                await page.locator(".tw-grid").first.wait_for(state="visible", timeout=10000)
            except Exception:
                pass

            target = grid.locator('div.tw-transition-all.tw-cursor-pointer[draggable="false"]').first
            if await target.count() > 0:
                logger.info("[broll] clicking first result (draggable=false transition)")
                if await safe_click(target, page, timeout_ms=5000):
                    await random_delay(0.5, 1.0, gate_callback)
                    return True

            target = grid.locator('div[draggable="false"]').filter(has=page.locator("img, video")).first
            if await target.count() > 0:
                logger.info("[broll] clicking first result (draggable=false fallback)")
                if await safe_click(target, page, timeout_ms=5000):
                    await random_delay(0.5, 1.0, gate_callback)
                    return True

            first_card = grid.locator("> div").first
            if await first_card.count() > 0:
                logger.info("[broll] clicking first result card container (grid > div)")
                if await safe_click(first_card, page, timeout_ms=5000):
                    await random_delay(0.5, 1.0, gate_callback)
                    return True

    except Exception as e:
        logger.error(f"[broll] error clicking result: {e}")
        
    return False



async def click_make_background(
    page: "Page",
    gate_callback: Optional[Callable[[], Awaitable[None]]] = None,
) -> bool:
    """
    Click the "Make Background" / "Сделать фоном" button.
    
    Args:
        page: Playwright Page object
        gate_callback: Optional pause/cancel callback
        
    Returns:
        True if button was clicked
    """
    name_re = re.compile(
        r"(Set as BG|Set as Background|Set as background|Make background|Сделать фоном|Сделать фон)",
        re.I,
    )

    try:
        await page.keyboard.press("Escape")
    except Exception:
        pass
    try:
        await click_canvas_center(page)
        await asyncio.sleep(0.6)
    except Exception:
        pass

    # Wait for button to appear explicitly
    try:
         # Generic waiter for any button that looks like "Set as BG"
         await page.get_by_role("button", name=name_re).first.wait_for(state="visible", timeout=3500)
    except Exception:
         pass

    # Try button by role name (Updated selector)
    try:
        btn = page.get_by_role("button", name=name_re)
        if await btn.count() > 0:
            if await safe_click(btn.first, page, timeout_ms=5000): # reduced timeout as we already waited
                return True
    except Exception:
        pass

    # Try button with text
    make_bg_btn = page.locator("button").filter(
        has_text=name_re
    )
    
    if await make_bg_btn.count() > 0:
        if await safe_click(make_bg_btn.first, page, timeout_ms=5000):
            return True

    try:
        make_bg_div = page.locator('[role="button"], div').filter(has_text=name_re)
        if await make_bg_div.count() > 0:
            if await safe_click(make_bg_div.first, page, timeout_ms=5000):
                return True
    except Exception:
        pass
    
    # Try button with icon
    try:
        # List of potential icons for "Set as Background"
        icon_names = [
            "detachfromframe", "background", "pic", 
            "full-screen-one", "application-one", "layers"
        ]
        for icon in icon_names:
            alt_btns = page.locator(f'button:has(iconpark-icon[name="{icon}"])')
            if await alt_btns.count() > 0:
                # Often the "Set as BG" is the last one or specific one
                # We'll try the last one as it's often on the right of the toolbar
                logger.info(f"[broll] Found button with icon '{icon}'")
                if await safe_click(alt_btns.last, page, timeout_ms=5000):
                    return True
    except Exception:
        pass
    
    # Try menu item
    try:
        menu_item = page.locator("[role='menuitem']").filter(
            has_text=name_re
        )
        if await menu_item.count() > 0:
            if await safe_click(menu_item.first, page, timeout_ms=5000):
                return True
    except Exception:
        pass
        
    # Final fallback: Click canvas center to ensure selection, then try one last time
    # If that fails, try Right Click context menu
    try:
        logger.info("[broll] Set as BG button not found, trying to focus canvas center...")
        
        # 1. Try Left Click to show floating toolbar
        await click_canvas_center(page)
        await asyncio.sleep(1.0)
        
        # Try generic button again
        btn_retry = page.get_by_role("button", name=name_re)
        if await btn_retry.count() > 0:
            if await safe_click(btn_retry.first, page, timeout_ms=5000):
                return True
                
        # 2. Try Right Click for context menu
        logger.info("[broll] Trying Right Click context menu...")
        # Get center coordinates
        viewport = page.viewport_size
        if viewport:
            x, y = viewport["width"] * 0.5, viewport["height"] * 0.5
            # Try to get canvas box if possible
            canvas = page.locator("canvas").first
            if await canvas.count() > 0:
                box = await canvas.bounding_box()
                if box:
                    x = box["x"] + box["width"] * 0.5
                    y = box["y"] + box["height"] * 0.5
            
            # Right click
            await page.mouse.click(x, y, button="right")
            await asyncio.sleep(1.0)
            
            # Look for menu item
            menu_item = page.locator('[role="menuitem"], .context-menu-item').filter(
                has_text=name_re
            )
            if await menu_item.count() > 0:
                logger.info("[broll] Found Set as BG in context menu")
                if await safe_click(menu_item.first, page, timeout_ms=5000):
                    return True
                    
    except Exception as e:
        logger.error(f"[broll] fallback click strategies failed: {e}")
        pass

    try:
        remove_btn = page.locator("button").filter(has_text=re.compile(r"^\s*(Remove|Удалить)\s*$", re.I))
        landscape_btn = page.locator(
            'button[aria-label*="Landscape"], button[aria-label*="Portrait"]'
        )
        if await remove_btn.count() > 0 and await landscape_btn.count() > 0:
            try:
                if await remove_btn.first.is_visible() and await landscape_btn.first.is_visible():
                    logger.info("[broll] background UI detected; treating as already set")
                    return True
            except Exception:
                pass
    except Exception:
        pass

    await _dump_ui_candidates(page, "broll_set_bg_not_found")
    return False


async def wait_for_broll_ready(
    page: "Page",
    min_wait_sec: float = 0.0,
    max_iterations: int = 50,
    gate_callback: Optional[Callable[[], Awaitable[None]]] = None,
) -> bool:
    """
    Wait for B-roll to be applied (no aria-busy elements).
    
    Args:
        page: Playwright Page object
        min_wait_sec: Minimum wait before checking
        max_iterations: Maximum check iterations
        gate_callback: Optional pause/cancel callback
        
    Returns:
        True when ready
    """
    if min_wait_sec > 0:
        await random_delay(min_wait_sec, min_wait_sec + 0.2, gate_callback)
    
    for _ in range(max_iterations):
        busy = page.locator('[aria-busy="true"]')
        try:
            if await busy.count() > 0:
                await random_delay(0.2, 0.3, gate_callback)
                continue
        except Exception:
            pass
        return True
    
    return True


async def try_delete_foreground(
    page: "Page",
    gate_callback: Optional[Callable[[], Awaitable[None]]] = None,
) -> bool:
    """
    Try to delete the foreground layer after B-roll insertion.
    
    Args:
        page: Playwright Page object
        gate_callback: Optional pause/cancel callback
        
    Returns:
        True if deletion was attempted
    """
    try:
        if gate_callback:
            await gate_callback()
            
        # Clear selection first
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        
        # Focus canvas/stage by clicking center
        canvas = page.locator("canvas").first
        clicked = False
        
        if await canvas.count() > 0:
            box = await canvas.bounding_box()
            if box:
                # Click center
                await page.mouse.click(
                    box["x"] + box["width"] * 0.5,
                    box["y"] + box["height"] * 0.5,
                )
                clicked = True
        
        if not clicked:
             # Fallback to viewport center
             vs = page.viewport_size
             if vs:
                 await page.mouse.click(vs["width"] * 0.5, vs["height"] * 0.5)
                 
        await asyncio.sleep(0.5)
        
        # Try Delete
        await page.keyboard.press("Delete")
        await asyncio.sleep(0.5)
        
        # Try Backspace
        await page.keyboard.press("Backspace")
        await asyncio.sleep(0.5)

        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        await asyncio.sleep(0.25)

        avatar_ui = None
        try:
            avatar_ui = page.locator("button").filter(
                has_text=re.compile(r"^\s*(Change avatar|Change look|Replace avatar)\s*$", re.I)
            )
            if await avatar_ui.count() > 0 and await avatar_ui.first.is_visible():
                logger.info("[broll] foreground still present; trying context menu Delete")
            else:
                return True
        except Exception:
            return True

        try:
            canvas = page.locator("canvas").first
            x = y = None
            if await canvas.count() > 0:
                box = await canvas.bounding_box()
                if box:
                    x = box["x"] + box["width"] * 0.5
                    y = box["y"] + box["height"] * 0.5
            if x is None or y is None:
                vs = page.viewport_size
                if vs:
                    x = vs["width"] * 0.5
                    y = vs["height"] * 0.5
            if x is not None and y is not None:
                await page.mouse.click(x, y, button="right")
                await asyncio.sleep(0.6)
                delete_item = page.locator('[role="menuitem"]').filter(
                    has_text=re.compile(r"^\s*(Delete|Удалить)\s*$", re.I)
                )
                if await delete_item.count() > 0:
                    await safe_click(delete_item.first, page, timeout_ms=5000)
                    await asyncio.sleep(0.6)
        except Exception:
            pass

        try:
            if avatar_ui and await avatar_ui.count() > 0 and await avatar_ui.first.is_visible():
                logger.info("[broll] foreground still present after context menu Delete")
                return False
        except Exception:
            pass

        return True
        
    except Exception as e:
        logger.error(f"[broll] delete foreground failed: {e}")
        return False


async def close_media_panel(
    page: "Page",
    gate_callback: Optional[Callable[[], Awaitable[None]]] = None,
) -> bool:
    """
    Close the media panel.
    
    Args:
        page: Playwright Page object
        gate_callback: Optional pause/cancel callback
        
    Returns:
        True if panel was closed
    """
    try:
        # Try clicking the close X button
        close_btn = page.locator('button').filter(
            has=page.locator('iconpark-icon[name="close-one"]')
        )
        if await close_btn.count() > 0:
            await safe_click(close_btn.first, page, timeout_ms=5000)
            return True
    except Exception:
        pass
    
    try:
        # Try pressing Escape
        await page.keyboard.press("Escape")
        return True
    except Exception:
        pass
    
    return False


async def handle_nano_banano(
    page: "Page",
    prompt: str,
    scene_idx: int,
    output_dir: str,
    episode_id: str = "episode",
    part_idx: int = 0,
    gate_callback: Optional[Callable[[], Awaitable[None]]] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Handle Nano Banano image generation and insertion.
    
    Args:
        page: Playwright Page object
        prompt: Image generation prompt
        scene_idx: Scene index
        output_dir: Directory to save generated images
        episode_id: Episode identifier
        part_idx: Part index
        gate_callback: Optional pause/cancel callback
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
        if gate_callback:
            await gate_callback()
        
        logger.info(f"[nano_banano] generating for scene {scene_idx}")
        image_path, mime = await generate_image(
            prompt,
            output_dir,
            episode_id,
            part_idx,
            scene_idx,
        )
        
        logger.info(f"[nano_banano] saved: {image_path}")
        
        try:
            copy_image_to_clipboard(image_path, mime)
        except Exception as e:
            return False, f"clipboard copy failed: {e}"

        from core.browser import click_canvas_center

        if gate_callback:
            await gate_callback()
        await click_canvas_center(page)
        await asyncio.sleep(0.25)

        if gate_callback:
            await gate_callback()
        try:
            await page.keyboard.press("Delete")
        except Exception:
            pass
        try:
            await page.keyboard.press("Backspace")
        except Exception:
            pass

        await asyncio.sleep(0.25)

        if gate_callback:
            await gate_callback()
        await click_canvas_center(page)
        await asyncio.sleep(0.25)

        if gate_callback:
            await gate_callback()
        try:
            await page.keyboard.press("Meta+V")
        except Exception as e:
            return False, f"paste failed: {e}"

        name_re = re.compile(
            r"(Set as BG|Set as Background|Set as background|Make background|Сделать фоном|Сделать фон)",
            re.I,
        )
        btn = page.get_by_role("button", name=name_re)
        waited = False
        try:
            await btn.first.wait_for(state="visible", timeout=6000)
            waited = True
        except Exception:
            await asyncio.sleep(5)

        try:
            if await btn.count() > 0 and await btn.first.is_visible():
                if gate_callback:
                    await gate_callback()
                await btn.first.click(timeout=8000, force=True)
            else:
                if waited:
                    logger.warning("[nano_banano] Set as BG button not visible after wait")
                else:
                    logger.warning("[nano_banano] Set as BG button not found after fallback sleep")
        except Exception as e:
            return False, f"set_as_bg click failed: {e}"

        logger.info(f"[nano_banano] completed for scene {scene_idx}")
        return True, None
        
    except Exception as e:
        logger.error(f"[nano_banano] error: {e}")
        return False, str(e)
