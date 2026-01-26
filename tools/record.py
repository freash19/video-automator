import asyncio
import os
from playwright.async_api import async_playwright

AUTH_STATE_PATH = "debug/auth_state.json"

async def main():
    """
    Launches Playwright with the Inspector enabled (page.pause()), 
    loading the existing authentication state.
    This serves as a programmatic 'playwright codegen'.
    """
    async with async_playwright() as p:
        print("Launching Playwright Inspector with auth state...")
        
        # Launch browser (headed is required for recording)
        # Using args to avoid sandbox issues and detection
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars"
            ]
        )
        
        # Load auth state if exists
        context_args = {
            "viewport": {"width": 1280, "height": 800},
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        if os.path.exists(AUTH_STATE_PATH):
            print(f"Loading auth state from {AUTH_STATE_PATH}")
            context_args["storage_state"] = AUTH_STATE_PATH
        else:
            print(f"Warning: {AUTH_STATE_PATH} not found. You may need to log in manually.")

        context = await browser.new_context(**context_args)
        
        # Inject script to hide webdriver property
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        page = await context.new_page()
        
        print("Navigating to HeyGen Home...")
        try:
            # Go to home or projects to verify login
            await page.goto("https://app.heygen.com/home", timeout=60000)
        except Exception as e:
            print(f"Navigation error (continuing anyway): {e}")

        print("\n" + "="*50)
        print("PLAYWRIGHT INSPECTOR IS OPEN")
        print("1. The browser is now paused.")
        print("2. A 'Playwright Inspector' window should appear.")
        print("3. Click 'Record' in the Inspector to start generating code.")
        print("4. Perform your actions in the browser window.")
        print("5. Copy the generated code from the Inspector.")
        print("="*50 + "\n")

        # page.pause() opens the Inspector and stops execution until resumed/closed
        await page.pause()
        

if __name__ == "__main__":
    asyncio.run(main())
