import asyncio
import json
import os
import re

from playwright.async_api import async_playwright


URL = "https://app.heygen.com/create-v4/draft?template_id=0344d8614d484b16a7ab0531560bae91&private=1"
AUTH_STATE_PATH = "debug/auth_state.json"


async def first_visible(locator):
    n = await locator.count()
    for i in range(n):
        cand = locator.nth(i)
        try:
            if await cand.is_visible():
                return cand
        except Exception:
            continue
    return None


async def dump_locators(page, selector: str, limit: int = 200):
    loc = page.locator(selector)
    n = await loc.count()
    out = []
    for i in range(min(n, limit)):
        el = loc.nth(i)
        try:
            if not await el.is_visible():
                continue
        except Exception:
            continue
        payload = await el.evaluate(
            """(node) => ({
              tag: node.tagName.toLowerCase(),
              role: node.getAttribute('role') || '',
              id: node.id || '',
              testId: node.getAttribute('data-testid') || '',
              ariaLabel: node.getAttribute('aria-label') || '',
              ariaControls: node.getAttribute('aria-controls') || '',
              ariaOwns: node.getAttribute('aria-owns') || '',
              name: node.getAttribute('name') || '',
              placeholder: node.getAttribute('placeholder') || '',
              text: (node.innerText || '').trim().slice(0, 200),
            })"""
        )
        out.append(payload)
    return out


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            storage_state=AUTH_STATE_PATH if os.path.exists(AUTH_STATE_PATH) else None,
            ignore_https_errors=True,
        )
        page = await context.new_page()
        await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(15000)

        scene_btn = page.get_by_role("button", name=re.compile(r"^1\b"))
        s = await first_visible(scene_btn)
        if s:
            await s.click()
            await page.wait_for_timeout(1500)

        customize = page.get_by_role("button", name=re.compile(r"Customize|Настроить", re.I))
        c = await first_visible(customize)
        if c:
            await c.click()
            await page.wait_for_timeout(2000)

        # Try to open first combobox to materialize listbox
        combo = await first_visible(page.get_by_role("combobox"))
        if combo:
            try:
                await combo.click()
                await page.wait_for_timeout(800)
            except Exception:
                pass

        dump = {
            "url": page.url,
            "buttons": await dump_locators(page, '[role="button"],button', limit=250),
            "tabs": await dump_locators(page, '[role="tab"]', limit=100),
            "menuitems": await dump_locators(page, '[role="menuitem"]', limit=100),
            "combobox": await dump_locators(page, '[role="combobox"],input[role="combobox"],input[aria-controls]', limit=50),
            "listbox": await dump_locators(page, '[role="listbox"],[role="option"]', limit=100),
        }
        os.makedirs("debug/inspection", exist_ok=True)
        with open("debug/inspection/customize_dom_dump.json", "w", encoding="utf-8") as f:
            json.dump(dump, f, ensure_ascii=False, indent=2)
        await page.screenshot(path="debug/inspection/customize_dom_dump.png", full_page=True)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())

