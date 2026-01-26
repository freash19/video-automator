import asyncio
import os
import sys
from playwright.async_api import async_playwright, Page, BrowserContext
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

AUTH_STATE_PATH = "debug/auth_state.json"

class AuthManager:
    @staticmethod
    async def login_if_needed(page: Page, context: BrowserContext):
        print("Checking authentication status...")
        try:
            # Use domcontentloaded for faster/safer navigation check
            await page.goto("https://app.heygen.com/projects", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(5000) # Give it time to render/redirect
            
            # Check for login indicators
            login_btn = page.locator("a[href*='login'], button:has-text('Log in'), button:has-text('Sign in')")
            is_login_visible = await login_btn.count() > 0 and await login_btn.first.is_visible()
            
            url = page.url
            if "login" in url or "signin" in url or is_login_visible:
                print("Not logged in. Performing login...")
                email = os.getenv("HEYGEN_LOGIN")
                password = os.getenv("HEYGEN_PASSWORD")
                
                if not email or not password:
                    raise ValueError("HEYGEN_LOGIN and HEYGEN_PASSWORD must be set in .env")
                
                if "login" not in url and "signin" not in url:
                    await page.goto("https://app.heygen.com/login", wait_until="networkidle")
                
                print(f"Logging in as {email}...")
                await page.wait_for_selector("input[type='email'], input[name='email']", timeout=10000)
                await page.fill("input[type='email'], input[name='email']", email)
                
                next_btn = page.locator("button:has-text('Next'), button:has-text('Continue')")
                if await next_btn.count() > 0 and await next_btn.first.is_visible():
                     await next_btn.first.click()
                     await page.wait_for_timeout(1000)

                await page.wait_for_selector("input[type='password']", timeout=10000)
                await page.fill("input[type='password']", password)
                
                submit_btn = page.locator("button[type='submit'], button:has-text('Sign in'), button:has-text('Log in')")
                await submit_btn.first.click()
                
                print("Waiting for login to complete...")
                await page.wait_for_url("**/projects**", timeout=30000)
                
                print("Login successful. Saving auth state...")
                await context.storage_state(path=AUTH_STATE_PATH)
            else:
                print("Already logged in.")
                
        except Exception as e:
            print(f"Authentication failed: {e}")
            raise e

async def main():
    async with async_playwright() as p:
        # Launching with standard settings (Mode 3 from manual_auth)
        browser = await p.chromium.launch(headless=False)
        
        context_args = {
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {"width": 1280, "height": 800},
            "ignore_https_errors": True
        }
        if os.path.exists(AUTH_STATE_PATH):
            print(f"Loading auth state from {AUTH_STATE_PATH}")
            context_args["storage_state"] = AUTH_STATE_PATH
            
        context = await browser.new_context(**context_args)
        
        # Inject script to hide webdriver property (always good practice)
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        page = await context.new_page()
        
        try:
            await AuthManager.login_if_needed(page, context)
            
            print("Navigating to Templates...")
            await page.goto("https://app.heygen.com/templates", wait_until="domcontentloaded", timeout=60000)
            
            # Additional wait for dynamic content
            await page.wait_for_timeout(8000)
            
            target_name = "Well aging Podcast"
            print(f"Searching for template: {target_name}...")
            
            # Debug: take screenshot of templates page
            await page.screenshot(path="debug/templates_page.png")
            print("Saved screenshot to debug/templates_page.png")

            # Try to find the element
            # Note: The text might be in a child element or shadow DOM.
            # We'll search for the text in the entire body content first to see if it exists.
            content = await page.content()
            if target_name not in content:
                print(f"WARNING: Text '{target_name}' not found in page content source.")
            
            template_text = page.locator(f"text={target_name}")
            
            if await template_text.count() > 0:
                print("Found template text element.")
                first_text_el = template_text.first
                
                # Navigate up to find the card container. 
                # Usually the structure is Card -> [Preview Image, Title Section]
                # So we go up until we find a container that looks like a card (e.g. has multiple children)
                
                # Let's try to find the parent that contains both the image and the text
                card_candidate = first_text_el.locator("xpath=..") # Parent
                
                # Check if this parent has a previous sibling (which might be the image)
                # Or if we need to go higher.
                
                # Let's try to hover the element strictly ABOVE the text.
                # We can get the bounding box of the text, and hover x, y-100
                box = await first_text_el.bounding_box()
                if box:
                    print(f"Text bounding box: {box}")
                    # Hover 100px above the center of the text
                    target_x = box["x"] + box["width"] / 2
                    target_y = box["y"] - 100 
                    
                    print(f"Hovering at specific coordinates: ({target_x}, {target_y}) (above text)")
                    await page.mouse.move(target_x, target_y)
                    await page.wait_for_timeout(2000)
                    
                    # Now look for buttons that appeared
                    print("Looking for buttons appearing on hover...")
                    
                    # We look for any 'a' tag or button that is visible now
                    # Common selectors for "Use template"
                    hover_selectors = [
                        "button:has-text('Use this template')",
                        "button:has-text('Create')",
                        "a[href*='editor']",
                        "a[href*='create']",
                        "div[role='button']",
                        ".iconpark-icon" # The user mentioned an icon
                    ]
                    
                    # We need to be careful not to pick up buttons from OTHER cards.
                    # Ideally we scope to the card.
                    # Let's assume the card is the parent of the text (or grandparent)
                    card = first_text_el.locator("xpath=./ancestor::div[contains(@class, 'card') or count(*) > 1][1]")
                    
                    # If we can't find a semantic card, we'll search globally near the mouse or visible elements
                    
                    # Let's try to find a newly visible button specifically.
                    # We can't easily filter by "under mouse", but we can look for buttons that are visible.
                    
                    # Let's try to click the point we hovered!
                    print("Clicking the preview area to see if it triggers navigation or modal...")
                    
                    # We want to catch navigation if it happens
                    try:
                        async with page.expect_navigation(timeout=5000):
                            await page.mouse.click(target_x, target_y)
                        
                        new_url = page.url
                        print(f"Direct click navigated to: {new_url}")
                        return
                    except Exception as e:
                        print(f"Direct click did not trigger immediate navigation (Error: {e}). Checking for modal...")
                        await page.wait_for_timeout(2000)
                
                # If we are here, maybe a modal opened
                modal = page.locator("div[role='dialog']")
                if await modal.count() > 0 and await modal.first.is_visible():
                    print("Modal detected.")
                    await page.screenshot(path="debug/template_modal_v2.png")
                    
                    # Search for the blue button or any create button in the modal
                    # The user mentioned a blue button.
                    modal_buttons = modal.locator("button, a")
                    count = await modal_buttons.count()
                    print(f"Found {count} interactive elements in modal.")
                    
                    for i in range(count):
                        btn = modal_buttons.nth(i)
                        if not await btn.is_visible(): continue
                        
                        txt = await btn.inner_text()
                        html = await btn.evaluate("el => el.outerHTML")
                        href = await btn.get_attribute("href")
                        
                        # Filter for likely candidates
                        is_primary = "bg-brand" in html or "primary" in html or "blue" in html
                        has_create_text = "Create" in txt or "Создать" in txt or "Use" in txt
                        
                        if is_primary or has_create_text:
                            print(f"\nCANDIDATE BUTTON found in modal:")
                            print(f"Text: {txt}")
                            print(f"HTML: {html}")
                            if href:
                                print(f"LINK: {href}")
                                full_url = f"https://app.heygen.com{href}" if href.startswith("/") else href
                                print(f"FULL URL: {full_url}")
                            else:
                                print("No href. Trying to click to get URL...")
                                try:
                                    async with page.expect_navigation(timeout=10000):
                                        await btn.click()
                                    print(f"NAVIGATED TO: {page.url}")
                                    return
                                except Exception as e:
                                    print(f"Click failed or no navigation: {e}")
                            print("-" * 20)
                else:
                    print("No modal detected after click.")
                    
            else:
                print(f"Template '{target_name}' not found on the page.")
                
        except Exception as e:
            print(f"Error: {e}")
            await page.screenshot(path="debug/error.png")

if __name__ == "__main__":
    asyncio.run(main())
