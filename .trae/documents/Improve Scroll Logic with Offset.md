I will modify `_ensure_min_unfilled_scenes_visible` in `heygen_automation.py` to:
1.  Scroll the current scene element (`text_N`) to the top using `scrollIntoView({ block: 'start' })`.
2.  Use JavaScript to find the nearest scrollable ancestor of the element and adjust its `scrollTop` by subtracting 150 pixels. This will effectively push the content down by 150px relative to the viewport top, ensuring the element is not hidden by any headers and has some "breathing room" above it.
3.  This handles the user's request to "lower it significantly, not less than 150px" and ensures the previous scene is likely hidden or at least the current one is fully visible with context.

This logic is robust because it operates on the specific scroll container of the element, rather than assuming `window` scroll.