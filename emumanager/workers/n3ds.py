from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Optional

from emumanager.converters.n3ds_converter import (compress_to_7z,
                                                  convert_to_cia,
                                                  decompress_7z, decrypt_3ds)
from emumanager.n3ds import database as n3ds_db
from emumanager.n3ds import metadata as n3ds_meta
from emumanager.workers.common import (MSG_CANCELLED, GuiLogger, VerifyResult,
                                       calculate_file_hash,
                                       create_file_progress_cb,
                                       emit_verification_result,
                                       find_target_dir, make_result_collector)

MSG_N3DS_DIR_NOT_FOUND = "3DS ROMs directory not found."
N3DS_SUBDIRS = ["roms/3ds", "3ds", "n3ds", "roms/n3ds"]


def _process_n3ds_item(
    item: Path,
    logger: GuiLogger,
    deep_verify: bool = False,
    progress_cb: Optional[Callable[[float], None]] = None,
    per_file_cb: Optional[Callable[[VerifyResult], None]] = None,
) -> str:
    """
    Process a 3DS item (file) to extract serial and identify title.
    Returns: 'found', 'unknown', or 'skip'.
    """
    meta = n3ds_meta.get_metadata(item)
    serial = meta.get("serial")

    title = None
    status = "unknown"

    if serial:
        title = n3ds_db.db.get_title(serial)
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
        system="3DS",
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


def worker_n3ds_verify(
    base_path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    list_files_fn: Callable[[Path], list[Path]],
) -> str:
    """Worker function for 3DS verification."""
    logger = GuiLogger(log_cb)

    target_dir = find_target_dir(base_path, N3DS_SUBDIRS)
    if not target_dir:
        return MSG_N3DS_DIR_NOT_FOUND

    # Try to load DB
    db_path = base_path / "n3ds_db.csv"
    if db_path.exists():
        n3ds_db.db.load_from_csv(db_path)
        logger.info(f"Loaded 3DS database from {db_path}")

    logger.info(f"Scanning 3DS content in {target_dir}...")

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

        # Calculate progress range for this file
        start_prog = i / total
        file_weight = 1.0 / total

        file_prog_cb = create_file_progress_cb(
            progress_cb, start_prog, file_weight, f.name
        )

        if progress_cb:
            progress_cb(start_prog, f"Verifying {f.name}...")

        if f.suffix.lower() in (".3ds", ".cia", ".3dz", ".cci"):
            res = _process_n3ds_item(
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
        progress_cb(1.0, "3DS Verification complete")

    return f"Scan complete. Identified: {found}, Unknown: {unknown}"


def _organize_n3ds_item(item: Path, args: Any, logger: GuiLogger) -> bool:
    meta = n3ds_meta.get_metadata(item)
    serial = meta.get("serial")

    if not serial:
        return False

    db_title = n3ds_db.db.get_title(serial)
    title = db_title if db_title else "Unknown"

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


def worker_n3ds_organize(
    base_path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    list_files_fn: Callable[[Path], list[Path]],
) -> str:
    """Worker function for 3DS organization."""
    logger = GuiLogger(log_cb)

    target_dir = find_target_dir(base_path, N3DS_SUBDIRS)
    if not target_dir:
        return MSG_N3DS_DIR_NOT_FOUND

    # Try to load DB
    db_path = base_path / "n3ds_db.csv"
    if db_path.exists():
        n3ds_db.db.load_from_csv(db_path)
        logger.info(f"Loaded 3DS database from {db_path}")

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

        if f.suffix.lower() in (".3ds", ".cia", ".3dz", ".cci"):
            if _organize_n3ds_item(f, args, logger):
                renamed += 1
            else:
                skipped += 1

    if progress_cb:
        progress_cb(1.0, "3DS Organization complete")

    return f"Organization complete. Renamed: {renamed}, Skipped: {skipped}"


def worker_n3ds_compress(
    base_path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    list_files_fn: Callable[[Path], list[Path]],
) -> str:
    """Worker function for 3DS compression (to 7z)."""
    logger = GuiLogger(log_cb)

    target_dir = find_target_dir(base_path, N3DS_SUBDIRS)
    if not target_dir:
        return MSG_N3DS_DIR_NOT_FOUND

    logger.info(f"Compressing 3DS content in {target_dir}...")

    compressed = 0
    failed = 0
    skipped = 0

    files = list_files_fn(target_dir)
    total = len(files)
    progress_cb = getattr(args, "progress_callback", None)
    cancel_event = getattr(args, "cancel_event", None)
    dry_run = getattr(args, "dry_run", False)

    for i, f in enumerate(files):
        if cancel_event and cancel_event.is_set():
            logger.warning(MSG_CANCELLED)
            break

        # Calculate progress range for this file
        start_prog = i / total
        file_weight = 1.0 / total

        file_prog_cb = create_file_progress_cb(
            progress_cb, start_prog, file_weight, f.name
        )

        if progress_cb:
            progress_cb(start_prog, f"Compressing {f.name}...")

        print(f"DEBUG: Processing {f.name}, suffix={f.suffix}")

        if f.suffix.lower() in (".3ds", ".cia", ".3dz", ".cci"):
            dest = f.with_suffix(f.suffix + ".7z")
            if dest.exists():
                logger.info(f"Skipping {f.name}, already compressed.")
                skipped += 1
                continue

            logger.info(f"Compressing {f.name} -> {dest.name}")
            success = compress_to_7z(f, dest, dry_run=dry_run, progress_cb=file_prog_cb)
            if success:
                compressed += 1
                if not dry_run:
                    try:
                        f.unlink()  # Remove original
                    except Exception as e:
                        logger.warning(f"Failed to remove original {f.name}: {e}")
            else:
                failed += 1
                logger.error(f"Failed to compress {f.name}")

    if progress_cb:
        progress_cb(1.0, "3DS Compression complete")

    return (
        f"Compression complete. Compressed: {compressed}, "
        f"Failed: {failed}, Skipped: {skipped}"
    )


def worker_n3ds_decompress(
    base_path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    list_files_fn: Callable[[Path], list[Path]],
) -> str:
    """Worker function for 3DS decompression (from 7z)."""
    logger = GuiLogger(log_cb)

    target_dir = find_target_dir(base_path, N3DS_SUBDIRS)
    if not target_dir:
        return MSG_N3DS_DIR_NOT_FOUND

    logger.info(f"Decompressing 3DS content in {target_dir}...")

    decompressed = 0
    failed = 0
    skipped = 0  # noqa: F841

    files = list_files_fn(target_dir)
    total = len(files)
    progress_cb = getattr(args, "progress_callback", None)
    cancel_event = getattr(args, "cancel_event", None)
    dry_run = getattr(args, "dry_run", False)

    for i, f in enumerate(files):
        if cancel_event and cancel_event.is_set():
            logger.warning(MSG_CANCELLED)
            break

        # Calculate progress range for this file
        start_prog = i / total
        file_weight = 1.0 / total

        file_prog_cb = create_file_progress_cb(
            progress_cb, start_prog, file_weight, f.name
        )

        if progress_cb:
            progress_cb(start_prog, f"Decompressing {f.name}...")

        if f.suffix.lower() == ".7z":
            # Check if it contains 3DS files?
            # For now, assume yes if in 3DS folder.

            logger.info(f"Decompressing {f.name}")
            success = decompress_7z(
                f, target_dir, dry_run=dry_run, progress_cb=file_prog_cb
            )
            if success:
                decompressed += 1
                if not dry_run:
                    try:
                        f.unlink()  # Remove archive
                    except Exception as e:
                        logger.warning(f"Failed to remove archive {f.name}: {e}")
            else:
                failed += 1
                logger.error(f"Failed to decompress {f.name}")

    if progress_cb:
        progress_cb(1.0, "3DS Decompression complete")

    return f"Decompression complete. Decompressed: {decompressed}, Failed: {failed}"


def worker_n3ds_convert_cia(
    base_path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    list_files_fn: Callable[[Path], list[Path]],
) -> str:
    """Worker function for 3DS -> CIA conversion."""
    logger = GuiLogger(log_cb)

    target_dir = find_target_dir(base_path, N3DS_SUBDIRS)
    if not target_dir:
        return MSG_N3DS_DIR_NOT_FOUND

    logger.info(f"Converting 3DS to CIA in {target_dir}...")

    converted = 0
    failed = 0
    skipped = 0

    files = list_files_fn(target_dir)
    total = len(files)
    progress_cb = getattr(args, "progress_callback", None)
    cancel_event = getattr(args, "cancel_event", None)
    dry_run = getattr(args, "dry_run", False)

    for i, f in enumerate(files):
        if cancel_event and cancel_event.is_set():
            logger.warning(MSG_CANCELLED)
            break

        # Calculate progress range for this file
        start_prog = i / total
        file_weight = 1.0 / total

        file_prog_cb = create_file_progress_cb(
            progress_cb, start_prog, file_weight, f.name
        )

        if progress_cb:
            progress_cb(start_prog, f"Converting {f.name}...")

        if f.suffix.lower() == ".3ds":
            dest = f.with_suffix(".cia")
            if dest.exists():
                logger.info(f"Skipping {f.name}, CIA already exists.")
                skipped += 1
                continue

            logger.info(f"Converting {f.name} -> {dest.name}")
            try:
                success = convert_to_cia(
                    f, dest, dry_run=dry_run, progress_cb=file_prog_cb
                )
                if success:
                    converted += 1
                else:
                    failed += 1
                    logger.error(f"Failed to convert {f.name}")
            except FileNotFoundError as e:
                logger.error(str(e))
                return f"Conversion failed: {e}"
            except Exception as e:
                failed += 1
                logger.error(f"Exception converting {f.name}: {e}")

    if progress_cb:
        progress_cb(1.0, "3DS -> CIA Conversion complete")

    return (
        f"Conversion complete. Converted: {converted}, "
        f"Failed: {failed}, Skipped: {skipped}"
    )


def worker_n3ds_decrypt(
    base_path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    list_files_fn: Callable[[Path], list[Path]],
) -> str:
    """Worker function for 3DS decryption."""
    logger = GuiLogger(log_cb)

    target_dir = find_target_dir(base_path, N3DS_SUBDIRS)
    if not target_dir:
        return MSG_N3DS_DIR_NOT_FOUND

    logger.info(f"Decrypting 3DS content in {target_dir}...")

    decrypted = 0
    failed = 0
    skipped = 0

    files = list_files_fn(target_dir)
    total = len(files)
    progress_cb = getattr(args, "progress_callback", None)
    cancel_event = getattr(args, "cancel_event", None)
    dry_run = getattr(args, "dry_run", False)

    for i, f in enumerate(files):
        if cancel_event and cancel_event.is_set():
            logger.warning(MSG_CANCELLED)
            break

        # Calculate progress range for this file
        start_prog = i / total
        file_weight = 1.0 / total

        file_prog_cb = create_file_progress_cb(
            progress_cb, start_prog, file_weight, f.name
        )

        if progress_cb:
            progress_cb(start_prog, f"Decrypting {f.name}...")

        if f.suffix.lower() == ".3ds":
            dest = f.with_name(f.stem + "_decrypted.3ds")
            if dest.exists():
                logger.info(f"Skipping {f.name}, decrypted file already exists.")
                skipped += 1
                continue

            logger.info(f"Decrypting {f.name} -> {dest.name}")
            try:
                success = decrypt_3ds(
                    f, dest, dry_run=dry_run, progress_cb=file_prog_cb
                )
                if success:
                    decrypted += 1
                else:
                    failed += 1
                    logger.error(
                        f"Failed to decrypt {f.name} (Tool not implemented/found)"
                    )
            except FileNotFoundError as e:
                logger.error(str(e))
                return f"Decryption failed: {e}"
            except Exception as e:
                failed += 1
                logger.error(f"Exception decrypting {f.name}: {e}")

    if progress_cb:
        progress_cb(1.0, "3DS Decryption complete")

    return (
        f"Decryption complete. Decrypted: {decrypted}, "
        f"Failed: {failed}, Skipped: {skipped}"
    )


def worker_n3ds_compress_single(
    filepath: Path, args: Any, log_cb: Callable[[str], None]
) -> Optional[Path]:
    """Worker function for compressing a single 3DS file."""
    logger = GuiLogger(log_cb)

    if filepath.suffix.lower() not in (".3ds", ".cia", ".3dz", ".cci"):
        logger.warning(f"Skipping {filepath.name}: Not a valid 3DS file.")
        return None

    dest = filepath.with_suffix(filepath.suffix + ".7z")
    if dest.exists():
        logger.info(f"Skipping {filepath.name}: {dest.name} already exists.")
        return None

    logger.info(f"Compressing {filepath.name} -> {dest.name}...")
    if compress_to_7z(filepath, dest):
        if getattr(args, "rm_originals", False):
            try:
                filepath.unlink()
                logger.info(f"Deleted original: {filepath.name}")
            except Exception as e:
                logger.error(f"Failed to delete original: {e}")
        return dest
    else:
        logger.error(f"Compression failed for {filepath.name}")
        return None


def worker_n3ds_decompress_single(
    filepath: Path, args: Any, log_cb: Callable[[str], None]
) -> Optional[Path]:
    """Worker function for decompressing a single 3DS file."""
    logger = GuiLogger(log_cb)

    if filepath.suffix.lower() != ".7z":
        logger.warning(f"Skipping {filepath.name}: Not a 7z file.")
        return None

    # We don't know the inner filename easily without listing,
    # but decompress_7z handles extraction to the same dir.
    logger.info(f"Decompressing {filepath.name}...")

    # decompress_7z returns list of extracted files or None
    extracted = decompress_7z(filepath, filepath.parent)

    if extracted:
        logger.info(f"Decompressed {len(extracted)} files.")
        if getattr(args, "rm_originals", False):
            try:
                filepath.unlink()
                logger.info(f"Deleted archive: {filepath.name}")
            except Exception as e:
                logger.error(f"Failed to delete archive: {e}")
        return extracted[0] if extracted else None
    else:
        logger.error(f"Decompression failed for {filepath.name}")
        return None
