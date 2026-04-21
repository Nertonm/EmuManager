# Contributing

Changes should leave the project more maintainable than they found it. This repository already has a large surface area, so the contribution bar is intentionally practical and strict.

## Environment Setup

1. Use Python 3.10 or newer.
2. Install editable dependencies:

```bash
pip install -e ".[dev,gui]"
```

## Required Quality Checks

Run these before opening a PR:

```bash
ruff check emumanager
python -m compileall -q emumanager
pytest -q
```

## Code Guidelines

- Prefer improving existing abstractions over adding parallel ones.
- Keep UI layers thin. Domain rules belong in providers, services, workers, or the orchestrator.
- Do not reintroduce legacy names from the old `switch_organizer` layout.
- Use type hints on new public functions and methods.
- Replace broad inline logic with small named helpers when a block becomes hard to scan.
- Avoid silent fallbacks unless the degraded behavior is intentional and documented.

## Tests

- Add or update tests for behavior changes.
- If a module is weakly covered, prefer small targeted tests instead of leaving the change implicit.
- For GUI-related changes, add coverage where practical, but do not expand brittle test scaffolding without reason.

## Documentation

- Update `README.md` when commands, entry points, or developer workflow change.
- Update `docs/ARCHITECTURE.md` when responsibilities move between layers.
- Keep docs grounded in the current code, not in aspirational structure.

## Providers

If adding support for a new system:

1. Create a new package under `emumanager/[system_name]`.
2. Implement `provider.py` inheriting from `SystemProvider`.
3. Register the provider in `emumanager.common.registry` or ensure auto-discovery covers it.
4. Add tests for metadata extraction, extension support, and validation behavior.
