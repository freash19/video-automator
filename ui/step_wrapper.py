import functools
import os
import time
import asyncio
from playwright.async_api import Page
from ui.logger import logger

def step(step_name: str):
    """
    Decorator to wrap async methods with logging, error handling, and screenshots.
    
    Args:
        step_name: Name of the step for logging.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            logger.info(f"[{step_name}] start")
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(f"[{step_name}] success duration={duration:.2f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"[{step_name}] failed duration={duration:.2f}s error={str(e)}")
                
                # Attempt to find 'page' object for screenshot
                page = None
                for arg in args:
                    if isinstance(arg, Page):
                        page = arg
                        break
                if not page:
                    for val in kwargs.values():
                        if isinstance(val, Page):
                            page = val
                            break
                
                if page:
                    try:
                        screenshot_dir = "debug/screenshots"
                        os.makedirs(screenshot_dir, exist_ok=True)
                        # Sanitize step name for filename
                        safe_name = "".join(x for x in step_name if x.isalnum() or x in "_-")
                        timestamp = int(time.time())
                        screenshot_path = f"{screenshot_dir}/{safe_name}_{timestamp}.png"
                        await page.screenshot(path=screenshot_path, full_page=True)
                        logger.error(f"[{step_name}] screenshot_saved: {screenshot_path}")
                    except Exception as se:
                        logger.error(f"[{step_name}] screenshot_failed: {se}")
                
                raise e
        return wrapper
    return decorator
