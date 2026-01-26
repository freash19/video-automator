import asyncio
import json
import os
import sys
from heygen_automation import HeyGenAutomation

# Mock Runner object structure if needed, or just use variables
class MockRunner:
    def __init__(self, config_path):
        with open(config_path, "r") as f:
            self.config = json.load(f)
        self.csv_path = os.path.abspath("test_scenes_3.csv")
        self.automation = HeyGenAutomation(self.csv_path, self.config)

async def run_test():
    print("🚀 Starting test run with profile_3...")
    
    # 1. Setup Runner
    runner = MockRunner("config.json")
    
    # Force profile_3 usage
    runner.config["profile_to_use"] = "profile_3"
    runner.automation.config["profile_to_use"] = "profile_3"
    
    # Ensure profile path is absolute for safety
    if runner.config["profiles"]["profile_3"]["profile_path"].startswith("-/"):
         # Make it absolute
         abs_path = os.path.join(os.getcwd(), runner.config["profiles"]["profile_3"]["profile_path"])
         runner.config["profiles"]["profile_3"]["profile_path"] = abs_path
         runner.automation.config["profiles"]["profile_3"]["profile_path"] = abs_path
         print(f"Fixed profile path to: {abs_path}")

    # 2. Open shared browser
    print("OPENING BROWSER (Parent)...")
    if not await runner.automation.open_browser():
        print("❌ Failed to open browser")
        return
    print("✅ Browser opened successfully")

    # 3. Verify we have a browser instance
    if not runner.automation.browser:
        print("❌ No browser object in runner.automation")
        return

    # 4. Create child automation instance (mimicking _run_one in ui/api.py)
    print("CREATING CHILD AUTOMATION...")
    auto = HeyGenAutomation(
        runner.csv_path, 
        runner.config, 
        browser=runner.automation.browser, 
        playwright=runner.automation.playwright
    )
    
    # 5. Run the task
    print("RUNNING PROCESS_EPISODE_PART...")
    try:
        # We need to ensure the episode exists in the CSV, which it does (test_ep_3)
        # and part 1.
        result = await auto.process_episode_part("test_ep_3", 1)
        if result:
            print("✅ Task completed successfully!")
        else:
            print("❌ Task failed or returned False")
    except Exception as e:
        print(f"❌ Exception during task execution: {e}")
        import traceback
        traceback.print_exc()

    # 6. Keep browser open for inspection if needed, or close
    # For automated test, we close.
    # await runner.automation.browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
