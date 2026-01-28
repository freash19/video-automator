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

        # Enter first scene if present
        scene_btn = page.get_by_role("button", name=re.compile(r"^1\b"))
        s = await first_visible(scene_btn)
        if s:
            await s.click()
            await page.wait_for_timeout(1500)

        # Try open Customize
        customize = page.get_by_role("button", name=re.compile(r"Customize|Настроить", re.I))
        c = await first_visible(customize)
        if c:
            await c.click()
            await page.wait_for_timeout(2000)

        # Collect candidate actions by role
        keywords = [
            "Set as Background",
            "Background",
            "Foreground",
            "Delete",
            "Remove",
            "Сделать фоном",
            "Фон",
            "Передний",
            "Удал",
        ]

        def has_kw(s: str) -> bool:
            ss = (s or "").lower()
            return any(k.lower() in ss for k in keywords)

        found = []
        for role in ["menuitem", "button", "tab", "option", "combobox", "listbox"]:
            loc = page.get_by_role(role)
            n = await loc.count()
            for i in range(min(n, 200)):
                it = loc.nth(i)
                try:
                    if not await it.is_visible():
                        continue
                except Exception:
                    continue
                try:
                    text = (await it.inner_text()) or ""
                except Exception:
                    text = ""
                try:
                    aria = (await it.get_attribute("aria-label")) or ""
                except Exception:
                    aria = ""
                label = " ".join((aria + " " + text).split())
                if label and has_kw(label):
                    found.append({"role": role, "label": label[:200]})

        # Combobox -> listbox linkage
        combo = await first_visible(page.get_by_role("combobox"))
        linkage = None
        if combo:
            aria_controls = await combo.get_attribute("aria-controls")
            aria_owns = await combo.get_attribute("aria-owns")
            linkage = {
                "aria-controls": aria_controls,
                "aria-owns": aria_owns,
            }
            # Also dump referenced element role, if any
            ref_id = aria_controls or aria_owns
            if ref_id:
                # Radix часто генерирует id с ':' и др. спецсимволами — безопаснее искать по [id="..."]
                ref = page.locator(f"[id={json.dumps(ref_id)}]")
                linkage["ref_count"] = await ref.count()
                if await ref.count() > 0:
                    linkage["ref_role"] = await ref.first.get_attribute("role")

        os.makedirs("debug/inspection", exist_ok=True)
        with open("debug/inspection/customize_and_combobox_dump.json", "w", encoding="utf-8") as f:
            json.dump(
                {"url": page.url, "found": found, "combobox_linkage": linkage},
                f,
                ensure_ascii=False,
                indent=2,
            )
        await page.screenshot(path="debug/inspection/customize_and_combobox.png", full_page=True)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
