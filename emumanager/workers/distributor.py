from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, TYPE_CHECKING

from emumanager.logging_cfg import log_call, set_correlation_id
from emumanager.manager import guess_system_for_file
from emumanager.workers.common import get_logger_for_gui, skip_if_compressed, WorkerResult

if TYPE_CHECKING:
    from emumanager.library import LibraryDB


def _is_distributable_file(file_path: Path, logger: logging.Logger) -> bool:
    """Verifica se o ficheiro deve ser processado pela distribuição."""
    # Skip hidden files or system files
    if file_path.name.startswith(".") or file_path.name in [
        "_INSTALL_LOG.txt",
        "ps2_db.csv",
        "keys.txt",
        "prod.keys",
    ]:
        return False

    # Skip files that scanner has already marked as compressed
    if skip_if_compressed(file_path, logger):
        return False
        
    return True


def _process_distribution_item(file_path: Path, base_path: Path, logger: logging.Logger, result: WorkerResult, library_db=None, cancel_event: Any = None):
    """Detecta o sistema alvo e executa a movimentação física."""
    if cancel_event and cancel_event.is_set():
        return
    
    item_start = datetime.now()
    system = guess_system_for_file(file_path)
    if not system:
        logger.warning(f"Could not determine system for: {file_path.name}")
        result.skipped_count += 1
        return

    target_dir = base_path / system
    target_path = target_dir / file_path.name

    if target_path.exists():
        logger.warning(f"File already exists in target: {target_path}. Skipping.")
        result.skipped_count += 1
        return

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Moving {file_path.name} -> {system}/")
        
        old_path_str = str(file_path.resolve())
        file_path.rename(target_path)
        
        # Update database if available
        if library_db:
            try:
                entry = library_db.get_entry(old_path_str)
                if entry:
                    entry.path = str(target_path.resolve())
                    library_db.update_entry(entry)
                    library_db.log_action(str(target_path), "DISTRIBUTED", f"Moved from root to {system}/")
            except Exception as e:
                logger.debug(f"Failed to update DB for distributed file {file_path.name}: {e}")
        
        duration = (datetime.now() - item_start).total_seconds()
        result.add_item_result(file_path, "success", duration, system=system)
        result.success_count += 1
    except Exception as e:
        logger.error(f"Error moving {file_path.name}: {e}")
        result.add_error(file_path, str(e))


@log_call(level=logging.INFO)
def worker_distribute_root(
    base_path: Path,
    log_cb: Callable[[str], None],
    progress_cb: Optional[Callable[[float, str], None]] = None,
    cancel_event: Any = None,
    library_db: Optional[Any] = None,
) -> WorkerResult:
    """
    Scans the root of base_path (roms folder) for files and moves them
    to their respective system subfolders based on extension/heuristics.
    
    Args:
        base_path: Root folder to scan for unorganized files
        log_cb: Logging callback
        progress_cb: Progress callback
        cancel_event: Cancellation event
        library_db: Optional LibraryDB instance to update file paths in database
    
    Returns WorkerResult with detailed stats.
    """
    start_time = datetime.now()
    set_correlation_id()
    logger = get_logger_for_gui(log_cb, name="emumanager.workers.distributor")
    logger.info(f"Scanning root folder for unorganized files: {base_path}")
    
    result = WorkerResult(task_name="Distribution")

    try:
        root_files = [f for f in base_path.iterdir() if f.is_file()]
    except Exception as e:
        logger.error(f"Failed to list files in {base_path}: {e}")
        result.add_error(base_path, str(e))
        result.duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        return result

    if not root_files:
        logger.info("No files found in root folder to distribute.")
        result.duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        return result

    total = len(root_files)

    for i, file_path in enumerate(root_files):
        if cancel_event and cancel_event.is_set():
            logger.warning("Distribution cancelled by user.")
            break
library_db, 
        if progress_cb:
            progress_cb(i / total, f"Distributing: {file_path.name}")

        if not _is_distributable_file(file_path, logger):
            result.skipped_count += 1
            continue

        _process_distribution_item(file_path, base_path, logger, result, cancel_event)

    result.duration_ms = (datetime.now() - start_time).total_seconds() * 1000
    logger.info(f"Distribution complete. {result}")
    return result
