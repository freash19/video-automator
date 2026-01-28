import asyncio
import json
import os
import argparse
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Page, BrowserContext
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
DEBUG_DIR = "debug/inspection"
AUTH_STATE_PATH = "debug/auth_state.json"
REPORT_PATH = f"{DEBUG_DIR}/report_custom.json"
SCREENSHOT_PATH = f"{DEBUG_DIR}/screenshot_custom.png"

# Ensure directories exist
os.makedirs(DEBUG_DIR, exist_ok=True)

class AuthManager:
    @staticmethod
    async def login_if_needed(page: Page, context: BrowserContext):
        print("Checking authentication status...")
        try:
            await page.goto("https://app.heygen.com/projects", wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            
            url = page.url
            if "login" in url or "signin" in url:
                print("Not logged in. Performing login...")
                email = os.getenv("HEYGEN_LOGIN")
                password = os.getenv("HEYGEN_PASSWORD")
                
                if not email or not password:
                    raise ValueError("HEYGEN_LOGIN and HEYGEN_PASSWORD must be set in .env")
                
                if "login" not in url:
                    await page.goto("https://app.heygen.com/login", wait_until="networkidle")
                
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

async def scan_page(page: Page):
    print("Scanning DOM...")
    elements = await page.evaluate("""
        () => {
            const results = [];
            
            function isInteractive(el) {
                const tag = el.tagName.toLowerCase();
                const style = window.getComputedStyle(el);
                
                if (['button', 'a', 'input', 'select', 'textarea'].includes(tag)) return true;
                if (el.getAttribute('role') === 'button') return true;
                if (el.getAttribute('role') === 'option') return true;
                if (el.getAttribute('role') === 'listitem') return true;
                if (el.hasAttribute('data-testid')) return true;
                if (el.hasAttribute('aria-label')) return true;
                if (style.cursor === 'pointer') return true;
                
                return false;
            }

            function getIconName(element) {
                // Check for iconpark-icon in children
                const icon = element.querySelector('iconpark-icon');
                if (icon) return icon.getAttribute('name');
                
                // Check for svg
                const svg = element.querySelector('svg');
                if (svg) return 'svg';
                
                return '';
            }
            
            function getXPath(element) {
                if (element.id !== '')
                    return 'id("' + element.id + '")';
                if (element === document.body)
                    return element.tagName;

                var ix = 0;
                try {
                    var siblings = element.parentNode.childNodes;
                    for (var i = 0; i < siblings.length; i++) {
                        var sibling = siblings[i];
                        if (sibling === element)
                            return getXPath(element.parentNode) + '/' + element.tagName + '[' + (ix + 1) + ']';
                        if (sibling.nodeType === 1 && sibling.tagName === element.tagName)
                            ix++;
                    }
                } catch (e) {
                    return '';
                }
            }

            function traverse(root) {
                const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
                let node = walker.nextNode();
                while(node) {
                    if (isInteractive(node)) {
                            const rect = node.getBoundingClientRect();
                            const style = window.getComputedStyle(node);
                            if (rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none') {
                                results.push({
                                tagName: node.tagName.toLowerCase(),
                                text: node.innerText ? node.innerText.substring(0, 100).replace(/\\n/g, ' ') : '',
                                iconName: getIconName(node),
                                href: node.getAttribute('href') || '',
                                testId: node.getAttribute('data-testid') || '',
                                ariaLabel: node.getAttribute('aria-label') || '',
                                role: node.getAttribute('role') || '',
                                class: node.className || '',
                                xpath: getXPath(node),
                                rect: {
                                    x: rect.x + window.scrollX,
                                    y: rect.y + window.scrollY,
                                    width: rect.width,
                                    height: rect.height
                                }
                            });
                            }
                    }
                    
                    if (node.shadowRoot) {
                        traverse(node.shadowRoot);
                    }
                    
                    node = walker.nextNode();
                }
            }
            
            traverse(document.body);
            
            return results;
        }
    """)
    
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(elements, f, indent=2, ensure_ascii=False)
    print(f"Report saved to {REPORT_PATH}")
    
    await page.screenshot(path=SCREENSHOT_PATH, full_page=True)
    print(f"Screenshot saved to {SCREENSHOT_PATH}")

async def main():
    url = "https://app.heygen.com/create-v4/draft?template_id=39d48e33d44041bba2a3415d86488ffb&private=1"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            storage_state=AUTH_STATE_PATH if os.path.exists(AUTH_STATE_PATH) else None
        )
        page = await context.new_page()
        
        await AuthManager.login_if_needed(page, context)
        
        print(f"Navigating to {url}...")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(10000) # Wait for editor to load
        
        # 1. Click Media
        print("Looking for Media button...")
        try:
            # Try finding the sidebar Media button
            media_btn = page.locator('div[role="button"]:has-text("Media"), div[role="button"]:has-text("Медиа")')
            if await media_btn.count() == 0:
                 media_btn = page.locator('button:has(iconpark-icon[name="media2"])')
            
            if await media_btn.count() > 0:
                print("Clicking Media button...")
                await media_btn.first.click()
                await page.wait_for_timeout(3000)
            else:
                print("Media button not found!")
        except Exception as e:
            print(f"Error clicking Media: {e}")

        # 2. Click Video Tab (if needed, usually default or accessible)
        print("Looking for Video tab...")
        try:
             video_tab = page.locator('div[role="tab"]:has-text("Video"), div[role="tab"]:has-text("Видео")')
             if await video_tab.count() > 0:
                 print("Clicking Video tab...")
                 await video_tab.first.click()
                 await page.wait_for_timeout(2000)
        except Exception as e:
             print(f"Error clicking Video tab: {e}")
             
        # 3. Click first available media item (Image/Video)
        print("Clicking first media item...")
        try:
            # Try to click the first image/video card in the grid
            # Based on report, items are in a grid.
            # We'll try to click a div that contains an image or has a specific class
            
            # Wait for grid to load
            await page.wait_for_selector('.tw-grid', timeout=10000)
            
            # Click the first item
            items = page.locator('.tw-grid > div')
            if await items.count() > 0:
                print(f"Found {await items.count()} items. Clicking first...")
                await items.first.click()
                await page.wait_for_timeout(5000) # Wait for canvas update
            else:
                 print("No items found in grid.")
                 
        except Exception as e:
            print(f"Error clicking item: {e}")
            # Fallback: try clicking by xpath from report if grid selector fails
            try:
                # Use a known xpath prefix from report or similar
                # .../DIV[3]/DIV[2]/DIV[1]/DIV[1]/DIV[2]/DIV[1] ...
                pass
            except:
                pass

        # Scan 1: After adding element
        print("Scanning DOM (Post-Add)...")
        await scan_page(page)
        
        # Try Right Click on Canvas
        print("Attempting Right Click on Canvas center...")
        try:
             # Click center of viewport as a proxy for canvas center
             viewport = page.viewport_size
             if viewport:
                 # Center of the canvas area (left of the media panel)
                 # Media panel starts around x=900. Canvas is to the left.
                 x = 450
                 y = 400
                 await page.mouse.click(x, y, button="right")
                 print("Right clicked. Waiting for menu...")
                 await page.wait_for_timeout(2000)
                 
                 # Scan 2: After Right Click
                 print("Scanning DOM (Post-Right-Click)...")
                 global REPORT_PATH
                 REPORT_PATH = f"{DEBUG_DIR}/report_context_menu.json"
                 await scan_page(page)
        except Exception as e:
             print(f"Error right clicking: {e}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
