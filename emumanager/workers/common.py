from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Callable, Optional

from emumanager.common.models import VerifyResult
from emumanager.logging_cfg import get_correlation_id, set_correlation_id
from emumanager.library import LibraryDB, LibraryEntry

# Constants for logging
LOG_WARN = "WARN: "
LOG_ERROR = "ERROR: "
LOG_EXCEPTION = "EXCEPTION: "
MSG_CANCELLED = "Operation cancelled by user."


class GuiLogHandler(logging.Handler):
    """Logging handler that redirects LogRecords to the GUI callback.

    The handler is robust: it ensures a formatter is present (defaults to the
    project's JsonFormatter) and shields the GUI from handler errors.
    """

    def __init__(
        self,
        log_callback: Callable[[str], None],
        formatter: logging.Formatter | None = None,
    ):
        super().__init__()
        self.log_callback = log_callback
        # Import here to avoid circular import at module import time
        try:
            from emumanager.logging_cfg import JsonFormatter

            default_formatter = JsonFormatter()
        except Exception:
            default_formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s"
            )

        self.setFormatter(formatter or default_formatter)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            # Guard the callback in case it raises
            try:
                self.log_callback(msg)
            except Exception:
                # Best-effort: swallow GUI callback errors to avoid crashing app
                pass
        except Exception:
            self.handleError(record)


def get_logger_for_gui(
    log_callback: Callable[[str], None],
    name: str = "emumanager",
    level: int = logging.INFO,
) -> logging.Logger:
    """Create or return a logger wired to a GuiLogHandler.

    This is idempotent: if a handler for the provided callback is already
    attached it won't be added again.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Check existing handlers for a GuiLogHandler using the same callback
    for h in logger.handlers:
        if (
            isinstance(h, GuiLogHandler)
            and getattr(h, "log_callback", None) == log_callback
        ):
            return logger

    # Add a new GuiLogHandler
    handler = GuiLogHandler(log_callback)
    # Keep structured output by default (JsonFormatter is set inside GuiLogHandler)
    logger.addHandler(handler)
    # Prevent propagation to root to avoid duplicate messages in console
    logger.propagate = False
    return logger


class GuiLogger:
    """Adapter to redirect logs to the GUI's log_msg method."""

    def __init__(self, log_callback: Callable[[str], None]):
        self.log_callback = log_callback

    def info(self, msg, *args):
        cid = get_correlation_id()
        prefix = f"[{cid}] " if cid else ""
        self.log_callback(prefix + (msg % args if args else msg))

    def warning(self, msg, *args):
        cid = get_correlation_id()
        prefix = f"[{cid}] " if cid else ""
        self.log_callback(prefix + LOG_WARN + (msg % args if args else msg))

    def error(self, msg, *args):
        cid = get_correlation_id()
        prefix = f"[{cid}] " if cid else ""
        self.log_callback(prefix + LOG_ERROR + (msg % args if args else msg))

    def debug(self, msg, *args):
        pass  # Ignore debug logs in GUI by default

    def exception(self, msg, *args):
        cid = get_correlation_id()
        prefix = f"[{cid}] " if cid else ""
        self.log_callback(prefix + LOG_EXCEPTION + (msg % args if args else msg))


def calculate_file_hash(
    file_path: Path,
    algo: str = "md5",
    chunk_size: int = 8192,
    progress_cb=None,
) -> str:
    """Calculate hash of a file."""
    h = hashlib.new(algo)
    total_size = file_path.stat().st_size
    processed = 0

    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
            processed += len(chunk)
            if progress_cb:
                progress_cb(processed / total_size)
    return h.hexdigest()


def create_file_progress_cb(
    main_progress_cb: Optional[Callable[[float, str], None]],
    start_prog: float,
    file_weight: float,
    filename: str,
):
    """
    Creates a callback for file operations that updates the main progress bar.

    Args:
        main_progress_cb: The main progress callback (accepts float, str).
        start_prog: The progress value (0.0-1.0) where this file starts.
        file_weight: The portion of the total progress this file represents (0.0-1.0).
        filename: The name of the file being processed.
    """
    if not main_progress_cb:
        return None

    def cb(file_prog: float):
        # Calculate total progress: start + (file_progress * weight)
        current = start_prog + (file_prog * file_weight)
        main_progress_cb(current, f"Processing {filename} ({int(file_prog * 100)}%)...")

    return cb


def find_target_dir(base_path: Path, subdirs: list[str]) -> Optional[Path]:
    """Finds a target directory from a list of candidates relative to base_path."""
    for sub in subdirs:
        p = base_path / sub
        if p.exists() and p.is_dir():
            return p
    # Fallback: check if base_path itself matches one of the subdirs names
    for sub in subdirs:
        if base_path.name == Path(sub).name:
            return base_path
    return None


def _clean_junk_files(
    files: list[Path],
    args: Any,
    logger: GuiLogger,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> int:
    count = 0
    total = len(files)
    junk_exts = {".txt", ".nfo", ".url", ".lnk", ".website"}

    for i, f in enumerate(files):
        if progress_cb and i % 50 == 0:
            progress_cb(i / total, f"Scanning junk... {int(i / total * 100)}%")

        if f.suffix.lower() in junk_exts:
            try:
                if not getattr(args, "dry_run", False):
                    from emumanager.common.fileops import safe_unlink

                    safe_unlink(f, logger)
                else:
                    logger.info(f"[DRY-RUN] Would delete junk file: {f.name}")
                count += 1
            except Exception as e:
                logger.error(f"Failed to delete {f.name}: {e}")
    return count


def _clean_empty_dirs(
    dirs: list[Path],
    args: Any,
    logger: GuiLogger,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> int:
    count = 0
    total = len(dirs)
    # Sort reverse to delete nested empty dirs first
    sorted_dirs = sorted(dirs, key=lambda x: len(str(x)), reverse=True)

    for i, d in enumerate(sorted_dirs):
        if progress_cb and i % 10 == 0:
            progress_cb(i / total, f"Scanning dirs... {int(i / total * 100)}%")

        try:
            if not any(d.iterdir()):
                if not getattr(args, "dry_run", False):
                    d.rmdir()
                logger.info(f"Deleted empty dir: {d.name}")
                count += 1
        except Exception:
            pass
    return count


def worker_clean_junk(
    base_path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    list_files_fn: Callable[[Path], list[Path]],
    list_dirs_fn: Callable[[Path], list[Path]],
) -> str:
    """Worker function for cleaning junk files."""
    # Initialize correlation id and use structured logger wired to GUI
    set_correlation_id()
    logger = get_logger_for_gui(log_cb, name="emumanager.workers.common")

    files = list_files_fn(base_path)
    dirs = list_dirs_fn(base_path)

    progress_cb = getattr(args, "progress_callback", None)

    deleted_files = _clean_junk_files(files, args, logger, progress_cb)
    deleted_dirs = _clean_empty_dirs(dirs, args, logger, progress_cb)

    if progress_cb:
        progress_cb(1.0, "Cleanup complete")

    return (
        f"Cleanup complete. Deleted {deleted_files} files and "
        f"{deleted_dirs} empty directories."
    )


def skip_if_compressed(
    file_path: Path, logger: GuiLogger, db: LibraryDB | None = None
) -> bool:
    """Check library DB for this file and, if marked COMPRESSED, log and
    create an action entry. Returns True if processing should be skipped.

    Accepts an optional `db` parameter so callers (and tests) can inject a
    specific LibraryDB instance (useful for temporary DBs). If `db` is None,
    a default LibraryDB() is used (backwards compatible).
    """
    try:
        local_db = db if db is not None else LibraryDB()
        entry = local_db.get_entry(str(file_path))
        if entry and entry.status == "COMPRESSED":
            logger.info(f"Skipping compressed file (logged): {file_path.name}")
            try:
                local_db.log_action(
                    str(file_path),
                    "SKIPPED_COMPRESSED",
                    "Scanner detected compressed file",
                )
            except Exception:
                # If logging fails, don't break the worker; just proceed to skip
                logger.warning(f"Failed to write action log for {file_path.name}")
            return True
    except Exception:
        # If DB unavailable, don't skip — let the worker decide (avoid false skips)
        logger.debug(f"Could not check library DB for {file_path}")
    return False


def emit_verification_result(
    per_file_cb: Optional[Callable[[VerifyResult], None]] = None,
    filename: str | Path = "",
    status: str = "UNKNOWN",
    serial: Optional[str] = None,
    title: Optional[str] = None,
    md5: Optional[str] = None,
    sha1: Optional[str] = None,
    crc: Optional[str] = None,
    **kwargs,
):
    """Emit a standardized verification result."""
    if not per_file_cb:
        return
    try:
        match_name = None
        if title and serial:
            match_name = f"{title} [{serial}]"
        elif title:
            match_name = title
        elif serial:
            match_name = f"[{serial}]"

        fname = filename.name if isinstance(filename, Path) else str(filename)
        fpath = str(filename) if isinstance(filename, Path) else None

        res = VerifyResult(
            filename=fname,
            status=status,
            match_name=match_name,
            crc=crc,
            sha1=sha1,
            md5=md5,
            sha256=None,
            full_path=fpath,
        )
        per_file_cb(res)
    except Exception:
        pass


def make_result_collector(per_file_cb, results_list):
    """Create a collector function that feeds both a callback and a list."""

    def _collector(d: Any, _cb=per_file_cb, _lst=results_list):
        if callable(_cb):
            try:
                _cb(d)
            except Exception:
                pass
        if isinstance(_lst, list):
            _lst.append(d)

    return _collector


def identify_game_by_hash(
    file_path: Path,
    db: LibraryDB | None = None,
    progress_cb: Optional[Callable[[float], None]] = None,
) -> Optional[LibraryEntry]:
    """Try to identify a library entry for `file_path` by computing a strong
    hash (sha1) and looking up the library DB. Returns a LibraryEntry if a
    matching hash is found, otherwise None.

    This function is intentionally conservative: it computes only the sha1
    (fast enough for typical ROM sizes) and consults the library DB's
    `find_entry_by_hash` method. Callers can then prefer the returned
    entry's `match_name` or `dat_name` when constructing a canonical filename
    for renaming.
    """
    try:
        local_db = db if db is not None else LibraryDB()
        # Compute SHA1; use progress callback if provided
        sha1 = calculate_file_hash(file_path, "sha1", progress_cb=progress_cb)
        if not sha1:
            return None
        found = local_db.find_entry_by_hash(sha1)
        return found
    except Exception:
        return None


def ensure_hashes_in_db(
    file_path: Path,
    db: LibraryDB | None = None,
    progress_cb: Optional[Callable[[float], None]] = None,
):
    """Ensure MD5 and SHA1 hashes for `file_path` are present in the LibraryDB.

    - If an entry exists and hashes are present, nothing is done.
    - Otherwise compute MD5 and SHA1 and upsert a LibraryEntry with those values.

    Returns a tuple (md5, sha1).
    """
    try:
        local_db = db if db is not None else LibraryDB()
        p = Path(file_path)
        # Try to read existing entry
        entry = local_db.get_entry(str(p))
        md5 = entry.md5 if entry and entry.md5 else None
        sha1 = entry.sha1 if entry and entry.sha1 else None

        if md5 and sha1:
            return md5, sha1

        # Compute missing hashes
        if not md5:
            md5 = calculate_file_hash(p, "md5", progress_cb=progress_cb)
        if not sha1:
            sha1 = calculate_file_hash(p, "sha1", progress_cb=progress_cb)

        # Build/update LibraryEntry
        try:
            st = p.stat()
            new_entry = LibraryEntry(
                path=str(p.resolve()),
                system=(entry.system if entry else ""),
                size=st.st_size,
                mtime=st.st_mtime,
                crc32=(entry.crc32 if entry else None),
                md5=md5,
                sha1=sha1,
                sha256=(entry.sha256 if entry else None),
                status=(entry.status if entry else ""),
                match_name=(entry.match_name if entry else None),
                dat_name=(entry.dat_name if entry else None),
            )
            local_db.update_entry(new_entry)
        except Exception:
            # Best-effort: ignore DB write failures
            pass

        return md5, sha1
    except Exception:
        return None, None
