I will modify `heygen_automation.py` to simplify the scene filling and verification logic as requested.

### Changes to `heygen_automation.py`

1.  **Simplify `_verify_scene_text` method**:
    *   Remove the retry loop (currently 3 attempts).
    *   Remove the call to `_fast_replace_text` (which caused the "second click").
    *   Remove the `Tab` key press.
    *   The method will now perform a single check: if the text matches, return `True`; otherwise, log failure and return `False`.

2.  **Update `fill_scene` method (inside `_insert_text` inner function)**:
    *   Remove `await page.keyboard.press('Tab')` after text insertion.
    *   Remove the entire inline verification and retry block (lines ~846-866), which contained additional clicks and text re-entry logic.

These changes ensure:
*   Only one click is performed (during scene selection).
*   No `Tab` key usage.
*   Only one verification check is performed immediately after filling.
