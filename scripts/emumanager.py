"""Compatibility shim for emumanager manager.

This script is intended to be runnable from the `scripts/` directory while the
real implementation lives under the `emumanager` package. To avoid accidental
shadowing when running the script directly (Python's module resolution favors
the script directory), we ensure the project root is on sys.path before
importing the package.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
	sys.path.insert(0, str(PROJECT_ROOT))

from emumanager.manager import *  # noqa: F401,F403,E402

__all__ = [name for name in globals().keys() if not name.startswith("_")]
