"""Centralized logging helpers (Core Python Refactoring).

Oferece configuração idempotente de loggers, suporte para correlation IDs
via contextvars (seguro para async/threads) e saída JSON/Human-readable.
"""

from __future__ import annotations

import contextvars
import functools
import json
import logging
import logging.handlers
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable


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


_STD_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
_cid_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "emumanager_correlation_id", default=None
)


def set_correlation_id(cid: str | None = None) -> str:
    cid = cid or uuid.uuid4().hex
    _cid_var.set(cid)
    return cid


def get_correlation_id() -> str | None:
    return _cid_var.get()


class JsonFormatter(logging.Formatter):
    """Formatador JSON minimalista com metadados de execução."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "cid": get_correlation_id(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def log_call(level: int = logging.INFO):
    """Decorador para logging automático de entrada/saída de funções."""

    def _decorator(func: Callable):
        @functools.wraps(func)
        def _wrapper(*args, **kwargs):
            logger = logging.getLogger(func.__module__)
            start = time.time()
            try:
                logger.debug(f"Entering {func.__qualname__}")
                result = func(*args, **kwargs)
                duration = (time.time() - start) * 1000.0
                logger.log(level, f"Exited {func.__qualname__} ({duration:.2f}ms)")
                return result
            except Exception as e:
                logger.exception(f"Exception in {func.__qualname__}: {e}")
                raise

        return _wrapper

    return _decorator


def get_logger(
    name: str = "emumanager",
    base_dir: Path | None = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """Retorna um logger configurado (singleton por nome)."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter(_STD_FORMAT))
        logger.addHandler(ch)

        if base_dir:
            try:
                log_file = Path(base_dir) / "_INSTALL_LOG.txt"
                log_file.parent.mkdir(parents=True, exist_ok=True)
                fh = logging.FileHandler(log_file, encoding="utf-8")
                fh.setFormatter(logging.Formatter(_STD_FORMAT))
                logger.addHandler(fh)
            except Exception:
                pass
    return logger


def get_fileops_logger(base_dir: Path | None = None, level: int = logging.INFO) -> logging.Logger:
    """Shim de compatibilidade para logger de operações de ficheiro."""
    return get_logger("emumanager.fileops", base_dir=base_dir, level=level)


def setup_gui_logging(signal_emitter, level: int = logging.INFO):
    """Shim de compatibilidade para logging de GUI (Qt)."""
    return configure_logging(level=level)


def configure_logging(
    level: int = logging.INFO,
    base_dir: Path | None = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    """Configuração central do logger raiz."""
    root = logging.getLogger()
    root.setLevel(level)

    # Evitar duplicar handlers se chamado múltiplas vezes
    if not any(getattr(h, "name", None) == "emu_console" for h in root.handlers):
        mode_json = not sys.stdout.isatty()
        ch = logging.StreamHandler(sys.stdout)
        ch.name = "emu_console"
        ch.setFormatter(JsonFormatter() if mode_json else logging.Formatter(_STD_FORMAT))
        root.addHandler(ch)

    if base_dir and not any(getattr(h, "name", None) == "emu_file" for h in root.handlers):
        try:
            log_path = Path(base_dir) / "logs" / "emumanager.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.handlers.RotatingFileHandler(
                log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
            )
            fh.name = "emu_file"
            fh.setFormatter(logging.Formatter(_STD_FORMAT))
            root.addHandler(fh)
        except Exception:
            pass

    return root
