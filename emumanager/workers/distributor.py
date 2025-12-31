from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional
import logging

from emumanager.manager import guess_system_for_file
from emumanager.workers.common import skip_if_compressed, get_logger_for_gui
from emumanager.logging_cfg import set_correlation_id, log_call


@log_call(level=logging.INFO)
def worker_distribute_root(
    base_path: Path,
    log_cb: Callable[[str], None],
    progress_cb: Optional[Callable[[float, str], None]] = None,
    cancel_event: Any = None,
) -> dict:
    """
    Scans the root of base_path (roms folder) for files and moves them
    to their respective system subfolders based on extension/heuristics.
    """
    # Initialize correlation id and use structured logger wired to GUI
    set_correlation_id()
    logger = get_logger_for_gui(log_cb, name="emumanager.workers.distributor")
    logger.info(f"Scanning root folder for unorganized files: {base_path}")

    # Only scan files directly in base_path
    try:
        root_files = [f for f in base_path.iterdir() if f.is_file()]
    except Exception as e:
        logger.error(f"Failed to list files in {base_path}: {e}")
        return {"moved": 0, "skipped": 0, "errors": 1}

    if not root_files:
        logger.info("No files found in root folder to distribute.")
        return {"moved": 0, "skipped": 0, "errors": 0}

    stats = {"moved": 0, "skipped": 0, "errors": 0}
    total = len(root_files)

    for i, file_path in enumerate(root_files):
        if cancel_event and cancel_event.is_set():
            logger.warning("Distribution cancelled.")
            break

        if progress_cb:
            progress_cb(i / total, f"Distributing: {file_path.name}")

        try:
            # Skip hidden files or system files
            if file_path.name.startswith(".") or file_path.name in [
                "_INSTALL_LOG.txt",
                "ps2_db.csv",
                "keys.txt",
                "prod.keys",
            ]:
                stats["skipped"] += 1
                continue

            # Skip files that scanner has already marked as compressed
            if skip_if_compressed(file_path, logger):
                stats["skipped"] += 1
                continue

            system = guess_system_for_file(file_path)
            if system:
                target_dir = base_path / system
                target_dir.mkdir(parents=True, exist_ok=True)
                target_path = target_dir / file_path.name

                if target_path.exists():
                    logger.warning(
                        f"File already exists in target: {target_path}. Skipping."
                    )
                    stats["skipped"] += 1
                else:
                    logger.info(f"Moving {file_path.name} -> {system}/")
                    file_path.rename(target_path)
                    stats["moved"] += 1
            else:
                logger.warning(f"Could not determine system for: {file_path.name}")
                stats["skipped"] += 1

        except Exception as e:
            logger.error(f"Error moving {file_path.name}: {e}")
            stats["errors"] += 1

    logger.info(f"Distribution complete. Stats: {stats}")
    return stats
