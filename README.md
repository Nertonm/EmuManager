# EmuManager

EmuManager is a Python application for auditing, organizing, verifying, and maintaining emulation libraries. It shares one backend across three interfaces:

- `emumanager`: Textual TUI for interactive workflows
- `emumanager-cli`: Typer CLI for scripted operations
- `emumanager-gui`: PyQt desktop interface

The project targets mixed collections with multiple systems and file formats, with support modules for PS2, PSX, PSP, PS3, Switch, 3DS, GameCube, and Wii.

## Capabilities

- Central orchestration for scan, organization, verification, quarantine, duplicate cleanup, and reporting
- Provider-based system support for metadata extraction, validation, and canonical naming
- Integrity tooling with hashes, DAT parsing, and optional external verification tools
- Deduplication and quarantine workflows backed by the local library database
- Conversion/compression helpers for formats such as CHD, RVZ, and NSZ
- Analytics and quality-control modules for collection health inspection

## Installation

Requires Python 3.10 or higher.

### Core

```bash
pip install .
```

### With GUI

```bash
pip install ".[gui]"
```

## Usage

### TUI

```bash
emumanager
```

### CLI

```bash
emumanager-cli --help
```

### GUI

```bash
emumanager-gui
```

## Project Layout

```text
emumanager/
  application/   Shared workflow contracts and collection view services
  common/        Shared primitives, validation, execution helpers
  core/          Session, orchestrator facade, and focused workflow mixins
  controllers/   GUI-facing controllers
  gui_main_*.py  Main window behavior split by feature area
  gui_ui*.py     Qt layout/scaffolding split by tab groups
  workers/       Background workflows and bridge helpers
  [system]/      Per-system metadata, database, and provider modules
docs/            Architecture and contribution documentation
tests/           Pytest suite
```

## Development

```bash
pip install -e ".[dev,gui]"
ruff check emumanager
python -m compileall -q emumanager
pytest -q
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Contributing](docs/CONTRIBUTING.md)

## License

MIT License.
