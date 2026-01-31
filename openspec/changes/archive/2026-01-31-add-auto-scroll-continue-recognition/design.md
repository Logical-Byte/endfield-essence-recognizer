## Context
The EssenceScanner currently processes 45 essence icons (5 rows × 9 columns) on a single visible page. Users must manually scroll down and re-trigger scanning to process additional pages. The game UI uses a mouse wheel to scroll the essence inventory page.

## Goals / Non-Goals
**Goals:**
- Automatically continue scanning after completing one page
- Use mouse wheel for scrolling (game-standard interaction)
- Detect when reaching the bottom to stop scanning gracefully
- Maintain existing user workflow (press `]` to start scan all pages)

**Non-Goals:**
- Configurable scroll amount or speed (use sensible defaults)
- Progress bar or page counter UI updates
- Alternative scroll methods (scrollbar, buttons)
- Skip empty pages or optimize scan order

## Decisions

### Scroll Position
- **Decision:** Scroll at a central position on the essence list area (e.g., x=960, y=500)
- **Reason:** Mouse wheel scrolling works best when cursor is positioned over the scrollable area
- **Alternative considered:** Scrolling at any position - but this could interact with other UI elements

### Scroll Amount per Page
- **Decision:** Use pyautogui scroll with appropriate ticks to scroll one full page
- **Reason:** pyautogui.scroll() provides cross-platform mouse wheel control; tune amount to match game's scroll distance
- **Alternative considered:** Pixel-based scrolling - more fragile and OS-dependent

### Bottom Detection Method
- **Decision:** Compare essence list area screenshots before and after scroll
- **Reason:** If the screenshot doesn't change after scrolling, we've reached the bottom
- **Implementation details:**
  - Capture screenshot of essence icon grid area before scroll
  - Attempt scroll
  - Capture screenshot of same area after scroll
  - Use OpenCV `cv2.matchTemplate()` or simple image difference to detect changes
  - If no significant change (similarity threshold > 0.95), assume bottom reached

### Loop Structure
- **Decision:** Wrap existing inner loop (45 essences) with outer loop for pages
- **Pseudocode:**
  ```
  page = 0
  while True:
    page += 1
    logger.info(f"开始扫描第 {page} 页...")
    for i, j in essence_icon_grid:
      # existing scan logic...
    # check if should continue scrolling
    if not should_scroll_down():
      break
    scroll_down()
  ```
- **Alternative considered:** Recursive approach - unnecessary complexity

### Error Handling
- **Decision:** Stop scanning on scroll failure or repeated bottom detection
- **Reason:** Prevent infinite loops; provide clear feedback in logs

## Risks / Trade-offs

### Risk: Scroll Amount Incorrect
- **Risk:** Scroll too much (skip pages) or too little (partial page overlap)
- **Mitigation:** Test with game UI to find optimal scroll ticks; add configurable constant

### Risk: Bottom Detection False Positives
- **Risk:** Detect bottom too early (slow scroll animation) or too late (duplicate scanning)
- **Mitigation:** Add delay after scroll for UI to settle; use appropriate similarity threshold

### Risk: Performance Impact
- **Risk:** Screenshot comparison adds overhead
- **Mitigation:** Limit comparison area to essence grid; optimize with simple diff if full matchTemplate too slow

### Trade-off: Simplicity vs Robustness
- Choose simple screenshot comparison over more complex UI element detection
- Accept rare false positives in favor of maintainable code

## Migration Plan
- Add new constants to essence_scanner.py:
  - `SCROLL_POSITION = (960, 500)` - cursor position for scrolling
  - `SCROLL_TICKS = -5` - mouse wheel ticks to scroll one page
  - `BOTTOM_DETECTION_ROI = ((128, 196), (1374, 819)) - essence grid area for comparison
  - `BOTTOM_SIMILARITY_THRESHOLD = 0.95` - similarity threshold for bottom detection
- Add new functions:
  - `scroll_down_window(window)` - perform mouse wheel scroll
  - `is_at_bottom(window)` - detect if reached bottom
- Modify `EssenceScanner.run()` to wrap scan loop in page loop
- No breaking changes to public API or behavior

## Open Questions
- What is the optimal scroll tick count? (Need to test with game UI)
- How long should we wait after scroll for UI to settle? (Test empirically)
- Should we add a small visual indicator between pages? (Logging sufficient for now)
