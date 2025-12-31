from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable, Optional

from emumanager.converters import psp_converter
from emumanager.library import LibraryDB
from emumanager.logging_cfg import log_call, set_correlation_id
from emumanager.psp import database as psp_db
from emumanager.psp import metadata as psp_meta
from emumanager.workers.common import (
    MSG_CANCELLED,
    GuiLogger,
    VerifyResult,
    calculate_file_hash,
    create_file_progress_cb,
    emit_verification_result,
    get_logger_for_gui,
    identify_game_by_hash,
    make_result_collector,
    skip_if_compressed,
)

MSG_PSP_DIR_NOT_FOUND = "PSP ROMs directory not found."


def _process_psp_item(
    item: Path,
    logger: GuiLogger,
    deep_verify: bool = False,
    progress_cb: Optional[Callable[[float], None]] = None,
    per_file_cb: Optional[Callable[[VerifyResult], None]] = None,
) -> str:
    """
    Process a PSP item (file) to extract serial and identify title.
    Returns: 'found', 'unknown', or 'skip'.
    """
    meta = psp_meta.get_metadata(item)
    serial = meta.get("serial")

    title = None
    status = "unknown"

    if serial:
        title = psp_db.db.get_title(serial)
        if not title:
            title = meta.get("title", "Unknown Title")
        status = "found"
    else:
        title = meta.get("title", "Unknown")

    md5_val = None
    sha1_val = None

    if deep_verify:
        logger.info(f"Hashing {item.name}...")
        md5_val = calculate_file_hash(item, "md5", progress_cb=progress_cb)
        sha1_val = calculate_file_hash(item, "sha1", progress_cb=None)

    emit_verification_result(
        per_file_cb=per_file_cb,
        filename=item.name,
        status="VERIFIED" if status == "found" else "UNKNOWN",
        system="PSP",
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


def _resolve_psp_target(base_path: Path) -> Optional[Path]:
    candidates = [base_path / "roms" / "psp", base_path / "psp", base_path]
    return next((d for d in candidates if d.exists()), None)


@log_call(level=logging.INFO)
def worker_psp_verify(
    base_path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    list_files_fn: Callable[[Path], list[Path]],
    **kwargs
) -> str:
    """Worker function for PSP verification."""
    # Initialize correlation id for this worker run for traceability
    set_correlation_id()
    # Use a standard logging.Logger wired to the GUI via GuiLogHandler to
    # demonstrate structured logs. The returned logger implements the
    # standard logging API (info/debug/warning/error).
    logger = get_logger_for_gui(log_cb, name="emumanager.workers.psp")

    target_dir = _resolve_psp_target(base_path)

    if not target_dir:
        return MSG_PSP_DIR_NOT_FOUND

    # Try to load DB
    db_path = base_path / "psp_db.csv"
    if db_path.exists():
        psp_db.db.load_from_csv(db_path)
        logger.info(f"Loaded PSP database from {db_path}")

    logger.info(f"Scanning PSP content in {target_dir}...")

    found = 0
    unknown = 0

    files = list_files_fn(target_dir)
    total = len(files)
    progress_cb = getattr(args, "progress_callback", None)
    cancel_event = getattr(args, "cancel_event", None)
    deep_verify = getattr(args, "deep_verify", False)

    # Setup result collector
    results_list = getattr(args, "results", None)
    per_file_cb = make_result_collector(results_list, getattr(args, "on_result", None))

    for i, f in enumerate(files):
        if cancel_event and cancel_event.is_set():
            logger.warning(MSG_CANCELLED)
            break

        # If scanner flagged this file as compressed, skip and log action
        try:
            if skip_if_compressed(f, logger):
                continue
        except Exception:
            # Non-fatal: proceed if helper fails
            pass

        # Calculate progress range for this file
        start_prog = i / total
        file_weight = 1.0 / total

        file_prog_cb = create_file_progress_cb(
            progress_cb, start_prog, file_weight, f.name
        )

        if progress_cb:
            progress_cb(start_prog, f"Verifying {f.name}...")

        if f.suffix.lower() in (".iso", ".cso", ".pbp"):
            res = _process_psp_item(
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

    if progress_cb:
        progress_cb(1.0, "PSP Verification complete")

    return f"Scan complete. Identified: {found}, Unknown: {unknown}"


def _compress_psp_file(f: Path, args: Any, logger: GuiLogger) -> bool:
    cso_path = f.with_suffix(".cso")
    if cso_path.exists():
        logger.info(f"Skipping {f.name}, CSO already exists.")
        return False

    level = getattr(args, "level", 9)
    dry_run = getattr(args, "dry_run", False)

    # Compute and persist hashes for the source file before compressing so
    # verification data survives removal of the original.
    try:
        from emumanager.workers.common import ensure_hashes_in_db

        md5_val, sha1_val = ensure_hashes_in_db(f)
    except Exception:
        md5_val, sha1_val = (None, None)

    logger.info(f"Compressing {f.name} -> {cso_path.name} (Level {level})")

    if psp_converter.compress_to_cso(f, cso_path, level=level, dry_run=dry_run):
        logger.info(f"Compressed: {f.name}")

        # If the original is removed, attach the original hashes to the
        # new CSO entry so verification history remains available.
        if getattr(args, "rm_originals", False) and not dry_run:
            try:
                from emumanager.common.fileops import safe_unlink

                safe_unlink(f, logger)
            except Exception as e:
                logger.error(f"Failed to remove original: {e}")

        try:
            # Update library DB for cso_path with known hashes
            from emumanager.library import LibraryDB, LibraryEntry

            lib_db = LibraryDB()
            st = cso_path.stat() if cso_path.exists() else None
            if st:
                src_entry = lib_db.get_entry(str(f))
                system_name = src_entry.system if src_entry else "psp"
                new_entry = LibraryEntry(
                    path=str(cso_path.resolve()),
                    system=system_name,
                    size=st.st_size,
                    mtime=st.st_mtime,
                    crc32=None,
                    md5=md5_val,
                    sha1=sha1_val,
                    sha256=None,
                    status="COMPRESSED",
                    match_name=None,
                    dat_name=None,
                )
                lib_db.update_entry(new_entry)
                try:
                    lib_db.log_action(
                        str(cso_path), "COMPRESSED", f"Compressed from {f.name}"
                    )
                except Exception:
                    logger.warning(
                        f"Failed to record compress action for {cso_path.name}"
                    )
        except Exception:
            pass

        return True
    else:
        logger.error(f"Failed to compress {f.name}")
        return False


@log_call(level=logging.INFO)
def worker_psp_compress(
    base_path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    list_files_fn: Callable[[Path], list[Path]],
    **kwargs
) -> str:
    """Worker function for PSP compression (ISO -> CSO)."""
    # Initialize correlation id for this worker run for traceability
    set_correlation_id()
    logger = get_logger_for_gui(log_cb, name="emumanager.workers.psp")

    target_dir = _resolve_psp_target(base_path)

    if not target_dir:
        return MSG_PSP_DIR_NOT_FOUND

    files = list_files_fn(target_dir)
    iso_files = [f for f in files if f.suffix.lower() == ".iso"]

    if not iso_files:
        return "No ISO files found to compress."

    logger.info(f"Found {len(iso_files)} ISO files to compress.")

    success = 0
    failed = 0
    skipped = 0

    total = len(iso_files)
    progress_cb = getattr(args, "progress_callback", None)
    cancel_event = getattr(args, "cancel_event", None)

    for i, f in enumerate(iso_files):
        if cancel_event and cancel_event.is_set():
            logger.warning(MSG_CANCELLED)
            break

        if progress_cb:
            progress_cb(i / total, f"Compressing {f.name}...")

        # Skip compressed files (marked by scanner) before attempting compress
        try:
            if skip_if_compressed(f, logger):
                skipped += 1
                continue
        except Exception:
            pass

        if _compress_psp_file(f, args, logger):
            success += 1
        else:
            if f.with_suffix(".cso").exists():
                skipped += 1
            else:
                failed += 1

    if progress_cb:
        progress_cb(1.0, "PSP Compression complete")

    return (
        f"Compression complete. Success: {success}, "
        f"Failed: {failed}, Skipped: {skipped}"
    )


@log_call(level=logging.INFO)
def worker_psp_compress_single(
    path: Path, args: Any, log_cb: Callable[[str], None], **kwargs
) -> str:
    """Single-file wrapper for PSP compression (ISO -> CSO).

    This mirrors the directory-based worker but restricts the operation to the
    single provided file. Returns a summary string similar to the directory
    worker.
    """
    # Initialize correlation id for this single-file operation
    set_correlation_id()
    logger = get_logger_for_gui(log_cb, name="emumanager.workers.psp")

    if path.suffix.lower() not in (".iso",):
        logger.warning(f"No PSP compressor for {path.suffix}")
        return "No handler"

    # Reuse the existing compressor helper; respect args.rm_originals
    try:
        ok = _compress_psp_file(path, args, logger)
    except Exception as e:
        logger.error(f"Exception during PSP single compress: {e}")
        ok = False

    if ok:
        return "Compression complete. Success: 1, Failed: 0, Skipped: 0"
    else:
        # If CSO exists but _compress_psp_file returned False, it's likely skipped
        if path.with_suffix(".cso").exists():
            return "Compression complete. Success: 0, Failed: 0, Skipped: 1"
        return "Compression complete. Success: 0, Failed: 1, Skipped: 0"


def _organize_psp_item(item: Path, args: Any, logger: GuiLogger) -> bool:
    meta = psp_meta.get_metadata(item)
    serial = meta.get("serial")
    internal_title = meta.get("title")

    if not serial:
        # Try to identify by hash using library DB
        try:
            lib_db = LibraryDB()
            found = identify_game_by_hash(item, db=lib_db)
            if found:
                serial = found.dat_name
                # match_name may include title and [SERIAL]
                if found.match_name:
                    internal_title = found.match_name.split("[")[0].strip()
                logger.info(f"Identified by hash: using library match for {item.name}")
        except Exception:
            pass
        if not serial:
            return False

    db_title = psp_db.db.get_title(serial)
    title = db_title if db_title else internal_title

    if not title:
        title = "Unknown"

    # Sanitize
    clean_title = re.sub(r'[<>:"/\\|?*]', "", title).strip()

    # Standardize check (PSP metadata might have region/country code)
    # For now we stick to Title [Serial] as it is robust
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
        try:
            orig_path = str(item.resolve())
        except Exception:
            orig_path = str(item)

        if not getattr(args, "dry_run", False):
            item.rename(new_path)
        logger.info(f"Renamed: {item.name} -> {new_name}")
        # Write audit entry
        try:
            lib_db = LibraryDB()
            lib_db.log_action(orig_path, "RENAMED", f"{item.name} -> {new_name}")
        except Exception:
            logger.warning(f"Failed to write rename action for {item.name}")
        return True
    except Exception as e:
        logger.error(f"Failed to rename {item.name}: {e}")
        return False


@log_call(level=logging.INFO)
def worker_psp_organize(
    base_path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    list_files_fn: Callable[[Path], list[Path]],
    **kwargs
) -> str:
    """Worker function for PSP organization."""
    # Initialize correlation id for this worker run for traceability
    set_correlation_id()
    logger = get_logger_for_gui(log_cb, name="emumanager.workers.psp")

    candidates = [base_path / "roms" / "psp", base_path / "psp", base_path]
    target_dir = next((d for d in candidates if d.exists()), None)

    if not target_dir:
        return MSG_PSP_DIR_NOT_FOUND

    # Try to load DB
    db_path = base_path / "psp_db.csv"
    if db_path.exists():
        psp_db.db.load_from_csv(db_path)
        logger.info(f"Loaded PSP database from {db_path}")

    renamed = 0
    skipped = 0

    files = list_files_fn(target_dir)
    total = len(files)
    progress_cb = getattr(args, "progress_callback", None)
    cancel_event = getattr(args, "cancel_event", None)

    for i, f in enumerate(files):
        if cancel_event and cancel_event.is_set():
            logger.warning(MSG_CANCELLED)
            break

        if progress_cb:
            progress_cb(i / total, f"Organizing {f.name}...")

        if f.suffix.lower() in (".iso", ".cso", ".pbp"):
            # Skip files marked compressed by the scanner
            try:
                if skip_if_compressed(f, logger):
                    skipped += 1
                    continue
            except Exception:
                pass
            if _organize_psp_item(f, args, logger):
                renamed += 1
            else:
                skipped += 1

    if progress_cb:
        progress_cb(1.0, "PSP Organization complete")

    return f"PSP Organization complete. Renamed: {renamed}, Skipped: {skipped}"
