import asyncio
import os
import subprocess
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
    cards = page.locator('div.tw-group.tw-relative.tw-overflow-hidden.tw-rounded-md')
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
