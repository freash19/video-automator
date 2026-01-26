import asyncio
import time
import os
from playwright.async_api import async_playwright

AUTH_STATE_PATH = "debug/auth_state.json"

async def main():
    async with async_playwright() as p:
        print("Launching Chromium for manual authentication (SSL Ignores Enabled)...")
        
        # Using bundled Chromium with aggressive SSL error ignoring
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox", 
                "--ignore-certificate-errors",
                "--ignore-ssl-errors",
                "--allow-insecure-localhost",
                "--disable-web-security" # Helps with some strict CORS/SSL issues in testing
            ]
        )

        context_args = {
            "ignore_https_errors": True,
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {"width": 1280, "height": 800}
        }
        
        if os.path.exists(AUTH_STATE_PATH):
            print(f"Loading existing auth state from {AUTH_STATE_PATH}")
            context_args["storage_state"] = AUTH_STATE_PATH

        context = await browser.new_context(**context_args)
        
        # Inject script to hide webdriver property
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        page = await context.new_page()
        
        print("Navigating to login page...")
        try:
            await page.goto("https://app.heygen.com", timeout=60000)
        except Exception as e:
            print(f"Navigation error (might be ignored if page loaded partially): {e}")

        print("\n" + "="*50)
        print("BROWSER IS OPEN FOR MANUAL INTERACTION.")
        print("1. Log in if needed.")
        print("2. Change language settings or perform other actions.")
        print("3. Close the browser window when done.")
        print("State will be saved periodically.")
        print("="*50 + "\n")
        
        # Wait for user to close browser
        # 30 minutes timeout
        max_wait = 1800 
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                if page.is_closed():
                    print("Browser page was closed.")
                    break
                
                # Periodically save state
                await context.storage_state(path=AUTH_STATE_PATH)
                
                await asyncio.sleep(2)
            except Exception as e:
                print(f"Error checking status: {e}")
                break
        
        print("Final state save...")
        try:
            await context.storage_state(path=AUTH_STATE_PATH)
            print(f"SUCCESS: State saved to {AUTH_STATE_PATH}")
        except Exception as e:
            print(f"Error saving final state: {e}")


if __name__ == "__main__":
    asyncio.run(main())
