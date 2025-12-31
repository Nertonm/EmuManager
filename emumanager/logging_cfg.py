"""Centralized logging helpers for EmuManager.

Provide a small helper to create a logger that writes to stdout and to a
project-level install log under the base directory. This centralization makes
it easier to adjust formatting/verbosity in one place.
"""

from __future__ import annotations

import contextvars
import functools
import json
import logging
import logging.handlers
import os
import sys
import time
import uuid
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


_STD_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"


def get_logger(
    name: str = "emumanager",
    base_dir: Optional[Path] = None,
    level: int = logging.INFO,
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Check if console handler exists
    has_console = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in logger.handlers
    )
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


# Correlation ID support for tracing an execution across modules
_cid_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "emumanager_correlation_id", default=None
)


def set_correlation_id(cid: str | None = None) -> str:
    """Set or create and set a correlation id for the current context.

    Returns the correlation id string.
    """
    if cid is None:
        cid = uuid.uuid4().hex
    _cid_var.set(cid)
    return cid


def get_correlation_id() -> str | None:
    return _cid_var.get()


class JsonFormatter(logging.Formatter):
    """Minimal JSON formatter that includes correlation id when available."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        cid = get_correlation_id()
        if cid:
            payload["correlation_id"] = cid
        # Attach exception info if present
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _sanitize_args(args, kwargs, redact_keys=("password", "pwd", "secret")):
    def sanitize_obj(o):
        try:
            if isinstance(o, dict):
                return {
                    k: (
                        "***REDACTED***"
                        if k.lower() in redact_keys
                        else sanitize_obj(v)
                    )
                    for k, v in o.items()
                }
            if isinstance(o, (list, tuple)):
                return type(o)(sanitize_obj(x) for x in o)
            return o
        except Exception:
            return None

    return sanitize_obj(args), sanitize_obj(kwargs)


def log_call(level: int = logging.INFO, redact_keys: tuple[str, ...] = ("password",)):
    """Decorator that logs function entry, args (sanitized), duration and exit.

    Usage:
        @log_call()
        def foo(...):
            ...
    """

    def _decorator(func):
        @functools.wraps(func)
        def _wrapper(*args, **kwargs):
            logger = logging.getLogger(func.__module__)
            start = time.time()
            try:
                s_args, s_kwargs = _sanitize_args(args, kwargs, redact_keys)
                logger.debug(
                    "Entering %s; args=%s kwargs=%s",
                    func.__qualname__,
                    s_args,
                    s_kwargs,
                )
                result = func(*args, **kwargs)
                duration = (time.time() - start) * 1000.0
                logger.log(
                    level,
                    "Exited %s; duration_ms=%.2f; return=%s",
                    func.__qualname__,
                    duration,
                    repr(result)[:100],
                )
                return result
            except Exception:
                duration = (time.time() - start) * 1000.0
                logger.exception(
                    "Exception in %s after %.2fms",
                    func.__qualname__,
                    duration,
                )
                raise

        return _wrapper

    return _decorator


def get_fileops_logger(
    base_dir: Optional[Path] = None, level: int = logging.INFO
) -> logging.Logger:
    """Return a logger dedicated to file operations (audit-capable).

    This logger writes to a rotating file under base_dir/logs/fileops.log and
    also to console if not already configured. Handlers are added idempotently.
    """
    name = "emumanager.fileops"
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Add console handler if missing
    has_console = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in logger.handlers
    )
    if not has_console:
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(ch)

    # Add rotating file handler
    has_rotating = any(
        isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers
    )
    if base_dir and not has_rotating:
        try:
            logs_dir = Path(base_dir) / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            rfh = logging.handlers.RotatingFileHandler(
                str(logs_dir / "fileops.log"),
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            rfh.setFormatter(logging.Formatter(_STD_FORMAT))
            logger.addHandler(rfh)
        except Exception:
            logger.debug(
                "Could not create rotating file handler for fileops logger at %s",
                base_dir,
            )

    # Prevent propagation to root to avoid duplicate entries
    logger.propagate = False
    return logger


def configure_logging(env: Optional[str] = "auto", level: int = logging.INFO):
    """Configure the root logger.

    env: 'auto' (default) | 'json' | 'human'
    - 'auto' chooses human-readable when stdout is a TTY, otherwise JSON.
    - 'json' forces JSON output.
    - 'human' forces a readable formatter.

    Returns the root logger.
    """
    # Determine mode
    chosen = env or os.getenv("EMUMANAGER_LOG_FORMAT", "auto")
    if isinstance(chosen, str):
        chosen = chosen.lower()
    mode = "human"
    if chosen == "json":
        mode = "json"
    elif chosen == "human":
        mode = "human"
    else:
        # auto: prefer human when interactive
        try:
            mode = "human" if sys.stdout.isatty() else "json"
        except Exception:
            mode = "json"

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Add one console handler idempotently (mark by name)
    if not any(
        getattr(h, "name", None) == "emumanager_console"
        for h in root_logger.handlers
    ):
        sh = logging.StreamHandler()
        sh.name = "emumanager_console"
        if mode == "json":
            sh.setFormatter(JsonFormatter())
        else:
            fmt = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            sh.setFormatter(fmt)
        root_logger.addHandler(sh)

    return root_logger


class QtLogHandler(logging.Handler):
    """
    A custom logging handler that emits a signal for each log record.
    This allows the GUI to connect to this signal and display logs
    in a thread-safe manner.
    """

    def __init__(self, signal_emitter):
        super().__init__()
        self.signal_emitter = signal_emitter

    def emit(self, record):
        try:
            msg = self.format(record)
            # Emit signal (thread-safe)
            # We assume signal_emitter has a 'emit_log' method that triggers a Qt signal
            if hasattr(self.signal_emitter, "emit_log"):
                self.signal_emitter.emit_log(msg, record.levelno)
        except Exception:
            self.handleError(record)


def setup_gui_logging(signal_emitter, level=logging.INFO):
    """
    Configures the root logger to send messages to the GUI via a Qt signal.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Add Qt Handler
    handler = QtLogHandler(signal_emitter)
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Also ensure we have a console handler for debugging
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        root_logger.addHandler(ch)
