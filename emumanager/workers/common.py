from __future__ import annotations
import logging
import hashlib
from typing import Callable, Any, Optional
from pathlib import Path

# Constants for logging
LOG_WARN = "WARN: "
LOG_ERROR = "ERROR: "
LOG_EXCEPTION = "EXCEPTION: "
MSG_CANCELLED = "Operation cancelled by user."

class GuiLogHandler(logging.Handler):
    """Logging handler that redirects to the GUI callback."""
    def __init__(self, log_callback: Callable[[str], None]):
        super().__init__()
        self.log_callback = log_callback

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_callback(msg)
        except Exception:
            self.handleError(record)


class GuiLogger:
    """Adapter to redirect logs to the GUI's log_msg method."""
    def __init__(self, log_callback: Callable[[str], None]):
        self.log_callback = log_callback

    def info(self, msg, *args):
        self.log_callback(msg % args if args else msg)

    def warning(self, msg, *args):
        self.log_callback(LOG_WARN + (msg % args if args else msg))

    def error(self, msg, *args):
        self.log_callback(LOG_ERROR + (msg % args if args else msg))

    def debug(self, msg, *args):
        pass  # Ignore debug logs in GUI by default

    def exception(self, msg, *args):
        self.log_callback(LOG_EXCEPTION + (msg % args if args else msg))

def calculate_file_hash(file_path: Path, algo: str = "md5", chunk_size: int = 8192, progress_cb=None) -> str:
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

def create_file_progress_cb(main_progress_cb, start_prog: float, file_weight: float, filename: str):
    """
    Creates a callback for file operations (like hashing) that updates the main progress bar.
    
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

def _clean_junk_files(files: list[Path], args: Any, logger: GuiLogger, progress_cb: Optional[Callable[[float, str], None]] = None) -> int:
    count = 0
    total = len(files)
    junk_exts = {".txt", ".nfo", ".url", ".lnk", ".website"}
    
    for i, f in enumerate(files):
        if progress_cb and i % 50 == 0:
            progress_cb(i / total, f"Scanning junk... {int(i/total*100)}%")
            
        if f.suffix.lower() in junk_exts:
            try:
                if not getattr(args, "dry_run", False):
                    f.unlink()
                logger.info(f"Deleted junk file: {f.name}")
                count += 1
            except Exception as e:
                logger.error(f"Failed to delete {f.name}: {e}")
    return count

def _clean_empty_dirs(dirs: list[Path], args: Any, logger: GuiLogger, progress_cb: Optional[Callable[[float, str], None]] = None) -> int:
    count = 0
    total = len(dirs)
    # Sort reverse to delete nested empty dirs first
    sorted_dirs = sorted(dirs, key=lambda x: len(str(x)), reverse=True)
    
    for i, d in enumerate(sorted_dirs):
        if progress_cb and i % 10 == 0:
            progress_cb(i / total, f"Scanning dirs... {int(i/total*100)}%")
            
        try:
            if not any(d.iterdir()):
                if not getattr(args, "dry_run", False):
                    d.rmdir()
                logger.info(f"Deleted empty dir: {d.name}")
                count += 1
        except Exception:
            pass
    return count

def worker_clean_junk(base_path: Path, args: Any, log_cb: Callable[[str], None], list_files_fn: Callable[[Path], list[Path]], list_dirs_fn: Callable[[Path], list[Path]]) -> str:
    """Worker function for cleaning junk files."""
    logger = GuiLogger(log_cb)
    
    files = list_files_fn(base_path)
    dirs = list_dirs_fn(base_path)
    
    progress_cb = getattr(args, "progress_callback", None)
    
    deleted_files = _clean_junk_files(files, args, logger, progress_cb)
    deleted_dirs = _clean_empty_dirs(dirs, args, logger, progress_cb)
            
    if progress_cb:
        progress_cb(1.0, "Cleanup complete")
            
    return f"Cleanup complete. Deleted {deleted_files} files and {deleted_dirs} empty directories."
