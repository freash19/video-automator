I will fix the task launching and browser stability issues as requested.

**Plan:**

1.  **Create Test Data**:
    *   Create `test_scenes.csv` with the 3 scenes provided by the user.
2.  **Update Configuration**:
    *   Update `.env` with the provided HeyGen credentials (`HEYGEN_EMAIL`, `HEYGEN_PASSWORD`).
3.  **Fix Browser Launch (`heygen_automation.py`)**:
    *   Modify `open_browser` to strictly enforce using the system Google Chrome on macOS to avoid the "Test" version stability issues.
    *   Ensure `executable_path` points to `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`.
    *   Add `channel="chrome"` as a fallback.
4.  **Fix Profile Management (`ui/api.py`)**:
    *   Update `api_open_browser` to correctly apply the path of the selected profile (`profile_to_use`) to the automation config before launching. This ensures session persistence and correct profile switching.
5.  **Verify**:
    *   The system will be ready for you to press "Run" in the UI. I will confirm the files are in place.

**Implementation Details:**
*   **CSV**: I will map your data to `episode_id`, `part_idx`, `scene_idx`, `speaker`, `text`, `brolls`, `template_url`.
*   **Browser**: I will modify `heygen_automation.py` to check for the specific Chrome path you showed and force Playwright to use it.
