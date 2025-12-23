"""EmuManager package root.

Expose core modules at package level for convenient imports. Keep this file
small and explicit to make `import emumanager` lightweight.
"""

from . import architect
from . import manager
from . import config
from . import gui
from .converters import ps2_converter
from . import switch

__all__ = [
	"architect",
	"manager",
	"config",
	"gui",
	"ps2_converter",
	"switch",
]
