# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **PS2 Identification**: New module `emumanager.ps2` to extract Serials from ISO/BIN/GZ files and identify games.
- **PS2 Database**: Simple CSV-based database support (`ps2_db.csv`) for game title lookup.
- **GUI**: New "Identify & Verify Games" button in the PS2 tab.
- **Refactoring**: Extracted `process_files(files, ctx)` into `emumanager.switch.main_helpers`.
- Introduced small helpers: `build_new_filename`, `get_dest_folder`, `make_catalog_entry`.
- New unit tests added: `tests/test_main_helpers.py` covering the new helpers.

### Changed
- **Cleanup**: Removed `emumanager/legacy` and moved useful code to `emumanager/switch`.
- **Refactoring**: `switch_organizer.py` now builds a context dict and delegates file processing to `emumanager.switch.main_helpers.process_files`.
- **Refactoring**: Improved `gui_main.py` by extracting dialog logic and background task management.
- **Refactoring**: Centralized tool finding logic in `emumanager.common.execution`.

### Fixed
- Adjusted test suite and fixed issues surfaced by refactor; full test suite passing.
- Fixed PS2 Converter worker to correctly pass tool paths.


## [0.1.0] - 2025-12-22
- Initial public refactor and packaging efforts.
