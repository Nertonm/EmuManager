#!/usr/bin/env python3
"""Compatibility shim for switch_organizer.

This script redirects to emumanager.switch.cli.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from emumanager.switch.cli import *  # noqa: F401,F403,E402
from emumanager.switch.cli import main  # noqa: E402

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import logging

        logging.getLogger("organizer_v13").exception("Fatal error")
        sys.exit(2)
