import asyncio
import os
import subprocess
import re
from typing import List, Optional
from playwright.async_api import async_playwright

async def connect_cdp(cdp_url: str):
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(cdp_url)
        contexts = browser.contexts
        if not contexts:
            return None, None
        context = contexts[0]
        page = await context.new_page()
        return browser, page

async def open_projects(page):
    await page.goto("https://app.heygen.com/projects", wait_until="domcontentloaded", timeout=120000)

async def wait_ready(page, title: str, timeout_ms: int = 300000):
    await page.wait_for_selector(f'div:has-text("{title}")', timeout=timeout_ms)

async def download_video(page, title: str, target_dir: str) -> Optional[str]:
    await page.wait_for_selector(f'div:has-text("{title}")', timeout=60000)
    card = page.locator('div').filter(has_text=title).first
    await card.click()
    await page.wait_for_selector('button:has-text("Download")', timeout=60000)
    btn = page.locator('button:has-text("Download")').last
    async with page.expect_download() as dl:
        await btn.click()
    d = await dl.value
    path = os.path.join(target_dir, await d.suggested_filename())
    await d.save_as(path)
    return path

async def find_episode_parts(page, episode_id: str) -> List[str]:
    await page.goto("https://app.heygen.com/projects", wait_until="domcontentloaded", timeout=120000)
    cards = page.locator('div').filter(has_text=re.compile(re.escape(str(episode_id))))
    total = await cards.count()
    parts = []
    for i in range(total):
        c = cards.nth(i)
        txt = (await c.inner_text()).strip()
        if episode_id in txt and "_part_" in txt:
            parts.append(txt)
    indexes = []
    for t in parts:
        try:
            s = t.split("_part_")[-1]
            s2 = ''.join([ch for ch in s if ch.isdigit()])
            if s2:
                indexes.append(s2)
        except Exception:
            pass
    return sorted(list(set(indexes)), key=lambda x: int(x))

def ffmpeg_concat(inputs: List[str], intro: Optional[str], output_path: str, preset: str = "medium", crf: int = 23) -> int:
    lst_path = os.path.join(os.getcwd(), "concat_list.txt")
    lines = []
    if intro:
        lines.append(f"file '{intro}'\n")
    for p in inputs:
        lines.append(f"file '{p}'\n")
    with open(lst_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst_path,
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-c:a", "aac", output_path
    ]
    r = subprocess.run(cmd)
    try:
        os.remove(lst_path)
    except Exception:
        pass
    return r.returncode


def ffmpeg_concat_advanced(
    inputs: List[str],
    output_path: str,
    bitrate_kbps: int = 5000,
    resolution: str = "1080p",
    video_codec: str = "h264",
    audio_codec: str = "aac",
    intro: Optional[str] = None
) -> int:
    """
    Advanced video concatenation with configurable quality settings.
    
    Args:
        inputs: List of input video file paths
        output_path: Output file path
        bitrate_kbps: Video bitrate in kbps (2000, 5000, 8000, 15000)
        resolution: Output resolution ("720p", "1080p", "4k", "original")
        video_codec: Video codec ("h264", "h265")
        audio_codec: Audio codec ("aac", "mp3")
        intro: Optional intro video to prepend
    
    Returns:
        FFmpeg return code (0 = success)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Create concat list file
    lst_path = os.path.join(os.getcwd(), "concat_list.txt")
    lines = []
    
    if intro and os.path.isfile(intro):
        lines.append(f"file '{os.path.abspath(intro)}'\n")
    
    for p in inputs:
        if os.path.isfile(p):
            lines.append(f"file '{os.path.abspath(p)}'\n")
        else:
            logger.warning(f"Input file not found: {p}")
    
    if not lines:
        logger.error("No valid input files provided")
        return 1
    
    with open(lst_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    
    # Build FFmpeg command
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst_path]
    
    # Video codec
    if video_codec == "h265":
        cmd.extend(["-c:v", "libx265"])
    else:
        cmd.extend(["-c:v", "libx264"])
    
    # Video bitrate
    cmd.extend(["-b:v", f"{bitrate_kbps}k"])
    
    # Resolution scaling
    resolution_map = {
        "720p": "scale=-2:720",
        "1080p": "scale=-2:1080",
        "4k": "scale=-2:2160",
    }
    
    if resolution in resolution_map:
        cmd.extend(["-vf", resolution_map[resolution]])
    # "original" = no scaling
    
    # Preset for encoding speed/quality tradeoff
    if video_codec == "h265":
        cmd.extend(["-preset", "medium"])
    else:
        cmd.extend(["-preset", "medium"])
    
    # Audio codec
    if audio_codec == "mp3":
        cmd.extend(["-c:a", "libmp3lame", "-b:a", "192k"])
    else:
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])
    
    # Output file
    cmd.append(output_path)
    
    logger.info(f"Running FFmpeg: {' '.join(cmd)}")
    
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        
        if r.returncode != 0:
            logger.error(f"FFmpeg failed: {r.stderr}")
        else:
            logger.info(f"Successfully created: {output_path}")
        
        return r.returncode
        
    except Exception as e:
        logger.error(f"FFmpeg execution error: {e}")
        return 1
    finally:
        try:
            os.remove(lst_path)
        except Exception:
            pass


def get_video_duration(file_path: str) -> Optional[float]:
    """
    Get video duration in seconds using ffprobe.
    
    Args:
        file_path: Path to video file
    
    Returns:
        Duration in seconds, or None if failed
    """
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception:
        pass
    return None


def get_video_info(file_path: str) -> Optional[dict]:
    """
    Get video information using ffprobe.
    
    Args:
        file_path: Path to video file
    
    Returns:
        Dictionary with video info (duration, size, resolution, etc.)
    """
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            
            format_info = data.get("format", {})
            video_stream = None
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    video_stream = stream
                    break
            
            info = {
                "duration": float(format_info.get("duration", 0)),
                "size": int(format_info.get("size", 0)),
                "bitrate": int(format_info.get("bit_rate", 0)),
            }
            
            if video_stream:
                info["width"] = video_stream.get("width")
                info["height"] = video_stream.get("height")
                info["codec"] = video_stream.get("codec_name")
            
            return info
    except Exception:
        pass
    return None


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours}:{mins:02d}:{secs:02d}"
