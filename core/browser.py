"""
Browser interaction utilities for Playwright automation.

Provides robust click, scroll, and keyboard interaction helpers
with fallback strategies for handling edge cases.
"""

import asyncio
import os
import random
import time
from typing import TYPE_CHECKING, Optional, Tuple, List

from ui.logger import logger

if TYPE_CHECKING:
    from playwright.async_api import Page, Locator


async def safe_click(
    loc: "Locator",
    page: "Page",
    timeout_ms: int = 8000,
) -> bool:
    """
    Robust click with fallback strategies.
    
    Tries in order:
    1. Normal click
    2. Scroll into view + click
    3. Force click
    4. JavaScript click via element handle
    
    Args:
        loc: Playwright Locator to click
        page: Playwright Page object
        timeout_ms: Click timeout in milliseconds
        
    Returns:
        True if click succeeded, False otherwise
    """
    # Try scroll into view first
    try:
        await loc.scroll_into_view_if_needed()
    except asyncio.CancelledError:
        raise
    except Exception:
        pass
    
    # Try normal click
    try:
        await loc.click(timeout=timeout_ms)
        return True
    except asyncio.CancelledError:
        raise
    except Exception:
        pass
    
    # Try force click
    try:
        await loc.click(timeout=timeout_ms, force=True)
        return True
    except asyncio.CancelledError:
        raise
    except Exception:
        pass
    
    # Try JavaScript click
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


async def scroll_into_view(loc: "Locator") -> bool:
    """
    Scroll an element into the visible viewport.
    
    Args:
        loc: Playwright Locator to scroll to
        
    Returns:
        True if scroll succeeded
    """
    try:
        await loc.scroll_into_view_if_needed()
        return True
    except asyncio.CancelledError:
        raise
    except Exception:
        return False


async def read_locator_text(locator: "Locator") -> str:
    """
    Read text content from a locator, trying multiple methods.
    
    Args:
        locator: Playwright Locator to read from
        
    Returns:
        Text content or empty string
    """
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


async def fast_replace_text(
    page: "Page",
    locator: "Locator",
    text: str,
    gate_callback=None,
) -> None:
    """
    Quickly replace text in an input field using keyboard shortcuts.
    
    Uses Cmd+A to select all, then types the new text.
    
    Args:
        page: Playwright Page object
        locator: Locator of the input field
        text: New text to insert
        gate_callback: Optional async callback to check for pause/cancel
    """
    try:
        await locator.scroll_into_view_if_needed()
    except Exception:
        pass
    
    # Try to click and focus
    try:
        await locator.click(timeout=3000)
    except Exception:
        try:
            await locator.click(timeout=3000, force=True)
        except Exception:
            pass
    
    if gate_callback:
        await gate_callback()
    
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


async def click_canvas_center(page: "Page") -> bool:
    """
    Click the center of the canvas element.
    
    Used for focusing on scene content area.
    
    Args:
        page: Playwright Page object
        
    Returns:
        True if click succeeded
    """
    try:
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        
        canvas = page.locator("canvas").first
        box = await canvas.bounding_box()
        
        if box:
            await page.mouse.click(
                box["x"] + box["width"] * 0.5,
                box["y"] + box["height"] * 0.5,
            )
            return True
        
        # Fallback to viewport center
        vs = page.viewport_size
        if vs:
            await page.mouse.click(vs["width"] * 0.5, vs["height"] * 0.5)
            return True
    except Exception:
        pass
    
    return False


async def click_canvas_positions(
    page: "Page",
    positions: List[Tuple[float, float]],
    delay_sec: float = 0.2,
) -> bool:
    """
    Click multiple positions on the canvas.
    
    Args:
        page: Playwright Page object
        positions: List of (x_ratio, y_ratio) tuples (0.0-1.0)
        delay_sec: Delay between clicks
        
    Returns:
        True if any click succeeded
    """
    clicked = False
    
    for (rx, ry) in positions:
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
                clicked = True
            else:
                vs = page.viewport_size
                if vs:
                    await page.mouse.click(vs["width"] * rx, vs["height"] * ry)
                    clicked = True
        except Exception:
            try:
                vs = page.viewport_size
                if vs:
                    await page.mouse.click(vs["width"] * rx, vs["height"] * ry)
                    clicked = True
            except Exception:
                pass
        
        if clicked and delay_sec > 0:
            await asyncio.sleep(delay_sec)
            break
    
    return clicked


async def wait_for_not_busy(
    page: "Page",
    max_iterations: int = 50,
    delay_sec: float = 0.2,
) -> bool:
    """
    Wait until no elements have aria-busy="true".
    
    Args:
        page: Playwright Page object
        max_iterations: Maximum number of checks
        delay_sec: Delay between checks
        
    Returns:
        True when no busy elements found
    """
    for _ in range(max_iterations):
        busy = page.locator('[aria-busy="true"]')
        try:
            if await busy.count() > 0:
                await asyncio.sleep(delay_sec)
                continue
        except Exception:
            pass
        return True
    
    return True


async def capture_screenshot(
    page: "Page",
    name: str,
    output_dir: str = "debug/screenshots",
) -> Optional[str]:
    """
    Capture a screenshot for debugging.
    
    Args:
        page: Playwright Page object
        name: Name for the screenshot file
        output_dir: Directory to save screenshots
        
    Returns:
        Path to saved screenshot, or None if failed
    """
    try:
        if not page:
            return None
        
        os.makedirs(output_dir, exist_ok=True)
        safe = "".join(ch for ch in str(name) if ch.isalnum() or ch in "_-")
        ts = int(time.time() * 1000)
        path = f"{output_dir}/{safe}_{ts}.png"
        
        await page.screenshot(path=path, full_page=True)
        logger.info(f"[screenshot] saved: {path}")
        return path
    except Exception as e:
        logger.error(f"[screenshot] failed: {e}")
        return None


async def random_delay(
    min_sec: float = 0.25,
    max_sec: float = 0.55,
    gate_callback=None,
) -> None:
    """
    Wait for a random duration, respecting pause gates.
    
    Args:
        min_sec: Minimum delay in seconds
        max_sec: Maximum delay in seconds
        gate_callback: Optional async callback to check for pause/cancel
    """
    try:
        if gate_callback:
            await gate_callback()
        
        if min_sec < 0:
            min_sec = 0.0
        if max_sec < min_sec:
            max_sec = min_sec
        
        remaining = random.uniform(min_sec, max_sec)
        
        while remaining > 0:
            if gate_callback:
                await gate_callback()
            chunk = 0.2 if remaining > 0.2 else remaining
            await asyncio.sleep(chunk)
            remaining -= chunk
    except asyncio.CancelledError:
        raise
    except Exception:
        try:
            await asyncio.sleep(min_sec if min_sec else 0.1)
        except Exception:
            pass
