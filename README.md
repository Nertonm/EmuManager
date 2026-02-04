# EmuManager

**Industrial-grade emulation collection manager and utilities.**

EmuManager is a specialized tool designed for the automated management, verification, and organization of large-scale emulation libraries. It provides a robust backend capable of handling thousands of files with industrial reliability, supporting multiple modern consoles including PS2, GameCube, Wii, Switch, 3DS, PSP, and PSX.

## Key Features

*   **Universal Orchestrator**: Centralized logic for scanning, processing, and organizing ROM files across different directory structures.
*   **Modular Architecture**: System-specific providers ensure correct handling of unique file formats (e.g., ISO for PS2, RVZ for GameCube/Wii, NSP/XCI for Switch).
*   **Integrity Verification**: 
    *   Multi-threaded hashing (CRC32, MD5, SHA1).
    *   DAT file support (No-Intro, Redump) for precise verification.
    *   Native format verification (e.g., `dolphin-tool verify` for RVZ, `chdman verify` for CHD).
*   **Advanced Deduplication**: Identifies duplicates based on cryptographic hashes and normalized naming conventions, helping to recover wasted storage.
*   **Format Conversion**: 
    *   ISO to CHD (PS2, PSX).
    *   ISO to RVZ (GameCube, Wii).
    *   Compression management for Switch (NSZ).
*   **Analytics Dashboard**: Insights into collection completion, verification status, and storage usage.
*   **Multiple Interfaces**:
    *   **TUI (Textual)**: Rich terminal user interface for servers and remote management.
    *   **GUI (PyQt6)**: Full desktop experience with visual gallery and inspectors.
    *   **CLI**: Scriptable interface for cron jobs and pipelines.

## Installation

Requires Python 3.10 or higher.

### Core Installation (Headless/Server)

```bash
pip install .
```

### Full Installation (with GUI)

```bash
pip install ".[gui]"
```

## Usage

### Terminal User Interface (Recommended)

The interactive TUI serves as the main cockpit for managing the library.

```bash
emumanager
```

### Command Line Interface (Automation)

For specific commands without interactivity:

```bash
emumanager-cli --help
```

### Graphical User Interface

For desktop environments:

```bash
emumanager-gui
```

## Development

1.  Clone the repository.
2.  Install development dependencies:
    ```bash
    pip install -e ".[dev,gui]"
    ```
3.  Run tests:
    ```bash
    pytest
    ```

## License

MIT License.
