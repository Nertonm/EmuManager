# TODO

- [x] Fix `pytest` installation and run tests.
- [x] Remove global variables from `emumanager/switch/cli.py` and pass context explicitly.
- [x] Add unit tests for `emumanager/switch/cli.py` logic.
- [x] Verify `emumanager-gui` works with the new structure.
- [x] Add more converters (e.g. for other systems).
- [x] Improve error handling for missing tools (nstool, nsz, etc.).
- [x] Add "Identify" feature for other systems (GameCube, Wii, etc).
- [x] Centralize tool finding logic (currently scattered in converters/workers).
- [x] Add support for Wii and GameCube RVZ compression and verification.
- [x] Implement "Process Selected Files Only" in GUI.
- [x] Implement "Enforce Standard Naming" option.
- [x] Add DAT file verification (No-Intro/Redump) with visual results table.

## Future Ideas
- [ ] Add support for Xbox/Xbox360 ISOs (XISO).
- [ ] Integration with scraping APIs (Screenscraper, TheGamesDB).
- [ ] Dark Mode toggle in Settings (currently auto-applied).
