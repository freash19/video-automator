"""
Video scraper for HeyGen projects page.
Collects video metadata (title, duration, creation date, download URL) from up to 30 videos.
Skips drafts (videos with "Черновик" badge).
"""

import asyncio
import logging
import re
import uuid
from typing import List, Dict, Optional
from datetime import datetime
from playwright.async_api import Page, Locator

logger = logging.getLogger(__name__)


async def scrape_heygen_videos(
    page: Page,
    max_count: int = 30,
    already_scraped_titles: Optional[set] = None
) -> List[Dict]:
    """
    Scrape video metadata from HeyGen projects page.
    
    Strategy based on user-provided selectors:
    1. Find video cards by "Avatar Video" marker
    2. For each card extract:
       - Title from span element inside card
       - Duration from text like "40s" or "1:23"
       - Created time from text like "8 часов назад"
    3. Skip cards with "Черновик" (draft)
    4. Hover to reveal menu button, click for Download option
    
    Args:
        page: Playwright page instance (should be logged in to HeyGen)
        max_count: Maximum number of videos to scrape (default 30)
        already_scraped_titles: Set of titles to skip (already in database)
    
    Returns:
        List of video info dictionaries
    """
    if already_scraped_titles is None:
        already_scraped_titles = set()
    
    videos = []
    processed_titles = set()
    
    try:
        # Navigate to projects page
        logger.info("Navigating to HeyGen projects page...")
        await page.goto("https://app.heygen.com/projects", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(4)  # Wait for dynamic content
        
        logger.info("Starting video scraping on HeyGen projects page")
        
        # Scroll to load more videos
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(0.5)
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(1)
        
        # Find all video cards by "Avatar Video" marker
        avatar_markers = page.get_by_text("Avatar Video")
        total_cards = await avatar_markers.count()
        logger.info(f"Found {total_cards} 'Avatar Video' markers (video cards) on page")
        
        if total_cards == 0:
            logger.warning("No videos found on the page")
            return []
        
        scraped_count = 0
        
        for idx in range(min(total_cards, max_count * 2)):  # Process more to account for drafts
            if scraped_count >= max_count:
                break
                
            try:
                # Get the card container - go up from Avatar Video marker to the card
                marker = avatar_markers.nth(idx)
                
                # Find parent card container (several levels up)
                card = marker.locator("xpath=ancestor::div[contains(@class, 'cursor-pointer') or contains(@class, 'group')]").first
                
                if not await card.count():
                    # Alternative: go up fixed levels
                    card = marker.locator("xpath=ancestor::div[6]")
                
                if not await card.count():
                    logger.debug(f"Could not find card container for index {idx}")
                    continue
                
                # Check for draft - skip if "Черновик" present
                try:
                    card_text = await card.inner_text(timeout=2000)
                    if "Черновик" in card_text:
                        logger.debug(f"Skipping draft at index {idx}")
                        continue
                except Exception:
                    pass
                
                # Extract TITLE from span element inside card
                # Based on user info: locator("span").filter(has_text="ep_sauna_danger_p1")
                title = None
                try:
                    # Find span elements in the card that could be titles
                    spans = card.locator("span")
                    span_count = await spans.count()
                    
                    for si in range(span_count):
                        span = spans.nth(si)
                        try:
                            span_text = await span.inner_text(timeout=1000)
                            span_text = span_text.strip()
                            
                            # Skip empty, known UI text, time markers, durations
                            if not span_text:
                                continue
                            if span_text in ("Avatar Video", "Черновик", "•"):
                                continue
                            if re.match(r'^\d+s$', span_text):  # Duration like "40s"
                                continue
                            if re.match(r'^\d+:\d+$', span_text):  # Duration like "1:23"
                                continue
                            if re.match(r'^\d+\s*(час|минут|секунд|день|дн|недел)', span_text):  # Time ago
                                continue
                            
                            # This looks like a title
                            if len(span_text) > 1:
                                title = span_text
                                break
                        except Exception:
                            continue
                except Exception as e:
                    logger.debug(f"Error extracting title from spans: {e}")
                
                if not title:
                    title = f"Video_{idx}"
                
                # Skip if already processed
                if title in processed_titles or title in already_scraped_titles:
                    logger.debug(f"Skipping already processed: {title}")
                    continue
                
                # Extract DURATION - text like "40s" or "1:23"
                duration = ""
                try:
                    # Look for duration pattern in card
                    dur_elem = card.get_by_text(re.compile(r'^(\d+s|\d+:\d{2})$'))
                    if await dur_elem.count() > 0:
                        duration = await dur_elem.first.inner_text(timeout=1000)
                        duration = duration.strip()
                except Exception:
                    pass
                
                # Extract CREATED TIME - text like "8 часов назад"
                created_at = ""
                try:
                    # Look for time ago pattern
                    time_elem = card.get_by_text(re.compile(r'\d+\s*(час|минут|секунд|день|дн|недел)[а-яё]*\s*назад'))
                    if await time_elem.count() > 0:
                        created_at = await time_elem.first.inner_text(timeout=1000)
                        created_at = created_at.strip()
                except Exception:
                    pass
                
                # Try to get download URL via hover menu (menu appears on hover, no click)
                download_url = None
                try:
                    # Hover over card - menu appears automatically
                    await card.hover()
                    await asyncio.sleep(0.5)
                    
                    # Look for Download option that appeared on hover
                    download_option = page.locator("div").filter(has_text=re.compile(r"^Download$")).first
                    
                    if await download_option.is_visible(timeout=1000):
                        # Get href if it's a link
                        href = await download_option.get_attribute("href")
                        if href:
                            download_url = href
                    
                    # Move mouse away to close menu
                    await page.mouse.move(0, 0)
                    await asyncio.sleep(0.2)
                except Exception as e:
                    logger.debug(f"Could not get download URL from hover menu: {e}")
                    try:
                        await page.mouse.move(0, 0)
                    except Exception:
                        pass
                
                # Create video info
                video_info = {
                    "id": str(uuid.uuid4()),
                    "title": title,
                    "created_at": created_at or datetime.now().isoformat(),
                    "duration": duration,
                    "download_url": download_url,
                    "status": "ready",
                    "file_path": None,
                    "size": None
                }
                
                videos.append(video_info)
                processed_titles.add(title)
                scraped_count += 1
                
                logger.info(f"Scraped video {scraped_count}/{max_count}: {title} ({duration}) - {created_at}")
                
            except Exception as e:
                logger.warning(f"Error processing card {idx}: {e}")
                continue
        
        logger.info(f"Scraping complete. Found {len(videos)} videos")
        return videos
        
    except Exception as e:
        logger.error(f"Error during video scraping: {e}")
        import traceback
        traceback.print_exc()
        return videos


def _extract_title_from_card(card_text: str) -> Optional[str]:
    """Extract video title from card text."""
    if not card_text:
        return None
    
    lines = [l.strip() for l in card_text.split('\n') if l.strip()]
    
    # First pass: look for title before time markers
    for line in lines:
        # Skip known non-title lines
        if line in ("Черновик", "Avatar Video", "•", ""):
            continue
        
        # Skip lines that are just time markers
        if re.match(r'^\d+\s*(?:час|минут|секунд|день|дн|недел)[а-яё]*\s*назад', line):
            continue
            
        if "Avatar Video" in line:
            # Parse line like "40sep_sauna_danger_p17 часов назад•Avatar Video"
            # or "ep_name1 час назад•Avatar Video"
            # First try to extract everything before the time marker
            
            # Pattern: optional duration + title + time ago + Avatar Video
            # Example: "40sep_sauna_danger_p17 часов назад•Avatar Video"
            match = re.match(
                r'^(?:(\d+s|\d+:\d+)\s*)?(.+?)\s*(\d+\s*(?:час|минут|секунд|день|дн|недел)[а-яё]*\s*назад).*Avatar Video',
                line
            )
            if match:
                title = match.group(2).strip()
                # Clean up title - remove trailing special chars
                title = re.sub(r'[•\s]+$', '', title)
                if title and len(title) > 1:
                    return title
            
            # Try simpler: split by time marker
            time_match = re.search(r'(\d+\s*(?:час|минут|секунд|день|дн|недел)[а-яё]*\s*назад)', line)
            if time_match:
                before_time = line[:time_match.start()].strip()
                # Remove duration prefix
                before_time = re.sub(r'^(\d+s|\d+:\d+)\s*', '', before_time)
                if before_time and len(before_time) > 1:
                    return before_time.strip()
            
            # Last resort: split by •
            parts = line.split("•")
            if parts:
                first_part = parts[0].strip()
                # Remove duration prefix
                first_part = re.sub(r'^(\d+s|\d+:\d+)\s*', '', first_part)
                if first_part and len(first_part) > 1:
                    return first_part.strip()
        else:
            # This line might be the title itself
            # Check if it looks like a valid title (not just numbers or duration)
            clean = re.sub(r'^(\d+s|\d+:\d+)\s*', '', line)  # Remove duration prefix
            clean = re.sub(r'\s*(\d+\s*(?:час|минут|секунд|день|дн|недел)[а-яё]*\s*назад).*$', '', clean)  # Remove time suffix
            clean = clean.strip()
            
            if clean and len(clean) > 1 and not re.match(r'^\d+$', clean):
                return clean
    
    return None


def _extract_duration_and_date(card_text: str) -> tuple[str, str]:
    """Extract duration and creation date from card text."""
    duration = ""
    created_at = ""
    
    # Duration pattern: "40s" or "1:23" or "1:23:45"
    dur_match = re.search(r'(\d{1,2}:\d{2}(?::\d{2})?|\d+s)', card_text)
    if dur_match:
        duration = dur_match.group(1)
    
    # Date pattern: "X минут/часов/дней назад"
    date_match = re.search(r'(\d+\s*(?:минут|час|секунд|день|дн|недел)[а-яё]*\s*назад)', card_text)
    if date_match:
        created_at = date_match.group(1)
    
    return duration, created_at


async def _extract_video_info_from_dialog(page: Page, fallback_title: str) -> Optional[Dict]:
    """
    Extract video metadata from the download dialog.
    
    Expected dialog structure (from user's screenshot):
    - Tabs: "Видео" and "Субтитры"
    - Video preview on the left
    - Title, duration (e.g. "40s"), creation date on the right
    - Example: "ep_sauna_danger_p1 40s 25 января 2026 г. в 18:34"
    - "Скачать" button at bottom
    """
    try:
        await asyncio.sleep(0.5)  # Wait for dialog to fully render
        
        title = fallback_title
        duration = ""
        created_at = ""
        download_url = None
        
        # Try to get dialog text
        dialog_text = ""
        
        # Look for the download dialog - it should have "Видео" tab and "Скачать" button
        try:
            # Try to find dialog by looking for "Видео" and "Субтитры" tabs
            dialog_area = page.locator("div").filter(has_text="Видео").filter(has_text="Субтитры").first
            if await dialog_area.is_visible(timeout=2000):
                dialog_text = await dialog_area.inner_text(timeout=3000)
        except Exception:
            pass
        
        # Alternative: try to get text from any modal/dialog
        if not dialog_text:
            for selector in ['div[role="dialog"]', '[class*="modal"]', '[class*="overlay"]', '[class*="popup"]']:
                try:
                    elem = page.locator(selector).first
                    if await elem.is_visible(timeout=1000):
                        dialog_text = await elem.inner_text(timeout=2000)
                        if dialog_text and len(dialog_text) > 10:
                            break
                except Exception:
                    continue
        
        logger.debug(f"Dialog text: {dialog_text[:200] if dialog_text else 'empty'}...")
        
        if dialog_text:
            # Extract duration - pattern like "40s" at the start of text or standalone
            dur_match = re.search(r'(\d{1,2}:\d{2}(?::\d{2})?|\d+s)', dialog_text)
            if dur_match:
                duration = dur_match.group(1)
            
            # Extract creation date - Russian format
            date_match = re.search(
                r'(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4}\s*г?\.?\s*(?:в\s+\d{1,2}:\d{2})?)',
                dialog_text
            )
            if date_match:
                created_at = date_match.group(1).strip()
            
            # Try to extract better title from dialog
            # Pattern: "title 40s date" or similar
            lines = dialog_text.split('\n')
            for line in lines:
                line = line.strip()
                # Skip UI elements
                if line in ("Видео", "Субтитры", "Скачать", "Расширенные настройки", ""):
                    continue
                # Check if line contains title + duration + date
                match = re.match(r'^([a-zA-Z0-9_\-\.]+(?:[\s_][a-zA-Z0-9_\-\.]+)*)\s*(\d+s|\d+:\d+)', line)
                if match:
                    title = match.group(1).strip()
                    if not duration:
                        duration = match.group(2)
                    break
        
        # Try to get download URL from the dialog's download button
        try:
            dialog_download_btn = page.get_by_role("button", name="Скачать").last  # The one in dialog, not page
            if await dialog_download_btn.is_visible(timeout=1000):
                # Check for href or data-url
                href = await dialog_download_btn.get_attribute("href")
                if href:
                    download_url = href
                else:
                    # Check parent link
                    parent_link = dialog_download_btn.locator("xpath=ancestor::a[1]")
                    if await parent_link.count():
                        href = await parent_link.get_attribute("href")
                        if href:
                            download_url = href
        except Exception:
            pass
        
        # Also try to find any download links in the dialog
        if not download_url:
            try:
                download_links = page.locator('a[href*=".mp4"], a[href*="download"], a[download]')
                count = await download_links.count()
                for i in range(count):
                    href = await download_links.nth(i).get_attribute("href")
                    if href and (".mp4" in href or "download" in href.lower()):
                        download_url = href
                        break
            except Exception:
                pass
        
        return {
            "id": str(uuid.uuid4()),
            "title": title,
            "created_at": created_at or datetime.now().isoformat(),
            "duration": duration,
            "download_url": download_url,
            "status": "ready",
            "file_path": None,
            "size": None
        }
        
    except Exception as e:
        logger.error(f"Error extracting video info from dialog: {e}")
        return {
            "id": str(uuid.uuid4()),
            "title": fallback_title,
            "created_at": datetime.now().isoformat(),
            "duration": "",
            "download_url": None,
            "status": "ready",
            "file_path": None,
            "size": None
        }


async def download_single_video(
    page: Page,
    video_title: str,
    download_dir: str
) -> Optional[str]:
    """
    Download a single video by title using hover menu.
    
    Strategy:
    1. Find video card by title (partial match in span elements)
    2. Hover to reveal menu button
    3. Click menu button to open dropdown
    4. Click "Download" option
    
    Args:
        page: Playwright page instance
        video_title: Title of the video to download
        download_dir: Directory to save the downloaded file
    
    Returns:
        Path to the downloaded file, or None if download failed
    """
    import os
    
    try:
        # Navigate to projects page
        await page.goto("https://app.heygen.com/projects", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        # Strategy: Find span with the video title directly
        # Based on user info: locator("span").filter(has_text="ep_sauna_danger_p1")
        
        logger.info(f"Searching for video with title: '{video_title}'")
        
        # Find the title span directly
        title_span = page.locator("span").filter(has_text=video_title).first
        
        try:
            if not await title_span.is_visible(timeout=5000):
                logger.error(f"Could not find span with title: {video_title}")
                return None
        except Exception:
            logger.error(f"Could not find video with title: {video_title}")
            return None
        
        logger.info(f"Found title span for: {video_title}")
        
        # Get parent card container (go up several levels from the span)
        found_card = title_span.locator("xpath=ancestor::div[contains(@class, 'group') or contains(@class, 'cursor')]").first
        
        if not await found_card.count():
            # Try alternative - just go up 4-5 levels
            found_card = title_span.locator("xpath=ancestor::div[5]")
        
        if not await found_card.count():
            # Last resort - use the span itself for hovering
            found_card = title_span
        
        os.makedirs(download_dir, exist_ok=True)
        
        # METHOD 0: Try clicking directly on the title span to open video
        try:
            logger.info("Trying to click on title span directly...")
            title_span = page.locator("span").filter(has_text=video_title).first
            
            if await title_span.is_visible(timeout=2000):
                await title_span.click()
                await asyncio.sleep(2.5)
                
                # Check if we're on video page by looking for download button
                download_btn = page.get_by_role("button", name="Скачать").first
                if await download_btn.is_visible(timeout=3000):
                    logger.info("Opened video page via title click, proceeding to download...")
                    
                    # Click download button to open dialog
                    await download_btn.click()
                    await asyncio.sleep(1.5)
                    
                    # Find and click download button in dialog
                    dialog_download_btn = page.get_by_role("button", name="Скачать").last
                    
                    if await dialog_download_btn.is_visible(timeout=2000):
                        async with page.expect_download(timeout=120000) as download_info:
                            await dialog_download_btn.click()
                        
                        download = await download_info.value
                        suggested_name = download.suggested_filename
                        file_path = os.path.join(download_dir, suggested_name)
                        await download.save_as(file_path)
                        
                        logger.info(f"Downloaded video via title click to: {file_path}")
                        return file_path
        except Exception as e:
            logger.debug(f"Title click method failed: {e}")
            try:
                await page.keyboard.press("Escape")
                await page.goto("https://app.heygen.com/projects", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)
            except Exception:
                pass
        
        # METHOD 1: Hover on card - menu appears automatically (no click needed)
        try:
            logger.info("Trying hover method - menu should appear on hover...")
            
            # Hover over card to reveal dropdown menu (appears automatically)
            await found_card.hover()
            await asyncio.sleep(1.0)  # Wait for menu to appear
            
            # Look for Download option that appears on hover (no click needed to show menu)
            download_option = None
            
            # Try to find Download in the dropdown that appeared
            # Based on user: locator("div").filter(has_text="Download").nth(3)
            try:
                download_option = page.locator("div").filter(has_text=re.compile(r"^Download$")).first
                if await download_option.is_visible(timeout=2000):
                    logger.info("Download option found on hover!")
                else:
                    download_option = None
            except Exception:
                pass
            
            # Try Russian version
            if not download_option:
                try:
                    download_option = page.locator("div").filter(has_text=re.compile(r"^Скачать$")).first
                    if await download_option.is_visible(timeout=1000):
                        logger.info("Скачать option found on hover!")
                    else:
                        download_option = None
                except Exception:
                    pass
            
            if download_option:
                logger.info("Clicking Download option...")
                # Start download
                async with page.expect_download(timeout=120000) as download_info:
                    await download_option.click()
                
                download = await download_info.value
                
                # Save the file
                suggested_name = download.suggested_filename
                file_path = os.path.join(download_dir, suggested_name)
                await download.save_as(file_path)
                
                logger.info(f"Downloaded video via hover menu to: {file_path}")
                return file_path
            else:
                logger.info("Download option not visible after hover, trying alternative...")
        except Exception as e:
            logger.warning(f"Hover method failed: {e}")
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
        
        # METHOD 2: Fallback - click on card and use dialog
        logger.info("Trying fallback method: click card and use download dialog")
        
        try:
            await found_card.click()
            await asyncio.sleep(2.5)
            
            # Wait for download button (try Russian first, then English)
            download_btn = None
            
            try:
                download_btn = page.get_by_role("button", name="Скачать").first
                await download_btn.wait_for(state="visible", timeout=8000)
                logger.info("Found 'Скачать' button")
            except Exception:
                try:
                    download_btn = page.get_by_role("button", name="Download").first
                    await download_btn.wait_for(state="visible", timeout=5000)
                    logger.info("Found 'Download' button")
                except Exception:
                    logger.error("Could not find download button on video page")
                    await page.goto("https://app.heygen.com/projects", wait_until="domcontentloaded", timeout=30000)
                    return None
            
            # Click download button to open dialog
            await download_btn.click()
            await asyncio.sleep(1.5)
            
            # Find download button in dialog (last Скачать/Download button)
            dialog_download_btn = None
            
            try:
                dialog_download_btn = page.get_by_role("button", name="Скачать").last
                if await dialog_download_btn.is_visible(timeout=2000):
                    logger.info("Found dialog 'Скачать' button")
                else:
                    dialog_download_btn = None
            except Exception:
                pass
            
            if not dialog_download_btn:
                try:
                    dialog_download_btn = page.get_by_role("button", name="Download").last
                    if await dialog_download_btn.is_visible(timeout=2000):
                        logger.info("Found dialog 'Download' button")
                    else:
                        dialog_download_btn = None
                except Exception:
                    pass
            
            if not dialog_download_btn:
                logger.error("Could not find download button in dialog")
                await page.keyboard.press("Escape")
                await page.goto("https://app.heygen.com/projects", wait_until="domcontentloaded", timeout=30000)
                return None
            
            # Start download
            async with page.expect_download(timeout=120000) as download_info:
                await dialog_download_btn.click()
            
            download = await download_info.value
            
            # Save the file
            suggested_name = download.suggested_filename
            file_path = os.path.join(download_dir, suggested_name)
            await download.save_as(file_path)
            
            logger.info(f"Downloaded video via dialog to: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Dialog download failed: {e}")
            try:
                await page.keyboard.press("Escape")
                await page.goto("https://app.heygen.com/projects", wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass
            return None
        
    except Exception as e:
        logger.error(f"Error downloading video '{video_title}': {e}")
        import traceback
        traceback.print_exc()
        return None


async def download_video_by_url(
    download_url: str,
    download_dir: str,
    filename: str
) -> Optional[str]:
    """
    Download a video directly from URL using aiohttp.
    
    Args:
        download_url: Direct download URL
        download_dir: Directory to save the file
        filename: Name for the downloaded file
    
    Returns:
        Path to the downloaded file, or None if download failed
    """
    import os
    import aiohttp
    
    try:
        os.makedirs(download_dir, exist_ok=True)
        file_path = os.path.join(download_dir, filename)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(download_url) as response:
                if response.status == 200:
                    with open(file_path, 'wb') as f:
                        while True:
                            chunk = await response.content.read(8192)
                            if not chunk:
                                break
                            f.write(chunk)
                    
                    logger.info(f"Downloaded video to: {file_path}")
                    return file_path
                else:
                    logger.error(f"Download failed with status {response.status}")
                    return None
                    
    except Exception as e:
        logger.error(f"Error downloading video from URL: {e}")
        return None
