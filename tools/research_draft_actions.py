import asyncio
import json
import os
import re

from playwright.async_api import async_playwright


URL = "https://app.heygen.com/create-v4/draft?template_id=0344d8614d484b16a7ab0531560bae91&private=1"
AUTH_STATE_PATH = "debug/auth_state.json"


async def dump_role_names(page, role: str, contains: list[str]):
    loc = page.get_by_role(role)
    out = []
    n = await loc.count()
    for i in range(min(n, 300)):
        item = loc.nth(i)
        try:
            if not await item.is_visible():
                continue
        except Exception:
            continue
        try:
            name = (await item.get_attribute("aria-label")) or ""
        except Exception:
            name = ""
        try:
            txt = (await item.inner_text()) or ""
        except Exception:
            txt = ""
        hay = (name + " " + txt).strip()
        if not hay:
            continue
        if any(c.lower() in hay.lower() for c in contains):
            out.append({"role": role, "name": name, "text": txt[:200]})
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

        # Click first scene thumbnail if present
        scene_btn = page.get_by_role("button", name=re.compile(r"^1\b"))
        if await scene_btn.count() > 0:
            await scene_btn.first.click()
            await page.wait_for_timeout(3000)

        # Try open context menu on center
        await page.mouse.click(640, 320, button="right")
        await page.wait_for_timeout(1500)

        keywords = [
            "background",
            "set as",
            "foreground",
            "delete",
            "remove",
            "фон",
            "сделать",
            "перед",
            "удал",
        ]
        dump = {
            "url": page.url,
            "buttons": await dump_role_names(page, "button", keywords),
            "menuitems": await dump_role_names(page, "menuitem", keywords),
            "tabs": await dump_role_names(page, "tab", keywords),
            "comboboxes": await dump_role_names(page, "combobox", keywords),
            "listboxes": await dump_role_names(page, "listbox", keywords),
        }
        os.makedirs("debug/inspection", exist_ok=True)
        with open("debug/inspection/draft_actions_dump.json", "w", encoding="utf-8") as f:
            json.dump(dump, f, ensure_ascii=False, indent=2)

        await page.screenshot(path="debug/inspection/draft_actions_state.png", full_page=True)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())

