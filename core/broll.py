"""
B-roll handling for HeyGen automation.

Manages media panel interaction, video search, and background insertion.
Includes support for Nano Banano AI-generated images.
"""

import asyncio
import re
from typing import TYPE_CHECKING, Optional, Callable, Awaitable, List, Tuple

from ui.logger import logger
from core.browser import safe_click, random_delay
from utils.clipboard import parse_nano_banano_prompt, generate_image, copy_image_to_clipboard

if TYPE_CHECKING:
    from playwright.async_api import Page, Locator


# Media panel selectors
MEDIA_ICON_SELECTOR = 'iconpark-icon[name="media2"]'
MEDIA_PANEL_HEADER = 'h2'
VIDEO_TAB_NAMES = ['Видео', 'Video']
SOURCE_COMBO_NAMES = ['Источники', 'Sources']
ORIENTATION_COMBO_NAMES = ['Ориентация', 'Orientation']

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
]
RESULT_CARD_SELECTORS = [
    '[role="option"]',
    '[role="listitem"]',
    '[role="button"][aria-label*="video" i]',
    '[role="button"][aria-label*="видео" i]',
]


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
        
        ok = await safe_click(btn, page, timeout_ms=10000)
        
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
    async def _is_active(loc: "Locator") -> bool:
        """Check if a tab/button is in active state."""
        try:
            v = await loc.get_attribute("aria-selected")
            if v and str(v).lower() == "true":
                return True
        except Exception:
            pass
        try:
            v = await loc.get_attribute("data-state")
            if v and str(v).lower() in ("active", "on", "open"):
                return True
        except Exception:
            pass
        return False
    
    # Check if search input is already visible
    try:
        ready = await locate_search_input(page)
        if ready is not None:
            return True
    except Exception:
        pass
    
    for name in VIDEO_TAB_NAMES:
        # Try as tab role
        try:
            tab = page.get_by_role('tab', name=name)
            if await tab.count() > 0:
                if await _is_active(tab.first):
                    return True
                if await safe_click(tab.first, page, timeout_ms=8000):
                    await random_delay(0.15, 0.25, gate_callback)
                    return True
        except Exception:
            pass
        
        # Try as button role
        try:
            btn = page.get_by_role('button', name=name)
            if await btn.count() > 0:
                if await _is_active(btn.first):
                    return True
                if await safe_click(btn.first, page, timeout_ms=8000):
                    await random_delay(0.15, 0.25, gate_callback)
                    return True
        except Exception:
            pass
    
    # Fallback: tab button by text
    try:
        vid_tab = page.locator('button[role="tab"]').filter(
            has_text=re.compile(r'^\s*(Видео|Video)\s*$')
        )
        if await vid_tab.count() > 0:
            if await _is_active(vid_tab.first):
                return True
            if await safe_click(vid_tab.first, page, timeout_ms=8000):
                await random_delay(0.15, 0.25, gate_callback)
                return True
    except Exception:
        pass
    
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
    
    source_key = source.lower()
    targets = SOURCE_MAP.get(source_key, [source])
    
    # Try to find and click the source combobox
    combo_btn = None
    for name in SOURCE_COMBO_NAMES:
        try:
            # Try by role and name
            loc = page.get_by_role("combobox", name=re.compile(rf"^\s*{name}\s*", re.I))
            if await loc.count() > 0:
                combo_btn = loc.first
                break
            
            # Try by text inside button (including nested spans)
            loc = page.locator("button").filter(has_text=re.compile(rf"^\s*{name}\s*", re.I))
            if await loc.count() > 0:
                combo_btn = loc.first
                break
            
            # Try by data-selected-value span
            src_span = page.locator('div[data-selected-value="true"] > span').filter(
                has_text=re.compile(rf'^\s*{name}\s*$', re.I)
            )
            if await src_span.count() > 0:
                combo_btn = src_span.first.locator('xpath=ancestor::button[1]')
                break

            # Try by aria-label
            loc = page.locator(f"button[aria-label*='{name}']")
            if await loc.count() > 0:
                combo_btn = loc.first
                break
        except Exception:
            continue
            
    if not combo_btn:
        logger.warning(f"[broll] source combobox not found")
        return False
        
    if not await safe_click(combo_btn, page, timeout_ms=5000):
        return False
        
    await random_delay(0.1, 0.2, gate_callback)
    
    # Try to click the target option
    try:
        # Get aria-controls to narrow down search if possible
        ctrl_id = await combo_btn.get_attribute("aria-controls")
        if ctrl_id:
            esc_id = ctrl_id.replace(":", "\\:")
            for t in targets:
                opt = page.locator(f"#{esc_id}").locator(f"text={t}")
                if await opt.count() > 0:
                    if await safe_click(opt.first, page, timeout_ms=5000):
                        await random_delay(0.1, 0.15, gate_callback)
                        return True
        
        # Global search for option
        for t in targets:
            opt = page.locator('[role="option"]').filter(has_text=re.compile(rf"^\s*{re.escape(t)}\s*", re.I))
            if await opt.count() > 0:
                if await safe_click(opt.first, page, timeout_ms=5000):
                    await random_delay(0.1, 0.15, gate_callback)
                    return True
    except Exception as e:
        logger.error(f"[broll] error selecting source {source}: {e}")
        
    # Close combo if stuck
    try:
        await page.keyboard.press("Escape")
    except Exception:
        pass
        
    return False


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
    orientation_key = orientation.lower()
    targets = ORIENTATION_MAP.get(orientation_key, [orientation])
    
    # Try to find and click the orientation combobox
    combo_btn = None
    for name in ORIENTATION_COMBO_NAMES:
        try:
            # Try by role and name
            loc = page.get_by_role("combobox", name=re.compile(rf"^\s*{name}\s*", re.I))
            if await loc.count() > 0:
                combo_btn = loc.first
                break
            
            # Try by text inside button (including nested spans)
            loc = page.locator("button").filter(has_text=re.compile(rf"^\s*{name}\s*", re.I))
            if await loc.count() > 0:
                combo_btn = loc.first
                break
        except Exception:
            continue
            
    if not combo_btn:
        logger.warning(f"[broll] orientation combobox not found")
        return False
        
    if not await safe_click(combo_btn, page, timeout_ms=5000):
        return False
        
    await random_delay(0.1, 0.2, gate_callback)
    
    # Wait for dropdown to open
    try:
        combo_open = page.locator('button[role="combobox"][data-state="open"]')
        if await combo_open.count() == 0:
            await random_delay(0.1, 0.15, gate_callback)
    except Exception:
        pass
    
    # Try to click the target option
    try:
        # Get aria-controls to narrow down search if possible
        ctrl_id = await combo_btn.get_attribute("aria-controls")
        if ctrl_id:
            esc_id = ctrl_id.replace(":", "\\:")
            for t in targets:
                opt = page.locator(f"#{esc_id} >> text={t}")
                if await opt.count() > 0:
                    if await safe_click(opt.first, page, timeout_ms=5000):
                        await random_delay(0.1, 0.15, gate_callback)
                        return True
        
        # Global search for option
        for t in targets:
            opt = page.locator('[role="option"]').filter(has_text=re.compile(rf"^\s*{re.escape(t)}\s*", re.I))
            if await opt.count() > 0:
                if await safe_click(opt.first, page, timeout_ms=5000):
                    await random_delay(0.1, 0.15, gate_callback)
                    return True
        
        # Fallback: try Landscape for horizontal
        if orientation_key in ['horizontal', 'горизонтальная', 'landscape']:
            opt_en = page.locator('[role="option"]').filter(has_text=re.compile(r'^\s*Landscape\s*$'))
            if await opt_en.count() > 0:
                if await safe_click(opt_en.first, page, timeout_ms=5000):
                    await random_delay(0.1, 0.15, gate_callback)
                    return True
            
            # Last resort: keyboard navigation
            try:
                await page.keyboard.press('ArrowDown')
                await random_delay(0.05, 0.1, gate_callback)
                await page.keyboard.press('ArrowDown')
                await random_delay(0.05, 0.1, gate_callback)
                await page.keyboard.press('Enter')
                await random_delay(0.1, 0.15, gate_callback)
                return True
            except Exception:
                pass
                
    except Exception as e:
        logger.error(f"[broll] error selecting orientation {orientation}: {e}")
        
    # Close combo if stuck
    try:
        await page.keyboard.press("Escape")
    except Exception:
        pass
        
    return False


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
            r"(Искать видео онлайн|Search videos online)", re.I
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
    
    # Wait for results
    await random_delay(0.5, 1.0, gate_callback)
    
    # Try to find and click a result
    for _ in range(int(timeout_ms / 500)):
        if gate_callback:
            await gate_callback()
        
        result = await locate_result_card(page)
        if result is not None:
            if await safe_click(result, page, timeout_ms=5000):
                await random_delay(0.3, 0.5, gate_callback)
                return True
        
        await asyncio.sleep(0.5)
    
    logger.warning(f"[broll] no results for query: {query}")
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
    # Try button with text
    make_bg_btn = page.locator("button").filter(
        has_text=re.compile(
            r"(Сделать фоном|Сделать фон|Set as background|Make background)", re.I
        )
    )
    
    if await make_bg_btn.count() > 0:
        if await safe_click(make_bg_btn.first, page, timeout_ms=12000):
            return True
    
    # Try button with icon
    try:
        alt_btns = page.locator('button:has(iconpark-icon[name="detachfromframe"])')
        if await alt_btns.count() > 0:
            if await safe_click(alt_btns.last, page, timeout_ms=12000):
                return True
    except Exception:
        pass
    
    # Try menu item
    try:
        menu_item = page.locator("[role='menuitem']").filter(
            has_text=re.compile(
                r"(Сделать фоном|Set as background|Make background)", re.I
            )
        )
        if await menu_item.count() > 0:
            if await safe_click(menu_item.first, page, timeout_ms=12000):
                return True
    except Exception:
        pass
    
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
    clicks = [
        (0.5, 0.5),   # Center
        (0.5, 0.42),  # Upper center
        (0.5, 0.62),  # Lower center
        (0.4, 0.5),   # Left center
        (0.6, 0.5),   # Right center
    ]
    
    pressed = False
    
    for (rx, ry) in clicks:
        try:
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
            
            canvas = page.locator("canvas").first
            box = await canvas.bounding_box()
            
            if box:
                await page.mouse.click(
                    box["x"] + box["width"] * rx,
                    box["y"] + box["height"] * ry,
                )
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
        
        await random_delay(0.2, 0.3, gate_callback)
        
        # Try to press Delete/Backspace
        for key in ("Backspace", "Delete"):
            try:
                await page.keyboard.press(key)
                pressed = True
                break
            except Exception:
                continue
        
        if pressed:
            await random_delay(0.2, 0.3, gate_callback)
            break
    
    return pressed


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
    logger.info(f"[nano_banano] generating for scene {scene_idx}")
    
    try:
        if gate_callback:
            await gate_callback()
        
        # Generate the image
        image_path, mime = await generate_image(
            prompt,
            output_dir,
            episode_id,
            part_idx,
            scene_idx,
        )
        
        logger.info(f"[nano_banano] saved: {image_path}")
        
        # Copy to clipboard
        try:
            copy_image_to_clipboard(image_path, mime)
        except Exception as e:
            return False, f"clipboard copy failed: {e}"
        
        await random_delay(0.2, 0.3, gate_callback)
        
        # Click canvas to focus
        from core.browser import click_canvas_center
        await click_canvas_center(page)
        
        await random_delay(0.1, 0.2, gate_callback)
        
        # Delete existing foreground
        await try_delete_foreground(page, gate_callback)
        
        await random_delay(0.15, 0.25, gate_callback)
        
        # Paste from clipboard
        try:
            if gate_callback:
                await gate_callback()
            await page.keyboard.press("Meta+V")
        except Exception:
            return False, "paste failed"
        
        await random_delay(0.5, 0.7, gate_callback)
        
        # Click make background
        for attempt in range(3):
            if await click_make_background(page, gate_callback):
                await random_delay(0.3, 0.5, gate_callback)
                
                # Wait for it to apply
                await wait_for_broll_ready(page, min_wait_sec=0.3, gate_callback=gate_callback)
                
                # Delete foreground layer
                deleted = await try_delete_foreground(page, gate_callback)
                if deleted:
                    break
            
            await random_delay(0.2, 0.3, gate_callback)
        
        logger.info(f"[nano_banano] completed for scene {scene_idx}")
        return True, None
        
    except Exception as e:
        logger.error(f"[nano_banano] error: {e}")
        return False, str(e)
