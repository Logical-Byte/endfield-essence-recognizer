# auto-scroll-continue Specification

## Purpose
TBD - created by archiving change add-auto-scroll-continue-recognition. Update Purpose after archive.
## Requirements
### Requirement: Auto-Scroll Continue Recognition
The EssenceScanner SHALL automatically scroll down and continue recognizing essences on subsequent pages after completing the current page, until reaching the bottom of the essence list.

#### Scenario: Successful multi-page scan with auto-scroll
- **GIVEN** the essence inventory has multiple pages of essences
- **WHEN** the user presses the `]` key to start scanning
- **AND** the scanner completes all 45 essences on the first page
- **THEN** the system SHALL automatically scroll down to the next page
- **AND** SHALL continue scanning all essences on the new page
- **AND** SHALL repeat this process until reaching the bottom
- **AND** SHALL log each page transition (e.g., "开始扫描第 2 页...")

#### Scenario: Single page scan (no scrolling needed)
- **GIVEN** the essence inventory has only one page of essences
- **WHEN** the user presses the `]` key to start scanning
- **AND** the scanner completes all 45 essences on the first page
- **THEN** the system SHALL detect that it has reached the bottom
- **AND** SHALL complete scanning without attempting to scroll
- **AND** SHALL log "基质扫描完成。"

#### Scenario: Detection of bottom reached
- **GIVEN** the scanner has completed scanning a page
- **WHEN** the system attempts to determine if more pages exist
- **AND** captures a screenshot of the essence grid area
- **AND** performs a scroll operation
- **AND** captures another screenshot of the same area
- **AND** the two screenshots are sufficiently similar (similarity > 0.95)
- **THEN** the system SHALL determine that the bottom has been reached
- **AND** SHALL stop scanning
- **AND** SHALL log completion message

#### Scenario: User interruption during multi-page scan
- **GIVEN** the scanner is processing multiple pages
- **WHEN** the user presses the `]` key again to interrupt
- **THEN** the system SHALL stop scanning immediately
- **AND** SHALL log "基质扫描被中断。"
- **AND** SHALL NOT attempt further scrolling

#### Scenario: Window lost focus during multi-page scan
- **GIVEN** the scanner is processing multiple pages
- **WHEN** the game window loses focus or is minimized
- **THEN** the system SHALL detect the window state change
- **AND** SHALL stop scanning
- **AND** SHALL log appropriate error message

### Requirement: Mouse Wheel Scrolling
The system SHALL use mouse wheel scrolling to navigate between essence pages.

#### Scenario: Scroll down one page
- **WHEN** the system needs to scroll to the next page
- **THEN** the system SHALL position the mouse cursor over the essence list area
- **AND** SHALL execute a mouse wheel scroll with the appropriate number of ticks
- **AND** SHALL wait for the UI to settle before continuing

#### Scenario: Scroll position configuration
- **GIVEN** the system needs to scroll between pages
- **THEN** the scroll SHALL be performed at position (960, 500) in window client coordinates
- **AND** SHALL use -5 ticks to scroll one full page
- **AND** SHALL allow these values to be adjusted via code constants

