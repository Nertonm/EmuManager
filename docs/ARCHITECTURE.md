# Architecture

## Overview

EmuManager is organized around a shared application core reused by the TUI, GUI, and CLI. The codebase is not fully domain-pure yet, but the intended layering is clear:

- `common/` holds reusable primitives and low-level helpers
- `application/` exposes shared read-models and workflow contracts reused by CLI, GUI, and TUI
- `core/` owns orchestration, scanning, integrity, and session lifecycle
- `workers/` runs long-running tasks and compatibility workflows
- `controllers/` coordinates GUI actions without embedding all logic directly in widgets
- Per-system packages (`ps2/`, `psx/`, `switch/`, etc.) isolate console-specific metadata and provider behavior

## Runtime Layers

### Interface layer

- `emumanager.tui`: Textual cockpit for interactive terminal workflows
- `emumanager.tui_layout`: Textual layout/composition for the cockpit shell
- `emumanager.tui_library`: system listing, ROM browsing, filtering, and inspector wiring
- `emumanager.tui_workflows`: workflow execution, progress, synchronization, and report rendering
- `emumanager.tui_components`: reusable TUI widgets and shared CSS/binding constants
- `emumanager.gui_main`: Qt main window composition and shared bridges
- `emumanager.gui_main_library`: library browsing, scan refresh, and add/open workflows
- `emumanager.gui_main_library_scan`: dashboard refresh, scan orchestration, and system-list sync
- `emumanager.gui_main_library_browser`: façade for library-browser behaviors
- `emumanager.gui_main_library_browser_actions`: add/open-library/organize/cancel GUI actions
- `emumanager.gui_main_library_browser_listing`: ROM discovery, filters, and selection handling
- `emumanager.gui_main_library_browser_runtime`: common GUI action args and environment wiring
- `emumanager.gui_main_quarantine`: quarantine table refresh, restore, delete, and open-location actions
- `emumanager.gui_main_roms`: selected-ROM actions and metadata presentation
- `emumanager.gui_main_settings`: GUI settings persistence mixin
- `emumanager.gui_main_verification`: verification, DAT, and rehash workflow mixin
- `emumanager.gui_main_verification_dat`: DAT selection, verification execution, and post-verify sync
- `emumanager.gui_main_verification_rehash`: targeted rehash and in-memory result refresh
- `emumanager.gui_main_verification_results`: verification table rendering, filter, export, and row styling
- `emumanager.gui_main_verification_dats`: DAT download/update workflow
- `emumanager.gui_main_verification_identify`: single-file and full-library identify flows
- `emumanager.gui_ui`: Qt shell/scaffolding for the main window
- `emumanager.gui_ui_shell`: main-window shell, top bar, tabs, dock, and status wiring
- `emumanager.gui_ui_qt`: Qt compatibility helpers for icons and enum namespaces
- `emumanager.gui_ui_theme`: palette and stylesheet application
- `emumanager.gui_ui_shared`: shared button/tab factories used across UI builders
- `emumanager.gui_ui_library`: dashboard and library tab builders
- `emumanager.gui_ui_tools`: tools/quarantine tab builders
- `emumanager.gui_ui_extra_tabs`: verification, settings, gallery, and duplicate tab builders
- `emumanager.gui_messages`: shared GUI status/error copy reused across mixins
- `emumanager.cli`: Typer command surface for automation

These entry points should stay thin. They should delegate domain work to the orchestrator, controllers, or workers instead of reimplementing business logic locally.

### Coordination layer

- `emumanager.application.library_insights`: shared collection snapshots for dashboards, ROM browsers, and inspectors
- `emumanager.application.collection_reports`: shared analytics, deduplication, and quality report builders
- `emumanager.application.workflows`: interface-neutral contract for core orchestrator workflows
- `emumanager.core.orchestrator`: thin workflow façade that wires together focused orchestrator mixins
- `emumanager.core.orchestrator_library`: initialization, scanning, ingest, reporting, and cover helpers
- `emumanager.core.orchestrator_organization`: organization, distribution, and benchmark workflows
- `emumanager.core.orchestrator_maintenance`: integrity, duplicate cleanup, transcoding, and compliance workflows
- `emumanager.controllers.duplicates`: façade for duplicate-management GUI flows
- `emumanager.controllers.duplicates_moves`: duplicate move validation and execution
- `emumanager.controllers.duplicates_scan`: duplicate scan kickoff and summary rendering
- `emumanager.controllers.duplicates_view`: duplicate-group table and selection behavior
- `emumanager.controllers.tools`: façade for tool/controller actions
- `emumanager.controllers.*`: GUI-oriented coordination for tools, duplicates, and gallery behavior, increasingly driven by binding/spec maps instead of hand-wired UI code
- `emumanager.workers.*`: background job execution and system-specific batch operations
- `emumanager.switch.cli`: compatibility façade for the Switch command surface
- `emumanager.switch.cli_args`: argument parser, banner, manual, and CLI defaults
- `emumanager.switch.cli_operations`: metadata, verification, compression, and move operations
- `emumanager.switch.cli_runtime`: runtime wiring, progress, and finalization helpers

This layer translates user actions into application workflows and should own progress reporting, cancellation, and sequencing.

### Domain and infrastructure layer

- `emumanager.library`: façade for persistence contracts reused across the app
- `emumanager.library_models`: entry and duplicate-group models plus normalized-name helpers
- `emumanager.library_db_core`: SQLite connection, schema, CRUD, and audit-log behavior
- `emumanager.library_db_duplicates`: duplicate lookup queries by hash and normalized name
- `emumanager.common.registry`: provider discovery and lookup
- `emumanager.common.system`: base provider contract and default naming helpers
- `emumanager.verification.*`: DAT parsing, hashing, and download support
- `emumanager.common.execution`: tool lookup and command execution wrappers
- `emumanager.core.scanner`: façade for scanning workflows
- `emumanager.core.scanner_discovery`: directory traversal and library cleanup logic
- `emumanager.core.scanner_entries`: per-file metadata extraction and persistence
- `emumanager.core.scanner_verification`: hash/DAT/integrity verification behavior

## Providers

Each supported system exposes a provider implementing `SystemProvider`. Providers are responsible for:

- Declaring supported extensions
- Extracting minimal metadata
- Returning canonical naming suggestions
- Performing system-specific validation where possible

The registry is the integration point. New systems should be added through a provider package instead of branching orchestration logic everywhere.

## Persistence Model

`LibraryDB` is the operational source of truth for scan results and maintenance actions.

- Entries track paths, sizes, hashes, metadata, and status
- Action logs provide an audit trail for moves, deletions, quarantine, and organization
- Duplicate analysis can operate on hashes and normalized names

Because multiple workflows touch the database, write paths should be explicit and narrowly scoped.

## Maintenance Notes

Current debt hotspots to watch:

- The new `application/` layer should remain UI-agnostic; keep Rich/Textual/PyQt formatting details in the interface modules and push only reusable semantics into these services
- `gui_main.py` and `gui_ui.py` are now split by responsibility; keep new GUI behavior inside the focused mixins instead of pushing features back into the façade files
- `gui_ui.py` is now a façade over shell/theme/Qt-compat helpers plus per-tab builders; extend those focused modules instead of letting the façade grow again
- `gui_main_library.py` and `gui_main_verification.py` are now façade modules over smaller feature mixins; keep extending the focused leaf modules instead of regrowing the façade files
- `gui_main_library_browser.py`, `controllers/duplicates.py`, `library.py`, and `core/scanner.py` are now compatibility façades; extend their focused helper modules instead of letting those façade files grow again
- Tool tabs and other repeated Qt button patterns now go through shared factories/configuration; extend that pattern instead of adding new hand-built widget blocks
- The Switch CLI is now segmented into parser/runtime/operations modules; keep `switch/cli.py` as a stable façade instead of re-growing business logic there
- `tui.py` is now a small façade over focused TUI modules; keep future Textual work inside `tui_layout.py`, `tui_library.py`, `tui_workflows.py`, or `tui_components.py` instead of regrowing the façade
- Some worker modules still act as compatibility bridges for older flows; prefer consolidating behavior in orchestrator/services instead of growing bridge code
- External tools such as `chdman`, `dolphin-tool`, and Switch utilities should stay behind helper functions so missing-tool behavior is predictable

## Directory Map

```text
emumanager/
  application/          Shared workflow contracts and collection read-models
  analytics/            Collection metrics and reporting helpers
  common/               Execution, validation, registry, models, shared helpers
  controllers/          GUI controllers
  core/                 Orchestration, scanning, integrity, session management
  gui_messages.py       Shared GUI status/error messages
  gui_main_*.py         Main-window behavior split by feature area
  gui_ui*.py            Main-window layout/scaffolding split by tab groups
  library*.py           Persistence façade, models, and focused DB helpers
  converters/           Format conversion helpers
  deduplication/        Duplicate analysis
  metadata_providers/   Remote metadata integrations
  verification/         DAT parsing, downloads, hashing
  workers/              Batch/background workflows
  [system]/             Console-specific provider, metadata, database modules
tests/                  Automated regression suite
docs/                   Project documentation
```
