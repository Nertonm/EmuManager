#!/usr/bin/env python3
"""
EmuManager - Interactive interface

Small interactive, dependency-free text menu that wraps the project's modules
(`architect_roms_master` and `emumanager`) and provides an easy entrypoint for
common tasks: initialize collection, list systems and add ROMs.

Run: python3 scripts/emumanager_interface.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path so running this script from scripts/ will
# import the package instead of accidentally importing a top-level module with
# the same name.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
	sys.path.insert(0, str(PROJECT_ROOT))

from emumanager.interface import *  # noqa: F401,F403,E402


def _headless_smoke_test() -> int:
	"""Run a minimal headless smoke test for the interface (calls list_systems)."""
	import tempfile
	from emumanager import manager

	tmp = Path(tempfile.mkdtemp(prefix="emumanager_interface_smoke_"))
	print("Interface headless smoke: init dry-run on", tmp)
	rc = manager.cmd_init(tmp, dry_run=True)
	print("Interface smoke rc:", rc)
	return rc


if __name__ == "__main__":
	# Preserve original behaviour when executed directly. Allow --headless to run smoke test.
	import sys
	args = sys.argv[1:]
	if "--headless" in args:
		raise SystemExit(_headless_smoke_test())
	raise SystemExit(main())  # noqa: F405
