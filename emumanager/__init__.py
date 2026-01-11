"""EmuManager package root.

Expose core modules at package level for convenient imports. Keep this file
small and explicit to make `import emumanager` lightweight.
"""

from . import config, gui, manager, switch
from .converters import ps2_converter

__all__ = [
    "manager",
    "config",
    "gui",
    "ps2_converter",
    "switch",
]
