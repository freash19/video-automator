import asyncio
from typing import Dict
from playwright.async_api import async_playwright

async def test_selector(cdp_url: str, url: str, selector: str, timeout_ms: int = 10000) -> Dict[str, int]:
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0]
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        if selector.startswith("get_by_role("):
            role = selector.split("get_by_role('")[1].split("'")[0]
            name = selector.split("name='")[1].split("'")[0]
            loc = page.get_by_role(role, name=name)
        else:
            loc = page.locator(selector)
        cnt = await loc.count()
        return {"count": cnt}

def build_by_text(tag: str, text: str) -> str:
    return f"{tag}:has-text(\"{text}\")"

def build_by_role(role: str, name: str) -> str:
    return f"get_by_role('{role}', name='{name}')"

def build_by_icon(name: str) -> str:
    return f"iconpark-icon[name=\"{name}\"]"

async def highlight_selector(cdp_url: str, url: str, selector: str, timeout_ms: int = 10000) -> Dict[str, int]:
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0]
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        if selector.startswith("get_by_role("):
            role = selector.split("get_by_role('")[1].split("'")[0]
            name = selector.split("name='")[1].split("'")[0]
            loc = page.get_by_role(role, name=name)
        else:
            loc = page.locator(selector)
        cnt = await loc.count()
        for i in range(cnt):
            el = loc.nth(i)
            try:
                await el.evaluate("el => { el.style.outline='3px solid #e91e63'; el.style.outlineOffset='2px'; el.scrollIntoView({behavior:'smooth',block:'center'}); }")
            except Exception:
                pass
        return {"count": cnt}

