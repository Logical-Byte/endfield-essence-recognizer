## 1. Implementation
- [x] 1.1 Add scroll function to scroll down using mouse wheel at specific position
- [x] 1.2 Implement bottom detection by comparing screenshots before and after scroll
- [x] 1.3 Modify EssenceScanner.run() to add outer loop for multi-page scanning
- [x] 1.4 Integrate scroll and bottom detection logic into scan loop
- [x] 1.5 Add logging for page transition events (page number, scroll attempts)

## 2. Testing
- [ ] 2.1 Test auto-scroll with single page (should complete without scrolling)
- [ ] 2.2 Test auto-scroll with multiple pages (should scroll and continue)
- [ ] 2.3 Test bottom detection (should stop correctly at end)
- [ ] 2.4 Test interruption during multi-page scan (user can still stop with `]` key)
- [ ] 2.5 Test with various essence counts and page states
