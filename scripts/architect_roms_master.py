"""
Compatibility shim for older imports.

The real implementation lives in the `emumanager` package; this module re-exports
symbols so existing scripts that import `scripts.architect_roms_master` continue to
work.
"""

from emumanager.architect import *  # noqa: F401,F403

__all__ = [name for name in globals().keys() if not name.startswith("_")]
