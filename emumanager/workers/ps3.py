from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable, Optional

from emumanager.logging_cfg import log_call, set_correlation_id
from emumanager.ps3 import database as ps3_db
from emumanager.ps3 import metadata as ps3_meta
from emumanager.workers.common import (
    MSG_CANCELLED,
    GuiLogger,
    VerifyResult,
    calculate_file_hash,
    create_file_progress_cb,
    emit_verification_result,
    find_target_dir,
    get_logger_for_gui,
    make_result_collector,
    skip_if_compressed,
)

PARAM_SFO = "PARAM.SFO"
MSG_PS3_DIR_NOT_FOUND = "PS3 ROMs directory not found."
PS3_SUBDIRS = ["roms/ps3", "ps3"]


def _process_ps3_item(
    item: Path,
    logger: GuiLogger,
    deep_verify: bool = False,
    progress_cb: Optional[Callable[[float], None]] = None,
    per_file_cb: Optional[Callable[[VerifyResult], None]] = None,
) -> str:
    """
    Process a PS3 item (file or folder) to extract serial and identify title.
    Returns: 'found', 'unknown', or 'skip'.
    """
    meta = ps3_meta.get_metadata(item)
    serial = meta.get("serial")

    title = None
    status = "unknown"

    if serial:
        title = ps3_db.db.get_title(serial)
        if not title:
            title = meta.get("title", "Unknown Title")
        status = "found"
    else:
        title = meta.get("title", "Unknown")

    md5_val = None
    sha1_val = None

    if deep_verify and item.is_file():
        logger.info(f"Hashing {item.name}...")
        md5_val = calculate_file_hash(item, "md5", progress_cb=progress_cb)
        sha1_val = calculate_file_hash(item, "sha1", progress_cb=None)

    emit_verification_result(
        per_file_cb=per_file_cb,
        filename=item.name,
        status="VERIFIED" if status == "found" else "UNKNOWN",
        system="PS3",
        serial=serial,
        title=title,
        md5=md5_val,
        sha1=sha1_val,
    )

    info_str = f"[{serial or 'No Serial'}] {title}"
    if md5_val:
        info_str += f" | MD5: {md5_val}"

    logger.info(f"{info_str} -> {item.name}")

    return status


def _scan_ps3_folders(
    dirs: list[Path],
    logger: GuiLogger,
    args: Any,
    per_file_cb: Optional[Callable[[VerifyResult], None]] = None,
) -> tuple[int, int]:
    found = 0
    unknown = 0
    cancel_event = getattr(args, "cancel_event", None)

    for d in dirs:
        if cancel_event and cancel_event.is_set():
            break

        # Check if it's a game folder (has PARAM.SFO or PS3_GAME)
        if (d / PARAM_SFO).exists() or (d / "PS3_GAME" / PARAM_SFO).exists():
            # Respect compressed markers in the library DB
            if skip_if_compressed(d, logger):
                unknown += 1
                continue

            res = _process_ps3_item(
                d, logger, deep_verify=False, per_file_cb=per_file_cb
            )  # Don't hash folders
            if res == "found":
                found += 1
            elif res == "unknown":
                unknown += 1
    return found, unknown


def _scan_ps3_files(
    files: list[Path],
    logger: GuiLogger,
    args: Any,
    deep_verify: bool,
    progress_cb: Optional[Callable[[float, str], None]],
    per_file_cb: Optional[Callable[[VerifyResult], None]] = None,
) -> tuple[int, int]:
    found = 0
    unknown = 0
    total_files = len(files)
    cancel_event = getattr(args, "cancel_event", None)

    for i, f in enumerate(files):
        if cancel_event and cancel_event.is_set():
            logger.warning(MSG_CANCELLED)
            break

        # Calculate progress range for this file
        start_prog = i / total_files
        file_weight = 1.0 / total_files

        file_prog_cb = create_file_progress_cb(
            progress_cb, start_prog, file_weight, f.name
        )

        if progress_cb:
            progress_cb(start_prog, f"Verifying {f.name}...")

        if f.suffix.lower() in (".iso", ".pkg"):
            # Skip compressed files previously detected by scanner
            if skip_if_compressed(f, logger):
                unknown += 1
                continue

            res = _process_ps3_item(
                f,
                logger,
                deep_verify=deep_verify,
                progress_cb=file_prog_cb,
                per_file_cb=per_file_cb,
            )
            if res == "found":
                found += 1
            elif res == "unknown":
                unknown += 1
    return found, unknown


@log_call(level=logging.INFO)
def worker_ps3_verify(
    base_path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    list_files_fn: Callable[[Path], list[Path]],
    list_dirs_fn: Callable[[Path], list[Path]] = None,
) -> str:
    """Worker function for PS3 verification."""
    # Initialize correlation id and use structured logger wired to GUI
    set_correlation_id()
    logger = get_logger_for_gui(log_cb, name="emumanager.workers.ps3")

    target_dir = find_target_dir(base_path, PS3_SUBDIRS)
    if not target_dir:
        return MSG_PS3_DIR_NOT_FOUND

    # Try to load DB
    db_path = base_path / "ps3_db.csv"
    if db_path.exists():
        ps3_db.db.load_from_csv(db_path)
        logger.info(f"Loaded PS3 database from {db_path}")

    logger.info(f"Scanning PS3 content in {target_dir}...")

    files = list_files_fn(target_dir)
    progress_cb = getattr(args, "progress_callback", None)
    deep_verify = getattr(args, "deep_verify", False)

    # Setup result collector
    results_list = getattr(args, "results", None)
    per_file_cb = make_result_collector(results_list, getattr(args, "on_result", None))

    # Scan files (ISOs, PKGs)
    found, unknown = _scan_ps3_files(
        files, logger, args, deep_verify, progress_cb, per_file_cb
    )

    # Scan folders (JB format)
    if list_dirs_fn:
        dirs = list_dirs_fn(target_dir)
        f_found, f_unknown = _scan_ps3_folders(dirs, logger, args, per_file_cb)
        found += f_found
        unknown += f_unknown

    if progress_cb:
        progress_cb(1.0, "PS3 Verification complete")

    return f"Scan complete. Identified: {found}, Unknown: {unknown}"


def _organize_ps3_item(item: Path, args: Any, logger: GuiLogger) -> bool:
    meta = ps3_meta.get_metadata(item)
    serial = meta.get("serial")
    internal_title = meta.get("title")

    if not serial:
        return False

    db_title = ps3_db.db.get_title(serial)
    title = db_title if db_title else internal_title

    if not title:
        title = "Unknown"

    # Sanitize
    clean_title = re.sub(r'[<>:"/\\|?*]', "", title).strip()
    new_name = f"{clean_title} [{serial}]"

    if item.is_file():
        new_name += item.suffix

    new_path = item.parent / new_name

    if item.name == new_name:
        return False

    if new_path.exists():
        logger.warning(f"Target already exists: {new_name}")
        return False

    try:
        if not getattr(args, "dry_run", False):
            item.rename(new_path)
        logger.info(f"Renamed: {item.name} -> {new_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to rename {item.name}: {e}")
        return False


def _organize_ps3_folders(
    dirs: list[Path], args: Any, logger: GuiLogger
) -> tuple[int, int]:
    renamed = 0
    skipped = 0
    cancel_event = getattr(args, "cancel_event", None)

    for d in dirs:
        if cancel_event and cancel_event.is_set():
            break

        if (d / PARAM_SFO).exists() or (d / "PS3_GAME" / PARAM_SFO).exists():
            if _organize_ps3_item(d, args, logger):
                renamed += 1
            else:
                skipped += 1
    return renamed, skipped


@log_call(level=logging.INFO)
def worker_ps3_organize(
    base_path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    list_files_fn: Callable[[Path], list[Path]],
    list_dirs_fn: Callable[[Path], list[Path]] = None,
) -> str:
    """Worker function for PS3 organization."""
    # Initialize correlation id and use structured logger wired to GUI
    set_correlation_id()
    logger = get_logger_for_gui(log_cb, name="emumanager.workers.ps3")

    target_dir = find_target_dir(base_path, PS3_SUBDIRS)
    if not target_dir:
        return MSG_PS3_DIR_NOT_FOUND

    # Try to load DB
    db_path = base_path / "ps3_db.csv"
    if db_path.exists():
        ps3_db.db.load_from_csv(db_path)
        logger.info(f"Loaded PS3 database from {db_path}")

    renamed = 0
    skipped = 0

    files = list_files_fn(target_dir)
    total_files = len(files)
    progress_cb = getattr(args, "progress_callback", None)
    cancel_event = getattr(args, "cancel_event", None)

    # Organize ISOs/PKGs
    for i, f in enumerate(files):
        if cancel_event and cancel_event.is_set():
            logger.warning(MSG_CANCELLED)
            break

        if progress_cb:
            progress_cb(i / total_files, f"Organizing {f.name}...")

        if f.suffix.lower() in (".iso", ".pkg"):
            # Respect compressed markers
            if skip_if_compressed(f, logger):
                skipped += 1
                continue

            if _organize_ps3_item(f, args, logger):
                renamed += 1
            else:
                skipped += 1

    # Organize Folders
    if list_dirs_fn and not (cancel_event and cancel_event.is_set()):
        dirs = list_dirs_fn(target_dir)
        # Check for compressed markers when organizing folders.
        # The folder-level helper will call _organize_ps3_item after existence
        # checks; it will increment the skipped count for items it does not
        # process, so we defer to it for folder-level handling.
        f_renamed, f_skipped = _organize_ps3_folders(dirs, args, logger)
        renamed += f_renamed
        skipped += f_skipped

    if progress_cb:
        progress_cb(1.0, "PS3 Organization complete")

    return f"PS3 Organization complete. Renamed: {renamed}, Skipped: {skipped}"
