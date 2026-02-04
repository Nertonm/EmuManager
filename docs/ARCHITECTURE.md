# Architecture Documentation

## Overview

EmuManager follows a layered architecture designed to separate concerns between the user interface, coordination logic, and low-level system handling.

## Core Components

### 1. The Orchestrator (`emumanager.core.orchestrator`)

The Orchestrator acts as the central hub of the application. It receives high-level commands from the UI (TUI/GUI/CLI) and delegates them to specific subsystems. It manages the `Session` context and ensures that long-running tasks are properly tracked.

### 2. Library Database (`emumanager.library`)

Persistence is handled by `LibraryDB`, a wrapper around SQLite.
*   **Schema**: Stores file paths, hashes (CRC32/MD5/SHA1), metadata, and verification status.
*   **WAL Mode**: Write-Ahead Logging is enabled to support concurrent reading and writing, essential for the multi-threaded worker architecture.
*   **Thread Safety**: Uses thread-local connection objects to prevent concurrency issues.

### 3. System Providers (`emumanager.common.system`)

To handle the diversity of console formats, EmuManager uses a Strategy pattern via "Providers". Each supported system (e.g., PS2, GameCube) implements a `SystemProvider` interface.

*   **Responsibilities**:
    *   Identifying valid file extensions (e.g., `.rvz`, `.iso`).
    *   Extracting internal metadata (serial numbers, titles) from binary headers.
    *   Validating file integrity specific to the format.
*   **Registry**: A central registry (`emumanager.common.registry`) automatically discovers and loads these providers at runtime.

### 4. Workers (`emumanager.workers`)

Long-running operations are encapsulated in Workers to keep the UI responsive.
*   **Scanner**: Recursively crawls directories, interacting with Providers to identify files.
*   **Hasher**: Performs multithreaded calculation of cryptographic hashes.
*   **Organizer**: Moves and renames files based on canonical metadata.

### 5. Verification

Verification is two-fold:
1.  **Cryptographic**: Comparison of calculated hashes against known "clean" sets (DAT files).
2.  **Structural**: Using external tools (`chdman`, `dolphin-tool`) to verify the internal structure of container formats like CHD or RVZ.

## Directory Structure

*   `emumanager/`: Main package.
    *   `core/`: Core logic (Orchestrator, Scanner).
    *   `common/`: Shared utilities, base classes, database interfaces.
    *   `workers/`: Asynchronous task implementations.
    *   `[system_name]/`: Specific provider implementations (e.g., `ps2/`, `gamecube/`).
    *   `ui/` / `tui.py` / `gui_main.py`: Interface layers.
*   `tests/`: Pytest suite.
