import asyncio
import json
import os

from playwright.async_api import async_playwright


URL = "https://app.heygen.com/create-v4/draft?template_id=0344d8614d484b16a7ab0531560bae91&private=1&sceneDetail=customizeForeground"
AUTH_STATE_PATH = "debug/auth_state.json"


async def read_menuitems(page):
    items = page.get_by_role("menuitem")
    out = []
    n = await items.count()
    for i in range(min(n, 60)):
        it = items.nth(i)
        try:
            if not await it.is_visible():
                continue
        except Exception:
            continue
        try:
            txt = (await it.inner_text()) or ""
        except Exception:
            txt = ""
        txt = " ".join(txt.split())
        if txt:
            out.append(txt)
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

        # Probe mostly the right-side panel where asset/library controls live.
        points = []
        for x in [900, 980, 1060, 1140, 1220]:
            for y in [140, 220, 300, 380, 460, 540, 620, 700]:
                points.append((x, y))

        results = []
        for x, y in points:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(120)
            await page.mouse.click(x, y, button="right")
            await page.wait_for_timeout(450)
            menu = await read_menuitems(page)
            if menu:
                results.append({"x": x, "y": y, "menuitems": menu})
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(120)

        os.makedirs("debug/inspection", exist_ok=True)
        with open("debug/inspection/context_menus_customize_foreground.json", "w", encoding="utf-8") as f:
            json.dump({"url": page.url, "results": results}, f, ensure_ascii=False, indent=2)
        await page.screenshot(path="debug/inspection/context_menus_customize_foreground.png", full_page=True)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())

