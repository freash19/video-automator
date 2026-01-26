"""
Scene management for HeyGen automation.

Handles scene filling, text verification, and empty scene deletion.
These functions are extracted from HeyGenAutomation for modularity.
"""

import asyncio
import random
import re
from typing import TYPE_CHECKING, Optional, Callable, Awaitable, List, Dict, Any

from ui.logger import logger
from utils.helpers import normalize_speaker_key, normalize_text_for_compare
from core.browser import safe_click, read_locator_text, fast_replace_text

if TYPE_CHECKING:
    from playwright.async_api import Page, Locator


# Selectors for scene elements
SCENE_TEXT_SELECTOR = 'span[data-node-view-content-react]'
MORE_BUTTON_SELECTOR = 'button:has(iconpark-icon[name="more-level"])'
DELETE_MENU_SELECTOR = 'div[role="menuitem"]'


async def find_scene_locator(
    page: "Page",
    scene_number: int,
) -> Optional["Locator"]:
    """
    Find the locator for a scene's text span.
    
    Args:
        page: Playwright Page object
        scene_number: Scene number (1, 2, 3, ...)
        
    Returns:
        Locator for the scene span, or None if not found
    """
    text_label = f"text_{scene_number}"
    span_locator = page.locator(SCENE_TEXT_SELECTOR).filter(
        has_text=re.compile(rf'^\s*{re.escape(text_label)}\s*$')
    )
    
    try:
        count = await span_locator.count()
        if count > 0:
            return span_locator.first
    except Exception:
        pass
    
    return None


async def select_scene(
    page: "Page",
    locator: "Locator",
    gate_callback: Optional[Callable[[], Awaitable[None]]] = None,
) -> bool:
    """
    Click on a scene to select it for editing.
    
    Args:
        page: Playwright Page object
        locator: Locator for the scene element
        gate_callback: Optional async callback for pause/cancel gates
        
    Returns:
        True if scene was selected successfully
    """
    if gate_callback:
        await gate_callback()
    
    try:
        await locator.scroll_into_view_if_needed()
    except Exception:
        pass
    
    await asyncio.sleep(0.05)
    
    try:
        await page.keyboard.press('Escape')
    except Exception:
        pass
    
    # Try different click strategies
    try:
        await locator.click(timeout=3000)
    except Exception:
        try:
            await locator.click(timeout=3000, force=True)
        except Exception:
            try:
                box = await locator.bounding_box()
                if box:
                    await page.mouse.click(
                        box['x'] + box['width'] / 2,
                        box['y'] + box['height'] / 2,
                    )
                    return True
            except Exception:
                return False
            return False
    
    if gate_callback:
        await gate_callback()
    
    await asyncio.sleep(random.uniform(0.1, 0.2))
    return True


async def insert_text_in_scene(
    page: "Page",
    text: str,
    gate_callback: Optional[Callable[[], Awaitable[None]]] = None,
    enable_enhance_voice: bool = False,
) -> bool:
    """
    Insert text into the currently selected scene.
    
    Args:
        page: Playwright Page object
        text: Text to insert
        gate_callback: Optional async callback for pause/cancel gates
        enable_enhance_voice: Whether to click Enhance Voice button
        
    Returns:
        True if text was inserted successfully
    """
    if gate_callback:
        await gate_callback()
    
    try:
        await page.keyboard.press('Meta+A')
        await asyncio.sleep(0.05)
        await page.keyboard.press('Backspace')
        await asyncio.sleep(random.uniform(0.05, 0.1))
        
        if gate_callback:
            await gate_callback()
        
        await page.keyboard.insert_text(text)
        await asyncio.sleep(random.uniform(0.1, 0.2))
        await page.keyboard.press('Tab')
        await asyncio.sleep(random.uniform(0.1, 0.2))
        
        # Optional: Enhance Voice button
        if enable_enhance_voice:
            try:
                btn = page.locator('button:has(iconpark-icon[name="director-mode"])').filter(
                    has_text=re.compile(r'Enhance Voice|Усилить голос')
                )
                if await btn.count() > 0:
                    await btn.last.click()
                    await asyncio.sleep(0.3)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
        
        return True
    except asyncio.CancelledError:
        raise
    except Exception:
        return False


async def verify_scene_text(
    page: "Page",
    locator: "Locator",
    expected: str,
    attempts: int = 3,
    interval: float = 0.2,
    gate_callback: Optional[Callable[[], Awaitable[None]]] = None,
) -> bool:
    """
    Verify that scene text matches expected value.
    
    Args:
        page: Playwright Page object
        locator: Locator for the scene element
        expected: Expected text content
        attempts: Number of verification attempts
        interval: Delay between attempts
        gate_callback: Optional async callback for pause/cancel gates
        
    Returns:
        True if text matches expected value
    """
    target = str(expected or "").strip()
    if not target:
        return True
    
    for attempt in range(attempts):
        if gate_callback:
            await gate_callback()
        
        if interval > 0:
            await asyncio.sleep(interval)
        
        try:
            matches = page.get_by_text(target, exact=True)
            if await matches.count() > 0:
                return True
        except Exception:
            pass
        
        # First attempt: try to re-fill
        if attempt == 0:
            await fast_replace_text(page, locator, expected, gate_callback)
        else:
            try:
                await page.keyboard.press('Tab')
            except Exception:
                pass
    
    logger.warning(f"[verify_scene] text mismatch after {attempts} attempts")
    return False


async def fill_scene(
    page: "Page",
    scene_number: int,
    text: str,
    speaker: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    gate_callback: Optional[Callable[[], Awaitable[None]]] = None,
    notice_callback: Optional[Callable[[str], None]] = None,
    step_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> bool:
    """
    Fill a specific scene with text.
    
    This is the main entry point for scene filling, combining
    scene selection, text insertion, and optional verification.
    
    Args:
        page: Playwright Page object
        scene_number: Scene number (1, 2, 3, ...)
        text: Text to insert
        speaker: Optional speaker name for logging
        config: Configuration dictionary
        gate_callback: Optional async callback for pause/cancel gates
        notice_callback: Optional callback for status notices
        step_callback: Optional callback for step events
        
    Returns:
        True if scene was filled successfully
    """
    config = config or {}
    text_label = f"text_{scene_number}"
    
    if notice_callback:
        notice_callback(f"✏️ scene_start: scene={scene_number} label={text_label}")
    
    if step_callback:
        step_callback({"type": "start_scene", "scene": scene_number})
    
    try:
        if gate_callback:
            await gate_callback()
        
        # Find the scene locator
        span_locator = page.locator(SCENE_TEXT_SELECTOR).filter(
            has_text=re.compile(rf'^\s*{re.escape(text_label)}\s*$')
        )
        
        count = await span_locator.count()
        if count == 0:
            if notice_callback:
                notice_callback(f"⚠️ scene_field_missing: scene={scene_number}")
            if step_callback:
                step_callback({"type": "finish_scene", "scene": scene_number, "ok": False})
            return False
        
        safe_speaker = normalize_speaker_key(speaker)
        
        # Select the scene
        ok_select = await select_scene(page, span_locator.first, gate_callback)
        if not ok_select:
            if notice_callback:
                notice_callback(f"❌ scene_focus_failed: scene={scene_number}")
            if step_callback:
                step_callback({"type": "finish_scene", "scene": scene_number, "ok": False})
            return False
        
        # Insert the text
        enable_enhance = bool(config.get('enable_enhance_voice', False))
        ok_insert = await insert_text_in_scene(page, text, gate_callback, enable_enhance)
        if not ok_insert:
            if notice_callback:
                notice_callback(f"❌ scene_insert_failed: scene={scene_number}")
            if step_callback:
                step_callback({"type": "finish_scene", "scene": scene_number, "ok": False})
            return False
        
        # Verify (if enabled)
        verify_enabled = config.get('verify_scene_after_insert', True)
        if verify_enabled:
            attempts = int(config.get('checks', {}).get('verify_scene', {}).get('attempts', 3))
            interval = float(config.get('checks', {}).get('verify_scene', {}).get('interval_sec', 0.2))
            
            ok_verify = await verify_scene_text(
                page, span_locator.first, text,
                attempts=attempts,
                interval=interval,
                gate_callback=gate_callback,
            )
            if not ok_verify:
                if notice_callback:
                    notice_callback(f"❌ scene_verify_failed: scene={scene_number}")
                if step_callback:
                    step_callback({"type": "finish_scene", "scene": scene_number, "ok": False})
                return False
        
        if notice_callback:
            notice_callback(f"✅ scene_done: scene={scene_number}")
        if step_callback:
            step_callback({"type": "finish_scene", "scene": scene_number, "ok": True})
        
        return True
        
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error(f"[fill_scene] scene={scene_number} error: {e}")
        if notice_callback:
            notice_callback(f"❌ scene_error: scene={scene_number} err={e}")
        if step_callback:
            step_callback({"type": "finish_scene", "scene": scene_number, "ok": False})
        
        msg = str(e)
        if "Target page, context or browser has been closed" in msg:
            raise
        
        return False


async def delete_empty_scenes(
    page: "Page",
    filled_count: int,
    max_scenes: int = 15,
    gate_callback: Optional[Callable[[], Awaitable[None]]] = None,
    validation_timeout_ms: int = 6000,
    post_reload_wait: float = 1.5,
) -> None:
    """
    Delete all empty scenes after the filled ones.
    
    Args:
        page: Playwright Page object
        filled_count: Number of scenes that have been filled
        max_scenes: Maximum scenes in the template
        gate_callback: Optional async callback for pause/cancel gates
        validation_timeout_ms: Timeout for waiting for elements
        post_reload_wait: Fallback wait time
    """
    empty_scenes = list(range(filled_count + 1, max_scenes + 1))
    
    if not empty_scenes:
        logger.info("[delete_empty_scenes] no empty scenes to delete")
        return
    
    logger.info(f"[delete_empty_scenes] deleting scenes: {empty_scenes}")
    
    if gate_callback:
        await gate_callback()
    
    try:
        await page.wait_for_selector(SCENE_TEXT_SELECTOR, timeout=validation_timeout_ms)
    except asyncio.CancelledError:
        raise
    except Exception:
        await asyncio.sleep(post_reload_wait)
    
    for scene_num in empty_scenes:
        if gate_callback:
            await gate_callback()
        
        try:
            text_label = f"text_{scene_num}"
            
            span_locator = page.locator(f'{SCENE_TEXT_SELECTOR}:has-text("{text_label}")')
            count = await span_locator.count()
            
            if count == 0:
                logger.debug(f"[delete_empty_scenes] scene {text_label} not found, skipping")
                continue
            
            # Click on the scene
            await span_locator.first.scroll_into_view_if_needed()
            try:
                await page.keyboard.press('Escape')
            except Exception:
                pass
            
            if not await safe_click(span_locator.first, page, timeout_ms=3000):
                continue
            
            await asyncio.sleep(random.uniform(0.3, 0.5))
            
            # Click the more button
            more_button = page.locator(MORE_BUTTON_SELECTOR)
            if await more_button.count() == 0:
                logger.warning(f"[delete_empty_scenes] more button not found for {text_label}")
                continue
            
            await safe_click(more_button.last, page, timeout_ms=3000)
            await asyncio.sleep(random.uniform(0.3, 0.5))
            
            # Find and click delete menu item
            delete_item = page.locator(DELETE_MENU_SELECTOR).filter(
                has_text=re.compile(r'Удалить сцену|Delete scene')
            )
            
            try:
                await delete_item.first.wait_for(state='visible', timeout=2000)
            except Exception:
                pass
            
            if await delete_item.count() == 0:
                logger.warning(f"[delete_empty_scenes] delete menu item not found")
                continue
            
            await safe_click(delete_item.first, page, timeout_ms=3000)
            await asyncio.sleep(random.uniform(0.5, 0.8))
            
            logger.info(f"[delete_empty_scenes] deleted scene {scene_num}")
            
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[delete_empty_scenes] error deleting scene {scene_num}: {e}")
            continue
    
    logger.info("[delete_empty_scenes] completed")
