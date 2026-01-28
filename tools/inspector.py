import asyncio
import json
import os
import sys
import argparse
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright, Page, BrowserContext, ElementHandle
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
DEBUG_DIR = "debug/inspection"
AUTH_STATE_PATH = "debug/auth_state.json"
REPORT_PATH = f"{DEBUG_DIR}/report.json"
SCREENSHOT_PATH = f"{DEBUG_DIR}/screenshot.png"
ANNOTATED_PATH = f"{DEBUG_DIR}/annotated.png"

# Ensure directories exist
os.makedirs(DEBUG_DIR, exist_ok=True)
os.path.dirname(AUTH_STATE_PATH) and os.makedirs(os.path.dirname(AUTH_STATE_PATH), exist_ok=True)

class AuthManager:
    @staticmethod
    async def login_if_needed(page: Page, context: BrowserContext):
        """
        Checks if the user is logged in. If not, performs login using env vars.
        """
        print("Checking authentication status...")
        try:
            # Go to a protected page to check redirect
            await page.goto("https://app.heygen.com/projects", wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)  # Wait for redirects
            
            url = page.url
            if "login" in url or "signin" in url:
                print("Not logged in. Performing login...")
                email = os.getenv("HEYGEN_LOGIN")
                password = os.getenv("HEYGEN_PASSWORD")
                
                if not email or not password:
                    raise ValueError("HEYGEN_LOGIN and HEYGEN_PASSWORD must be set in .env")
                
                # Assume we are on login page or redirect to it
                if "login" not in url:
                    await page.goto("https://app.heygen.com/login", wait_until="networkidle")
                
                # Fill credentials (adjust selectors as needed for HeyGen)
                # These are generic selectors, might need adjustment based on actual UI
                print(f"Logging in as {email}...")
                
                # Attempt to find email input
                await page.wait_for_selector("input[type='email'], input[name='email']", timeout=10000)
                await page.fill("input[type='email'], input[name='email']", email)
                
                # Check if password field is visible or if we need to click "Next"
                # Some flows: Email -> Next -> Password
                next_btn = page.locator("button:has-text('Next'), button:has-text('Continue')")
                if await next_btn.count() > 0 and await next_btn.first.is_visible():
                     await next_btn.first.click()
                     await page.wait_for_timeout(1000)

                await page.wait_for_selector("input[type='password']", timeout=10000)
                await page.fill("input[type='password']", password)
                
                # Submit
                submit_btn = page.locator("button[type='submit'], button:has-text('Sign in'), button:has-text('Log in')")
                await submit_btn.first.click()
                
                # Wait for navigation to projects or dashboard
                print("Waiting for login to complete...")
                await page.wait_for_url("**/projects**", timeout=30000)
                
                # Save state
                print("Login successful. Saving auth state...")
                await context.storage_state(path=AUTH_STATE_PATH)
            else:
                print("Already logged in.")
                
        except Exception as e:
            print(f"Authentication failed: {e}")
            # Don't exit, might be able to inspect public pages or partial state
            
class Inspector:
    def __init__(self, page: Page):
        self.page = page
        self.elements = []

    async def explore(
        self,
        url: str,
        target_description: Optional[str] = None,
        pause_before_scan: bool = False,
        settle_ms: int = 5000,
    ):
        print(f"Navigating to {url}...")
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            print("Page loaded (domcontentloaded). Waiting for network to settle...")
            await self.page.wait_for_timeout(settle_ms)  # Give it time to render
        except Exception as e:
            print(f"Navigation warning: {e}")

        if pause_before_scan:
            print("Opening Playwright Inspector... Use the picker, then click Resume.")
            await self.page.pause()
        
        # Inject script to find elements
        print("Scanning DOM for interactive elements (including Shadow DOM)...")
        self.elements = await self.page.evaluate("""
            () => {
                const results = [];
                
                function isInteractive(el) {
                    const tag = el.tagName.toLowerCase();
                    const style = window.getComputedStyle(el);
                    
                    if (['button', 'a', 'input', 'select', 'textarea'].includes(tag)) return true;
                    if (el.getAttribute('role') === 'button') return true;
                    if (el.hasAttribute('data-testid')) return true;
                    if (el.hasAttribute('aria-label')) return true;
                    if (style.cursor === 'pointer') return true;
                    
                    return false;
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
                        return ''; // Fallback for detached/shadow
                    }
                }

                function traverse(root) {
                    const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
                    let node = walker.nextNode();
                    while(node) {
                        // Check current node
                        if (isInteractive(node)) {
                             const rect = node.getBoundingClientRect();
                             const style = window.getComputedStyle(node);
                             if (rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none') {
                                 results.push({
                                    tagName: node.tagName.toLowerCase(),
                                    text: node.innerText ? node.innerText.substring(0, 100).replace(/\\n/g, ' ') : '',
                                    href: node.getAttribute('href') || '',
                                    testId: node.getAttribute('data-testid') || '',
                                    ariaLabel: node.getAttribute('aria-label') || '',
                                    role: node.getAttribute('role') || '',
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
                        
                        // Check for Shadow Root
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
        
        print(f"Found {len(self.elements)} potential interactive elements.")
        
        # Save Report
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(self.elements, f, indent=2, ensure_ascii=False)
        print(f"Report saved to {REPORT_PATH}")
        
        # Screenshot
        await self.page.screenshot(path=SCREENSHOT_PATH, full_page=True)
        print(f"Screenshot saved to {SCREENSHOT_PATH}")
        
        # Annotate
        self._annotate_screenshot()
        
        # Console Output
        if target_description:
            self._print_relevant(target_description)

    def _annotate_screenshot(self):
        print("Generating annotated screenshot...")
        try:
            with Image.open(SCREENSHOT_PATH) as img:
                draw = ImageDraw.Draw(img, "RGBA")
                # Try to load a font, fallback to default
                try:
                    font = ImageFont.truetype("Arial.ttf", 14)
                except:
                    font = ImageFont.load_default()
                
                for idx, el in enumerate(self.elements):
                    r = el['rect']
                    # Draw red semi-transparent rectangle
                    draw.rectangle(
                        [r['x'], r['y'], r['x'] + r['width'], r['y'] + r['height']],
                        outline="red",
                        width=2,
                        fill=(255, 0, 0, 30)
                    )
                    # Draw index background
                    draw.rectangle(
                        [r['x'], r['y'], r['x'] + 25, r['y'] + 15],
                        fill="red"
                    )
                    # Draw index number
                    draw.text((r['x'] + 2, r['y']), str(idx), fill="white", font=font)
                
                img.save(ANNOTATED_PATH)
                print(f"Annotated screenshot saved to {ANNOTATED_PATH}")
        except Exception as e:
            print(f"Failed to annotate screenshot: {e}")

    def _print_relevant(self, description: str):
        print(f"\n--- Top Elements matching '{description}' (Simple Text Match) ---")
        # Simple scoring based on text overlap
        scored = []
        desc_lower = description.lower()
        for i, el in enumerate(self.elements):
            score = 0
            content = (el['text'] + " " + el['testId'] + " " + el['ariaLabel']).lower()
            if desc_lower in content:
                score += 10
            # Split words
            for word in desc_lower.split():
                if word in content:
                    score += 1
            
            if score > 0:
                scored.append((score, i, el))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        
        for score, idx, el in scored[:20]:
            print(f"[{idx}] Score: {score} | Tag: {el['tagName']} | Text: {el['text'][:30]}... | ID: {el['testId']}")

def _load_config() -> Dict[str, Any]:
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


async def _open_browser(p, cfg: Dict[str, Any]):
    browser_mode = (cfg.get("browser") or "chrome").lower()
    chrome_cdp_url = cfg.get("chrome_cdp_url") or "http://localhost:9222"
    multilogin_cdp_url = cfg.get("multilogin_cdp_url")
    profiles = cfg.get("profiles") or {}
    profile_to_use = (cfg.get("profile_to_use") or "").strip()
    force_embedded = bool(cfg.get("force_embedded_browser", False))

    if profile_to_use.lower() == "ask" or not profile_to_use:
        if "chrome_automation" in profiles:
            profile_to_use = "chrome_automation"
        elif profiles:
            profile_to_use = list(profiles.keys())[0]
        else:
            profile_to_use = "chrome_automation"

    if not force_embedded and browser_mode == "multilogin":
        if not multilogin_cdp_url:
            raise RuntimeError("multilogin_cdp_url missing")
        return await p.chromium.connect_over_cdp(multilogin_cdp_url)
    if not force_embedded:
        chosen_cdp = chrome_cdp_url
        profile_path = str(cfg.get("chrome_profile_path", "~/chrome_automation"))
        if profiles and profile_to_use and profile_to_use in profiles:
            pconf = profiles[profile_to_use] or {}
            if pconf.get("cdp_url"):
                chosen_cdp = pconf["cdp_url"]
            if pconf.get("profile_path"):
                profile_path = pconf["profile_path"]
        abs_profile_path = os.path.expanduser(profile_path)
        os.makedirs(abs_profile_path, exist_ok=True)
        try:
            return await p.chromium.connect_over_cdp(chosen_cdp)
        except Exception:
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--ignore-certificate-errors",
                "--ignore-ssl-errors",
                "--allow-insecure-localhost",
                "--disable-web-security",
            ]
            return await p.chromium.launch(headless=False, args=launch_args)

    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--ignore-certificate-errors",
        "--ignore-ssl-errors",
        "--allow-insecure-localhost",
        "--disable-web-security",
    ]
    return await p.chromium.launch(headless=False, args=launch_args)


async def main():
    parser = argparse.ArgumentParser(description="HeyGen UI Inspector")
    parser.add_argument("url", help="URL to inspect")
    parser.add_argument("--target", help="Description of target element to find", default=None)
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument(
        "--settle-ms",
        type=int,
        default=5000,
        help="Extra time to wait after domcontentloaded before scanning (ms)",
    )
    args = parser.parse_args()

    cfg = _load_config()

    async with async_playwright() as p:
        browser = await _open_browser(p, cfg)
        
        # Load state if exists
        context_args = {
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {"width": 1280, "height": 800},
            "ignore_https_errors": True
        }
        if os.path.exists(AUTH_STATE_PATH):
            print(f"Loading auth state from {AUTH_STATE_PATH}")
            context_args["storage_state"] = AUTH_STATE_PATH

        contexts = browser.contexts
        if contexts:
            context = contexts[0]
        else:
            context = await browser.new_context(**context_args)
            
        # Inject script to hide webdriver property
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        if context_args and not contexts:
            # storage_state only applies to newly created context
            pass

        page = context.pages[0] if context.pages else await context.new_page()
        
        # Auth Check
        await AuthManager.login_if_needed(page, context)
        
        # Explore
        inspector = Inspector(page)
        await inspector.explore(
            args.url,
            args.target,
            pause_before_scan=not args.headless,
            settle_ms=max(0, int(args.settle_ms)),
        )
        

if __name__ == "__main__":
    asyncio.run(main())
