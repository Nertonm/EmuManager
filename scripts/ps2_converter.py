"""Compatibility shim for the PS2 converter script.

This file is intentionally tiny: it ensures the project root is on sys.path
when executed from the `scripts/` directory and re-exports the canonical
implementation under `emumanager.converters.ps2_converter` so tests that import
`scripts.ps2_converter` continue to work.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from emumanager.converters.ps2_converter import *  # noqa: F401,F403,E402

__all__ = [name for name in globals().keys() if not name.startswith("_")]
