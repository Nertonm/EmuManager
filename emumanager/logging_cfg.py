"""Centralized logging helpers for EmuManager.

Provide a small helper to create a logger that writes to stdout and to a
project-level install log under the base directory. This centralization makes
it easier to adjust formatting/verbosity in one place.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
import logging.handlers


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

_STD_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

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
            fh.setFormatter(logging.Formatter(_STD_FORMAT))
            logger.addHandler(fh)
        except Exception:
            logger.debug("Could not create file handler for logger at %s", base_dir)
            
    return logger


def get_fileops_logger(base_dir: Optional[Path] = None, level: int = logging.INFO) -> logging.Logger:
    """Return a logger dedicated to file operations (audit-capable).

    This logger writes to a rotating file under base_dir/logs/fileops.log and
    also to console if not already configured. Handlers are added idempotently.
    """
    name = "emumanager.fileops"
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Add console handler if missing
    has_console = any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in logger.handlers)
    if not has_console:
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(ch)

    # Add rotating file handler
    has_rotating = any(isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers)
    if base_dir and not has_rotating:
        try:
            logs_dir = Path(base_dir) / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            rfh = logging.handlers.RotatingFileHandler(str(logs_dir / "fileops.log"), maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
            rfh.setFormatter(logging.Formatter(_STD_FORMAT))
            logger.addHandler(rfh)
        except Exception:
            logger.debug("Could not create rotating file handler for fileops logger at %s", base_dir)

    # Prevent propagation to root to avoid duplicate entries
    logger.propagate = False
    return logger
