I will fix the B-roll addition workflow by updating `core/broll.py` and `heygen_automation.py` to address the specific failure points you identified (Video tab selection, Source dropdowns, B-roll selection, Set as BG, and Foreground removal).

### Plan

1.  **Update `core/broll.py`**:
    *   **`select_video_tab`**: Change selector to `page.get_by_role("tab", name=...)` to correctly target the tab element. Keep `force=True` and `aria-selected` verification.
    *   **`select_media_source` & `select_orientation`**: Improve dropdown interaction by ensuring the menu opens and using more robust `get_by_role("option")` selectors for items like "Getty" and "Landscape".
    *   **`search_and_select_broll`**:
        *   Wait for search results to be fully interactive.
        *   Use a more specific selector for clicking the video result (targeting the container instead of just the image if needed).
    *   **`click_make_background`**: Add an explicit `wait_for` to ensure the "Set as BG" button is visible before attempting to click it.
    *   **`try_delete_foreground`**: Refine the deletion sequence: Wait for "Set as BG" -> Click Canvas Center (to select old foreground) -> Press Delete.

2.  **Update `heygen_automation.py`**:
    *   Disable the `close_media_panel` step after B-roll insertion, as requested ("убери закрывание панели Media").
    *   Ensure the `Video` tab selection is called explicitly before starting the B-roll search sequence.

3.  **Verification**:
    *   Review the code to ensure it matches the logic described in your Inspector findings.
    *   (User Action) You will need to run the automation to verify the fix against the "Fail" scenarios.
