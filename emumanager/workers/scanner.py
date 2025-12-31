from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable, Optional

from emumanager.library import LibraryDB, LibraryEntry
from emumanager.logging_cfg import log_call, set_correlation_id
from emumanager.workers.common import get_logger_for_gui

# Common archive/compressed extensions we should detect and mark in the DB.
ARCHIVE_EXTS = {
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".tgz",
    ".tbz2",
}


def is_compressed_file(p: Path) -> bool:
    """Heuristic: if any suffix indicates an archive/compressed file.

    This returns True for names like file.zip, file.iso.zip or file.cso.gz
    (i.e. any suffix in the chain matches ARCHIVE_EXTS).
    """
    try:
        return any(suffix.lower() in ARCHIVE_EXTS for suffix in p.suffixes)
    except Exception:
        return p.suffix.lower() in ARCHIVE_EXTS


@log_call(level=logging.INFO)
def worker_scan_library(
    base_dir: Path,
    log_msg: Callable[[str], None],
    progress_cb: Optional[Callable[[float, str], None]] = None,
    cancel_event=None,
):
    """
    Scans the library directory and updates the LibraryDB.
    """
    # Initialize correlation id and use structured logger wired to GUI
    set_correlation_id()
    logger = get_logger_for_gui(log_msg, name="emumanager.workers.scanner")
    logger.info(f"Starting library scan at {base_dir}")

    db = LibraryDB()

    # Determine roms directory
    # If base_dir has a 'roms' subdir, use it.
    # Otherwise, assume base_dir IS the roms directory if it contains system folders.
    roms_dir = base_dir / "roms"
    if not roms_dir.exists():
        # If there's no 'roms' subdir, base_dir might already be the roms folder.
        # Avoid scanning the entire filesystem by assuming base_dir is correct
        # when 'roms' is not present.
        roms_dir = base_dir

    if not roms_dir.exists():
        logger.warning(f"Directory not found: {roms_dir}")
        return

    # Get all existing entries from DB to check for removals
    existing_entries = {entry.path: entry for entry in db.get_all_entries()}
    found_paths = set()

    # Count total files for progress (approximate)
    # This might be slow, so maybe we skip total count or do a quick pass?
    # For now, let's just iterate and update.

    # We can iterate by system folders to give better progress feedback
    system_dirs = [
        d for d in roms_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
    ]
    total_systems = len(system_dirs)

    for i, sys_dir in enumerate(system_dirs):
        if cancel_event and cancel_event.is_set():
            logger.info("Scan cancelled.")
            return

        system_name = sys_dir.name
        if progress_cb:
            progress_cb(i / total_systems, f"Scanning {system_name}...")

        for root, _, files in os.walk(sys_dir):
            for file in files:
                if cancel_event and cancel_event.is_set():
                    return

                file_path = Path(root) / file
                str_path = str(file_path)
                found_paths.add(str_path)

                stat = file_path.stat()
                size = stat.st_size
                mtime = stat.st_mtime

                # Check if entry exists and is up to date
                entry = existing_entries.get(str_path)
                if entry:
                    if entry.size == size and entry.mtime == mtime:
                        continue  # No change

                # New or modified file
                # We don't calculate hashes here, just basic info
                # If the file is an archive/compressed file we mark it so the
                # rest of the application can decide to skip deep-inspection.
                detected_status = entry.status if entry else "UNKNOWN"
                if is_compressed_file(file_path):
                    detected_status = "COMPRESSED"
                    logger.info(
                        "Detected compressed/archive file, marking as COMPRESSED: %s",
                        file_path,
                    )

                new_entry = LibraryEntry(
                    path=str_path,
                    system=system_name,
                    size=size,
                    mtime=mtime,
                    crc32=entry.crc32 if entry else None,
                    md5=entry.md5 if entry else None,
                    sha1=entry.sha1 if entry else None,
                    sha256=entry.sha256 if entry else None,
                    status=detected_status,
                    match_name=entry.match_name if entry else None,
                    dat_name=entry.dat_name if entry else None,
                )
                db.update_entry(new_entry)

    # Remove deleted files
    for path in existing_entries:
        if path not in found_paths:
            db.remove_entry(path)

    logger.info("Library scan complete.")

    # Return stats
    total_count = db.get_total_count()
    total_size = db.get_total_size()

    return {"count": total_count, "size": total_size}
