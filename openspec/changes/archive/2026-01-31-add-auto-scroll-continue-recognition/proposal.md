# Change: Add Auto-Scroll Continue Recognition

## Why
The current essence scanner only processes one page (45 essences) at a time. Users have to manually scroll down and press the scan key again to process additional pages, which is tedious when dealing with many essences. Adding auto-scroll continuation will improve efficiency by automatically scanning all pages in one operation.

## What Changes
- Add auto-scroll functionality to the EssenceScanner class that automatically scrolls down after completing one page
- Implement bottom detection logic to recognize when scrolling reaches the end
- Modify the existing scan loop to continue scrolling and recognizing until reaching the bottom
- No changes to user interface or configuration - works with existing `]` key binding

## Impact
- Affected specs: N/A (new capability)
- Affected code: `src/endfield_essence_recognizer/essence_scanner.py`
- Breaking changes: None
