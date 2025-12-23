"""Centralized logging helpers for EmuManager.

Provide a small helper to create a logger that writes to stdout and to a
project-level install log under the base directory. This centralization makes
it easier to adjust formatting/verbosity in one place.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional


class Col:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GREY = "\033[90m"
    BOLD = "\033[1m"
    WHITE = "\033[1;37m"


def get_logger(name: str = "emumanager", base_dir: Optional[Path] = None, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Check if console handler exists
    has_console = any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in logger.handlers)
    if not has_console:
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(ch)

    # Check if file handler exists
    has_file = any(isinstance(h, logging.FileHandler) for h in logger.handlers)
    
    if base_dir and not has_file:
        base_dir = Path(base_dir)
        try:
            base_dir.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(str(base_dir / "_INSTALL_LOG.txt"))
            fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
            logger.addHandler(fh)
        except Exception:
            logger.debug("Could not create file handler for logger at %s", base_dir)
            
    return logger
