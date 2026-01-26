import asyncio
import time
from playwright.async_api import async_playwright

AUTH_STATE_PATH = "debug/auth_state.json"

async def launch_and_wait(p, mode_name, launch_kwargs, context_kwargs):
    print(f"\n{'='*20} Launching Browser: {mode_name} {'='*20}")
    print("Instructions:")
    print("1. Try to log in manually.")
    print("2. If successful, wait for redirect to '/projects' or '/home'.")
    print("3. If this mode FAILS (e.g., SSL error, insecure browser warning):")
    print("   -> CLOSE THE BROWSER WINDOW MANUALLY.")
    print("   -> The script will detect the closure and try the next mode.")
    print(f"{'='*60}\n")

    try:
        browser = await p.chromium.launch(**launch_kwargs)
        context = await browser.new_context(**context_kwargs)
        
        # Always inject webdriver hide script
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        page = await context.new_page()
        
        try:
            print(f"[{mode_name}] Navigating to login page...")
            await page.goto("https://app.heygen.com/login", timeout=30000)
        except Exception as e:
            print(f"[{mode_name}] Navigation warning: {e}")

        login_detected = False
        login_start = None
        max_wait = 1800
        while True:
            if page.is_closed():
                if login_detected:
                    print(f"[{mode_name}] Browser closed by user. Finishing login flow.")
                    return True
                print(f"[{mode_name}] Browser closed by user. Moving to next mode (if any)...")
                return False

            if login_detected:
                if login_start is not None and time.time() - login_start > max_wait:
                    print(f"[{mode_name}] Timeout while waiting for manual close. Closing browser.")
                    return True
            else:
                try:
                    url = page.url
                    if "projects" in url or "home" in url:
                        print(f"\n[{mode_name}] SUCCESS! Login detected at: {url}")
                        print(f"[{mode_name}] Saving auth state to {AUTH_STATE_PATH}...")
                        import os
                        os.makedirs(os.path.dirname(AUTH_STATE_PATH), exist_ok=True)
                        await context.storage_state(path=AUTH_STATE_PATH)
                        print(f"[{mode_name}] State saved. Close the browser window when done.")
                        login_detected = True
                        login_start = time.time()
                except Exception:
                    pass
            
            await asyncio.sleep(1)

    except Exception as e:
        print(f"[{mode_name}] Error launching/running: {e}")
        return False

async def main():
    async with async_playwright() as p:
        
        # Mode 1: Stealth + SSL Ignore (Most likely to work for automation-blocked sites)
        success = await launch_and_wait(
            p,
            "Mode 1: Stealth + Ignore SSL",
            launch_kwargs={
                "headless": False,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--ignore-certificate-errors",
                    "--ignore-ssl-errors",
                    "--allow-insecure-localhost",
                    "--disable-web-security"
                ]
            },
            context_kwargs={
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "viewport": {"width": 1280, "height": 800},
                "ignore_https_errors": True
            }
        )
        if success: return

        # Mode 2: System Chrome (Best for Google Sign-In)
        success = await launch_and_wait(
            p,
            "Mode 2: System Chrome (Try Google Auth)",
            launch_kwargs={
                "headless": False,
                "channel": "chrome",
                "args": ["--no-sandbox"],
                "ignore_default_args": ["--enable-automation"]
            },
            context_kwargs={
                "viewport": {"width": 1280, "height": 800}
            }
        )
        if success: return

        # Mode 3: Clean/Standard (Fallback)
        success = await launch_and_wait(
            p,
            "Mode 3: Standard Chromium",
            launch_kwargs={
                "headless": False
            },
            context_kwargs={}
        )
        if success: return

        print("\nAll modes failed or were skipped. Please check your network or try a different approach.")

if __name__ == "__main__":
    asyncio.run(main())
