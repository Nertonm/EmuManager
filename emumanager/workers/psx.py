from __future__ import annotations

import logging
import re
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Any, Callable, Optional

from emumanager.common.execution import run_cmd_stream, run_cmd
from emumanager.library import LibraryDB, LibraryEntry
from emumanager.logging_cfg import log_call, set_correlation_id
from emumanager.psx import database as psx_db
from emumanager.psx import metadata as psx_meta
from emumanager.workers import common as workers_common
from emumanager.workers.common import (
    MSG_CANCELLED,
    GuiLogger,
    calculate_file_hash,
    create_file_progress_cb,
    emit_verification_result,
    ensure_hashes_in_db,
    find_target_dir,
    get_logger_for_gui,
    identify_game_by_hash,
    make_result_collector,
    skip_if_compressed,
)

MSG_PSX_DIR_NOT_FOUND = "PS1 ROMs directory not found."
PSX_SUBDIRS = ["roms/psx", "psx"]


def _chdman_create(output: Path, input_path: Path) -> subprocess.Popen:
    chdman = workers_common.find_tool("chdman")
    if not chdman:
        raise RuntimeError("'chdman' not found in PATH")
    # Use -i input -o output -f to force overwrite if exists? We'll avoid -f for safety.
    return subprocess.Popen(
        [str(chdman), "createcd", "-i", str(input_path), "-o", str(output)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def _collect_psx_inputs_for_conversion(target_dir: Path) -> list[Path]:
    """Collect candidate source files for PS1 conversion, preferring CUE over BIN.

    Also skip all BIN files in any directory that contains a CUE.
    """
    raw = [
        p
        for p in target_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in {".cue", ".bin", ".iso"}
    ]
    cue_dirs = {p.parent for p in raw if p.suffix.lower() == ".cue"}
    filtered: list[Path] = []
    for f in raw:
        suf = f.suffix.lower()
        if suf == ".bin":
            # Skip if matching CUE exists or any CUE exists in same directory
            if f.with_suffix(".cue").exists() or f.parent in cue_dirs:
                continue
        filtered.append(f)
    return filtered


def _convert_one_with_chdman(
    src: Path, logger: GuiLogger, dry_run: bool
) -> tuple[bool, bool]:
    """Run chdman for a single source. Returns (converted, skipped)."""
    out = src.with_suffix(".chd")
    if out.exists():
        logger.warning(f"Skip (exists): {out.name}")
        return False, True
    if dry_run:
        logger.info(f"[DRY] chdman createcd -i {src.name} -o {out.name}")
        return True, False
    try:
        # Use streaming runner so we can surface chdman output if needed
        chdman_path = workers_common.find_tool("chdman")
        cmd = [str(chdman_path), "createcd", "-i", str(src), "-o", str(out)]
        res = run_cmd_stream(cmd)
        rc = getattr(res, "returncode", 1)
        if rc == 0:
            return True, False
        logger.error(f"chdman failed ({rc}) for {src.name}")
        return False, False
    except Exception as e:
        logger.error(f"Conversion error for {src.name}: {e}")
        return False, False

@log_call(level=logging.INFO)
def worker_psx_convert(
    base_path: Path, args: Any, log_cb: Callable[[str], None], **kwargs
) -> str:
    """Convert PS1 CUE/BIN/ISO to CHD using chdman."""
    # Initialize correlation id and use structured logger wired to GUI
    set_correlation_id()
    logger = get_logger_for_gui(log_cb, name="emumanager.workers.psx")
    target_dir = find_target_dir(base_path, PSX_SUBDIRS)
    if not target_dir:
        return MSG_PSX_DIR_NOT_FOUND

    chdman = workers_common.find_tool("chdman")
    if not chdman:
        return "Error: 'chdman' not found in PATH."

    files = _collect_psx_inputs_for_conversion(target_dir)
    if not files:
        return "No PS1 images (cue/bin/iso) found."

    logger.info(f"Converting {len(files)} PS1 images to CHD...")
    converted = 0
    skipped = 0
    total = len(files)
    progress_cb = getattr(args, "progress_callback", None)
    cancel_event = getattr(args, "cancel_event", None)
    dry_run = bool(getattr(args, "dry_run", False))

    for i, src in enumerate(files):
        if cancel_event and cancel_event.is_set():
            logger.warning(MSG_CANCELLED)
            break
        # Skip files flagged as compressed by scanner
        try:
            if skip_if_compressed(src, logger):
                skipped += 1
                continue
        except Exception:
            pass
        if progress_cb:
            progress_cb(i / total, f"Converting {src.name}...")
        did_convert, did_skip = _convert_one_with_chdman(src, logger, dry_run)
        if did_convert:
            converted += 1
            # If the user requested originals removed, preserve hashes from the
            # original file and attach them to the new .chd entry so verification
            # info remains available after deletion.
            if getattr(args, "rm_originals", False):
                try:
                    lib_db = LibraryDB()
                    # Ensure original hashes are recorded (md5, sha1)
                    md5, sha1 = ensure_hashes_in_db(src, db=lib_db)
                    # Update the new CHD entry with the preserved hashes and mark
                    # it as COMPRESSED for downstream skip behavior.
                    try:
                        out = src.with_suffix(".chd")
                        st = out.stat()
                        new_entry = LibraryEntry(
                            path=str(out.resolve()),
                            system="",
                            size=st.st_size,
                            mtime=st.st_mtime,
                            crc32=None,
                            md5=md5,
                            sha1=sha1,
                            sha256=None,
                            status="COMPRESSED",
                            match_name=None,
                            dat_name=None,
                        )
                        lib_db.update_entry(new_entry)
                        lib_db.log_action(
                            str(out),
                            "COMPRESSED",
                            f"Converted from {src.name} and original removed",
                        )
                    except Exception:
                        # Best-effort: don't abort conversion on DB write problems
                        pass
                    # Now remove the original file
                    from emumanager.common.fileops import safe_unlink

                    safe_unlink(src, logger)
                except Exception as e:
                    logger.error(f"Failed to delete {src.name}: {e}")
        elif did_skip:
            skipped += 1

    if progress_cb:
        progress_cb(1.0, "PS1 Conversion complete")
    return f"PS1 Conversion complete. Converted: {converted}, Skipped: {skipped}"


def _dedup_psx_verify_files(files: list[Path]) -> list[Path]:
    """Deduplicate PS1 verification inputs.

    - If a directory has a .cue, skip all .bin in that directory (multi-bin cuesheets).
    - Also skip .bin that has a matching .cue with the same stem.
    """
    try:
        cue_files = [p for p in files if p.suffix.lower() == ".cue"]
        cue_dirs = {p.parent for p in cue_files}
        cue_stems = {p.with_suffix("").name for p in cue_files}
        _filtered = []
        for p in files:
            if p.suffix.lower() == ".bin":
                if p.parent in cue_dirs:
                    continue
                if p.with_suffix("").name in cue_stems:
                    continue
            _filtered.append(p)
        return _filtered
    except Exception:
        return files


def _process_psx_file(
    f: Path,
    logger: GuiLogger,
    deep_verify: bool = False,
    progress_cb: Optional[Callable[[float], None]] = None,
    per_file_cb: Optional[Callable[[Any], None]] = None,
) -> str:
    suffix = f.suffix.lower()
    if suffix not in {".bin", ".cue", ".iso", ".chd", ".gz", ".img"}:
        return "skip"
    if suffix == ".cue":
        # Prefer associated BIN for extraction; fall back to scanning CUE
        bin_path = f.with_suffix(".bin")
        if bin_path.exists():
            f = bin_path

    serial = psx_meta.get_psx_serial(f)
    info_str = ""
    if serial:
        title = psx_db.db.get_title(serial)
        info_str = f"[{serial}] {title or 'Unknown Title'}"
    else:
        info_str = "[NO SERIAL] Could not identify"

    md5: Optional[str] = None
    sha1: Optional[str] = None
    if deep_verify:
        logger.info(f"Hashing {f.name}...")
        md5 = calculate_file_hash(f, "md5", progress_cb=progress_cb)
        sha1 = calculate_file_hash(f, "sha1", progress_cb=progress_cb)
        info_str += f" | MD5: {md5} | SHA1: {sha1}"

    logger.info(f"{info_str} -> {f.name}")
    emit_verification_result(
        per_file_cb,
        f,
        status="VERIFIED" if serial else "UNKNOWN",
        serial=serial,
        title=psx_db.db.get_title(serial) if serial else None,
        md5=md5 if deep_verify else None,
        sha1=sha1 if deep_verify else None,
    )
    return "found" if serial else "unknown"


@log_call(level=logging.INFO)
def worker_psx_verify(
    base_path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    list_files_fn: Callable[[Path], list[Path]],
) -> str:
    # Initialize correlation id and use structured logger wired to GUI
    set_correlation_id()
    logger = get_logger_for_gui(log_cb, name="emumanager.workers.psx")
    target_dir = find_target_dir(base_path, PSX_SUBDIRS)
    if not target_dir:
        return MSG_PSX_DIR_NOT_FOUND

    # Optional CSV database: psx_db.csv in base
    db_path = base_path / "psx_db.csv"
    if db_path.exists():
        psx_db.db.load_from_csv(db_path)
        logger.info(f"Loaded PS1 database from {db_path}")
    else:
        # Ensure we don't retain state from previous runs/tests
        try:
            psx_db.db.clear()
        except Exception:
            pass

    files = list_files_fn(target_dir)
    files = _dedup_psx_verify_files(files)
    if not files:
        return "No PS1 files found."

    logger.info(f"Scanning {len(files)} files for PS1 Serials...")
    found = 0
    unknown = 0
    total = len(files)
    progress_cb = getattr(args, "progress_callback", None)
    cancel_event = getattr(args, "cancel_event", None)
    deep_verify = getattr(args, "deep_verify", False)

    # Optional rich result hooks (used by GUI table integration)
    per_file_cb_attr = getattr(args, "per_file_cb", None)
    results_list_attr = getattr(args, "results", None)
    collector = (
        make_result_collector(per_file_cb_attr, results_list_attr)
        if (callable(per_file_cb_attr) or isinstance(results_list_attr, list))
        else None
    )

    for i, f in enumerate(files):
        if cancel_event and cancel_event.is_set():
            logger.warning(MSG_CANCELLED)
            break
        # If scanner flagged this file as compressed, skip and log action
        try:
            if skip_if_compressed(f, logger):
                continue
        except Exception:
            pass
        start_prog = i / total
        weight = 1.0 / total
        file_prog_cb = create_file_progress_cb(progress_cb, start_prog, weight, f.name)
        if progress_cb:
            progress_cb(start_prog, f"Verifying {f.name}...")
        res = _process_psx_file(
            f,
            logger,
            deep_verify=deep_verify,
            progress_cb=file_prog_cb,
            per_file_cb=collector,
        )
        if res == "found":
            found += 1
        elif res == "unknown":
            unknown += 1

    if progress_cb:
        progress_cb(1.0, "PS1 Verification complete")
    return f"Scan complete. Identified: {found}, Unknown: {unknown}"


@log_call(level=logging.INFO)
def worker_chd_decompress_single(
    path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    **kwargs
) -> str:
    """Decompress a single .chd file to an .iso using chdman.

    This is a simple single-file wrapper suitable for the Tools -> Decompress
    context-menu action. The output will be written next to the original file
    with a .iso suffix. If chdman is not available or extraction fails, an
    error string is returned.
    """
    # Initialize correlation id and use structured logger wired to GUI
    set_correlation_id()
    logger = get_logger_for_gui(log_cb, name="emumanager.workers.psx")
    chdman = workers_common.find_tool("chdman")
    if not chdman:
        return "Error: 'chdman' not found in PATH."

    if path.suffix.lower() != ".chd":
        logger.warning(f"No CHD handler for {path.suffix}")
        return "No-op"

    out = path.with_suffix(".iso")
    if out.exists():
        logger.info(f"Skipping extraction, output exists: {out.name}")
        return f"Skipped (exists): {out.name}"

    logger.info(f"Extracting CHD: {path.name} -> {out.name}...")
    try:
        # Prefer to run `chdman info` first and pick the most likely extract
        # verb. Some CHDs are DVD images and extractdvd tends to work better;
        # others are CD images. If info can't be parsed, fall back to trying
        # several verbs.
        cmds = []
        try:
            info_res = run_cmd([str(chdman), "info", "-i", str(path)])
            info_out = getattr(info_res, "stdout", "") or ""
            tag_m = None
            # Look for a Metadata Tag line like "Tag='DVD '"
            import re

            m = re.search(r"Tag='([^']+)'", info_out)
            if m:
                tag_m = m.group(1).strip().upper()
            # If tag suggests DVD, try extractdvd first; if CD, try extractcd.
            if tag_m and "DVD" in tag_m:
                cmds = [
                    [str(chdman), "extractdvd", "-i", str(path), "-o", str(out)],
                    [str(chdman), "extractraw", "-i", str(path), "-o", str(out)],
                    [str(chdman), "extracthd", "-i", str(path), "-o", str(out)],
                    [str(chdman), "extract", "-i", str(path), "-o", str(out)],
                    [str(chdman), "extractcd", "-i", str(path), "-o", str(out)],
                ]
            elif tag_m and "CD" in tag_m:
                cmds = [
                    [str(chdman), "extractcd", "-i", str(path), "-o", str(out)],
                    [str(chdman), "extractraw", "-i", str(path), "-o", str(out)],
                    [str(chdman), "extracthd", "-i", str(path), "-o", str(out)],
                    [str(chdman), "extract", "-i", str(path), "-o", str(out)],
                ]
        except Exception:
            cmds = []

        if not cmds:
            cmds = [
                [str(chdman), "extractdvd", "-i", str(path), "-o", str(out)],
                [str(chdman), "extractraw", "-i", str(path), "-o", str(out)],
                [str(chdman), "extracthd", "-i", str(path), "-o", str(out)],
                [str(chdman), "extractcd", "-i", str(path), "-o", str(out)],
                [str(chdman), "extract", "-i", str(path), "-o", str(out)],
            ]
        progress_cb = getattr(args, "progress_callback", None)
        rc = 1
        for cmd in cmds:
            try:
                res = run_cmd_stream(cmd, progress_cb=progress_cb)
                rc = getattr(res, "returncode", 1)
                if rc == 0:
                    break
            except Exception:
                rc = 1
                continue

        if rc == 0:
            logger.info(f"Extraction complete: {out.name}")
            return f"Extracted: {out.name}"

        # Extraction failed; gather diagnostics (info + verify) and write a
        # more explanatory message to the logs so users can diagnose issues.
        full_log_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".chdman.out", delete=False, mode="w", encoding="utf-8") as outf:
                full_log_path = Path(outf.name)
                try:
                    outf.write("--- chdman last extraction output ---\n")
                    outf.write((getattr(res, "stdout", "") or "") + "\n")
                except Exception:
                    pass
                try:
                    info_res = run_cmd([str(chdman), "info", "-i", str(path)])
                    outf.write("--- chdman info ---\n")
                    outf.write((getattr(info_res, "stdout", "") or "") + "\n")
                except Exception:
                    pass
                try:
                    ver_res = run_cmd([str(chdman), "verify", "-i", str(path)])
                    outf.write("--- chdman verify ---\n")
                    outf.write((getattr(ver_res, "stdout", "") or "") + "\n")
                except Exception:
                    pass

        except Exception:
            full_log_path = None

        # Detect usage/help output and common runtime errors such as
        # 'Invalid data' which usually indicate corruption. We reuse the
        # outputs we collected earlier (info_res/ver_res) when available.
        last_out = getattr(res, "stdout", "") or ""
        info_out = ""
        ver_out = ""
        try:
            info_out = getattr(info_res, "stdout", "") or ""
        except Exception:
            pass
        try:
            ver_out = getattr(ver_res, "stdout", "") or ""
        except Exception:
            pass

        usage_detected = (
            ("Usage:" in last_out) or last_out.strip().startswith("chdman - MAME")
        )
        invalid_data_detected = (
            ("Invalid data" in last_out)
            or ("Invalid data" in info_out)
            or ("Invalid data" in ver_out)
        )

        if full_log_path:
            if usage_detected:
                logger.error(
                    "chdman appears to have printed its usage/help text when trying to "
                    f"extract {path.name}; this often means the chdman binary lacks "
                    "codec support (e.g. liblzma/libxz) or is an incomplete build.\n"
                    f"Full chdman output saved to: {full_log_path}\n"
                    f"Please run: ldd {str(chdman)} and install xz/liblzma if missing."
                )
                return (
                    "Error: chdman printed usage/help while extracting (likely missing "
                    f"liblzma/xz). See {full_log_path} "
                    f"and run 'ldd {str(chdman)}' to check."
                )
            if invalid_data_detected:
                # Attempt to quarantine the corrupted CHD: move it to a
                # `quarantine` subfolder next to the original file, update
                # the LibraryDB status to CORRUPT and log the action so the
                # user can inspect and restore if desired.
                try:
                    quarantine_dir = path.parent / "quarantine"
                    quarantine_dir.mkdir(parents=True, exist_ok=True)
                    new_path = quarantine_dir / path.name
                    shutil.move(str(path), str(new_path))

                    # Update DB entry (best-effort)
                    try:
                        lib_db = LibraryDB()
                        old_entry = lib_db.get_entry(str(path))
                        st = new_path.stat()
                        if old_entry:
                            new_entry = LibraryEntry(
                                path=str(new_path),
                                system=old_entry.system,
                                size=st.st_size,
                                mtime=st.st_mtime,
                                crc32=old_entry.crc32,
                                md5=old_entry.md5,
                                sha1=old_entry.sha1,
                                sha256=old_entry.sha256,
                                status="CORRUPT",
                                match_name=old_entry.match_name,
                                dat_name=old_entry.dat_name,
                            )
                        else:
                            new_entry = LibraryEntry(
                                path=str(new_path),
                                system="",
                                size=st.st_size,
                                mtime=st.st_mtime,
                                crc32=None,
                                md5=None,
                                sha1=None,
                                sha256=None,
                                status="CORRUPT",
                                match_name=None,
                                dat_name=None,
                            )
                        lib_db.update_entry(new_entry)
                        lib_db.log_action(
                            str(new_path),
                            "QUARANTINED",
                            (
                                "Moved from "
                                f"{path} due to invalid data; see {full_log_path}"
                            ),
                        )
                    except Exception:
                        # Best-effort: don't abort if DB update fails
                        logger.warning("Failed to update LibraryDB for quarantined CHD")

                    logger.error(
                        "chdman reported 'Invalid data' while reading "
                        f"{path.name}; the CHD has been moved to quarantine: {new_path}\n"
                        f"Full chdman output saved to: {full_log_path}\n"
                        "Action: run 'chdman verify -i <file>' to confirm integrity or restore from backup."
                    )
                    return (
                        f"Error: CHD contains invalid data and was moved to quarantine: {new_path}. See {full_log_path}"
                    )
                except Exception as e:
                    logger.error(f"Failed to quarantine corrupted CHD {path}: {e}")
                    return (
                        f"Error: CHD contains invalid data (could not quarantine automatically). See {full_log_path}"
                    )
            logger.error(f"chdman failed ({rc}) for {path.name}; see: {full_log_path}")
            return f"Error: chdman failed ({rc}); see {full_log_path}"
        else:
            if usage_detected:
                logger.error(
                    "chdman appears to have printed usage/help while extracting "
                    f"{path.name}; binary may lack codec support (liblzma/xz)."
                )
                return (
                    "Error: chdman printed usage/help while extracting (likely missing "
                    f"liblzma/xz). Run 'ldd {str(chdman)}' to check."
                )
            if invalid_data_detected:
                logger.error(
                    "chdman reported 'Invalid data' while reading "
                    f"{path.name}; the CHD may be corrupted."
                )
                return (
                    "Error: CHD contains invalid data (possible corruption). Run "
                    f"'chdman verify -i {str(path)}'."
                )
            logger.error(f"chdman failed ({rc}) for {path.name}")
            return f"Error: chdman failed ({rc})"
    except Exception as e:
        logger.error(f"Extraction error for {path.name}: {e}")
        return f"Error: {e}"


@log_call(level=logging.INFO)
def worker_chd_recompress_single(
    path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    **kwargs
) -> str:
    """Recompress a single .chd by extracting -> creating a new CHD.

    The operation extracts the CHD to a temporary ISO, creates a new CHD from
    that ISO (using `createdvd`/`createcd` depending on source), and replaces
    the original CHD if successful.
    """
    # Initialize correlation id and use structured logger wired to GUI
    set_correlation_id()
    logger = get_logger_for_gui(log_cb, name="emumanager.workers.psx")
    chdman = workers_common.find_tool("chdman")
    if not chdman:
        return "Error: 'chdman' not found in PATH."

    if path.suffix.lower() != ".chd":
        logger.warning(f"No CHD recompress handler for {path.suffix}")
        return "No-op"

    import tempfile

    logger.info(f"Recompressing {path.name}...")

    tmp_iso = None
    tmp_chd = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".iso", delete=False) as tf:
            tmp_iso = Path(tf.name)

        with tempfile.NamedTemporaryFile(suffix=".chd", delete=False) as tf2:
            tmp_chd = Path(tf2.name)

        # Extract to tmp_iso
        extract_cmds = [
            [str(chdman), "extractdvd", "-i", str(path), "-o", str(tmp_iso)],
            [str(chdman), "extractcd", "-i", str(path), "-o", str(tmp_iso)],
            [str(chdman), "extract", "-i", str(path), "-o", str(tmp_iso)],
        ]
        rc = 1
        progress_cb = getattr(args, "progress_callback", None)
        rc = 1
        for cmd in extract_cmds:
            try:
                res = run_cmd_stream(cmd, progress_cb=progress_cb)
                rc = getattr(res, "returncode", 1)
                if rc == 0:
                    break
            except Exception:
                rc = 1
                continue

        if rc != 0:
            logger.error(f"chdman failed ({rc}) while extracting {path.name}")
            return f"Error: chdman failed ({rc})"

        # Create CHD from tmp_iso into tmp_chd
        create_cmds = [
            [str(chdman), "createdvd", "-i", str(tmp_iso), "-o", str(tmp_chd)],
            [str(chdman), "createcd", "-i", str(tmp_iso), "-o", str(tmp_chd)],
        ]
        rc2 = 1
        rc2 = 1
        for cmd in create_cmds:
            try:
                res = run_cmd_stream(cmd, progress_cb=progress_cb)
                rc2 = getattr(res, "returncode", 1)
                if rc2 == 0:
                    break
            except Exception:
                rc2 = 1
                continue

        if rc2 != 0:
            logger.error(f"chdman failed ({rc2}) while creating CHD for {path.name}")
            return f"Error: chdman failed ({rc2})"

        # Replace original CHD with newly created one
        try:
            backup = path.with_suffix(path.suffix + ".bak")
            if backup.exists():
                backup.unlink()
            path.replace(backup)
            Path(tmp_chd).replace(path)
            backup.unlink(missing_ok=True)
            logger.info(f"Recompressed: {path.name}")
            return f"Recompressed: {path.name}"
        except Exception as e:
            logger.error(f"Failed to replace original CHD: {e}")
            return f"Error: {e}"
    finally:
        # Cleanup temp files
        try:
            if tmp_iso and tmp_iso.exists():
                tmp_iso.unlink()
        except Exception:
            pass
        try:
            if tmp_chd and tmp_chd.exists():
                tmp_chd.unlink()
        except Exception:
            pass


def _organize_psx_file(
    f: Path, args: Any, logger: GuiLogger
) -> tuple[bool, Optional[str]]:
    if f.suffix.lower() not in {".bin", ".cue", ".iso", ".chd", ".gz", ".img"}:
        return False, None
    # If CUE present, prefer reading serial from BIN alongside
    src_for_serial = f
    if f.suffix.lower() == ".cue":
        bin_path = f.with_suffix(".bin")
        if bin_path.exists():
            src_for_serial = bin_path
    serial = psx_meta.get_psx_serial(src_for_serial)
    title = None

    # If we couldn't extract a serial, try to identify by hash using the
    # library DB (sha1). This allows renaming when the library already has
    # a canonical entry for this file.
    if not serial:
        try:
            lib_db = LibraryDB()
            found = identify_game_by_hash(f, db=lib_db)
            if found:
                # dat_name stores serial-like IDs in many systems
                serial = found.dat_name
                # match_name may include title and [SERIAL], so take the text
                if found.match_name:
                    title = found.match_name.split("[")[0].strip()
                else:
                    title = None
                logger.info(f"Identified by hash: using library match for {f.name}")
        except Exception:
            pass

    if not serial:
        logger.warning(f"Could not extract serial from {f.name}")
        return False, None

    # Resolve title from DAT lookup or earlier found match; fall back to a
    # generic "Unknown Title" when no title is available in the DAT.
    title = title or psx_db.db.get_title(serial) or "Unknown Title"
    safe_title = re.sub(r'[<>:"/\\|?*]', "", title).strip()
    new_name = f"{safe_title} [{serial}]{f.suffix}"
    new_path = f.parent / new_name
    if f.name == new_name or new_path.exists():
        return False, None
    try:
        orig_path = str(f.resolve())
    except Exception:
        orig_path = str(f)

    try:
        if not args.dry_run:
            f.rename(new_path)
        logger.info(f"Renamed: {f.name} -> {new_name}")
        # Audit log
        try:
            lib_db = LibraryDB()
            lib_db.log_action(orig_path, "RENAMED", f"{f.name} -> {new_name}")
        except Exception:
            logger.warning(f"Failed to write rename action for {f.name}")
        return True, new_name
    except Exception as e:
        logger.error(f"Failed to rename {f.name}: {e}")
        return False, None


@log_call(level=logging.INFO)
def worker_psx_organize(
    base_path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    list_files_fn: Callable[[Path], list[Path]],
    **kwargs
) -> str:
    # Initialize correlation id and use structured logger wired to GUI
    set_correlation_id()
    logger = get_logger_for_gui(log_cb, name="emumanager.workers.psx")
    target_dir = find_target_dir(base_path, PSX_SUBDIRS)
    if not target_dir:
        return MSG_PSX_DIR_NOT_FOUND

    db_path = base_path / "psx_db.csv"
    if db_path.exists():
        psx_db.db.load_from_csv(db_path)
        logger.info(f"Loaded PS1 database from {db_path}")
    else:
        try:
            psx_db.db.clear()
        except Exception:
            pass

    files = list_files_fn(target_dir)
    if not files:
        return "No PS1 files found."

    logger.info(f"Organizing {len(files)} PS1 files...")
    renamed = 0
    skipped = 0
    renamed_names: list[str] = []
    total = len(files)
    progress_cb = getattr(args, "progress_callback", None)
    cancel_event = getattr(args, "cancel_event", None)

    for i, f in enumerate(files):
        if cancel_event and cancel_event.is_set():
            logger.warning(MSG_CANCELLED)
            break
        if progress_cb:
            progress_cb(i / total, f"Organizing {f.name}...")
        try:
            if skip_if_compressed(f, logger):
                skipped += 1
                continue
        except Exception:
            pass
        ok, new_name = _organize_psx_file(f, args, logger)
        if ok:
            renamed += 1
            if new_name:
                renamed_names.append(new_name)
        else:
            skipped += 1

    if progress_cb:
        progress_cb(1.0, "PS1 Organization complete")
    extra = f" ({', '.join(renamed_names)})" if renamed_names else ""
    return f"PS1 Organization complete. Renamed: {renamed}, Skipped: {skipped}{extra}"
