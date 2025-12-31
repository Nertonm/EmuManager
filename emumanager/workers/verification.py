from __future__ import annotations

import os
import tempfile
import logging
from pathlib import Path
from typing import Any, Callable, Optional

from emumanager.common.execution import run_cmd_stream
from emumanager.workers import common as workers_common
from emumanager.common.models import VerifyReport, VerifyResult
from emumanager.library import LibraryDB, LibraryEntry
from emumanager.verification import dat_parser, hasher
from emumanager.verification.dat_manager import find_dat_for_system
from emumanager.workers.common import (
    MSG_CANCELLED,
    GuiLogger,
    create_file_progress_cb,
    skip_if_compressed,
)
from emumanager.workers.common import get_logger_for_gui
from emumanager.logging_cfg import set_correlation_id, log_call



@log_call(level=logging.INFO)
def worker_hash_verify(
    base_path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    list_files_fn: Callable[[Path], list[Path]],
    **kwargs
) -> VerifyReport:
    """Worker function for DAT-based hash verification."""
    # Initialize correlation id and use structured logger wired to GUI
    set_correlation_id()
    logger = get_logger_for_gui(log_cb, name="emumanager.workers.verification")
    report = VerifyReport(text="")

    dat_path = getattr(args, "dat_path", None)

    # Auto-discovery logic if no specific DAT is provided
    dats_roots = getattr(args, "dats_roots", [])
    # Backwards compatibility
    single_root = getattr(args, "dats_root", None)
    if single_root:
        dats_roots.append(single_root)

    # Try to infer system from base_path name (e.g. "snes", "ps2")
    system_name = base_path.name

    if dats_roots and system_name:
        logger.info(f"Attempting to find DAT for system: {system_name}")

        # Search in all roots
        for root in dats_roots:
            if not root.exists():
                continue

            found = find_dat_for_system(Path(root), system_name)
            if found:
                dat_path = found
                logger.info(f"Auto-selected DAT: {found.name} (in {root})")
                break

        if not dat_path:
            logger.warning(
                f"No matching DAT found for system '{system_name}' "
                f"in {len(dats_roots)} locations"
            )

    if not dat_path or not Path(dat_path).exists():
        report.text = "Error: No valid DAT file selected or found."
        return report

    logger.info(f"Parsing DAT file: {dat_path}...")
    try:
        db = dat_parser.parse_dat_file(Path(dat_path))
        logger.info(f"DAT Loaded: {db.name} ({db.version})")
    except Exception as e:
        report.text = f"Error parsing DAT: {e}"
        return report

    return _run_verification(base_path, db, args, logger, list_files_fn)


@log_call(level=logging.INFO)
def worker_identify_all(
    base_path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    list_files_fn: Callable[[Path], list[Path]],
    **kwargs
) -> VerifyReport:
    """Worker function to identify files against ALL available DATs."""
    # Initialize correlation id and use structured logger wired to GUI
    set_correlation_id()
    logger = get_logger_for_gui(log_cb, name="emumanager.workers.verification")
    report = VerifyReport(text="")

    dats_roots = getattr(args, "dats_roots", [])
    # Backwards compatibility / fallback
    single_root = getattr(args, "dats_root", None)
    if single_root:
        dats_roots.append(single_root)

    # Filter existing roots
    dats_roots = [r for r in dats_roots if r and r.exists()]

    if not dats_roots:
        report.text = "Error: DATs directory not found."
        return report

    # 1. Load all DATs
    master_db = dat_parser.DatDb()
    master_db.name = "Master DB"

    dat_files_set = set()
    for root in dats_roots:
        dat_files_set.update(root.rglob("*.dat"))
        dat_files_set.update(root.rglob("*.xml"))

    dat_files = sorted(list(dat_files_set))

    if not dat_files:
        report.text = "No DAT files found."
        return report

    logger.info(f"Loading {len(dat_files)} DAT files into memory...")

    progress_cb = getattr(args, "progress_callback", None)

    for i, dat_file in enumerate(dat_files):
        try:
            if progress_cb:
                progress_cb(i / len(dat_files), f"Loading DAT: {dat_file.name}")

            db = dat_parser.parse_dat_file(dat_file)
            dat_parser.merge_dbs(master_db, db)
        except Exception as e:
            logger.warning(f"Failed to parse {dat_file.name}: {e}")

    logger.info(f"Master DB loaded. CRC entries: {len(master_db.crc_index)}")

    return _run_verification(base_path, master_db, args, logger, list_files_fn)


def _run_verification(base_path, db, args, logger, list_files_fn) -> VerifyReport:
    report = VerifyReport(text="")
    files = list_files_fn(base_path)
    if not files:
        report.text = "No files found to verify."
        return report

    logger.info(f"Verifying {len(files)} files against DB...")

    # Initialize Library DB
    lib_db = LibraryDB()

    verified = 0
    unknown = 0
    mismatch = 0
    compressed = 0
    hash_failed = 0

    total = len(files)
    progress_cb = getattr(args, "progress_callback", None)
    cancel_event = getattr(args, "cancel_event", None)

    for i, f in enumerate(files):
        if cancel_event and cancel_event.is_set():
            logger.warning(MSG_CANCELLED)
            break

        # Calculate progress range for this file
        start_prog = i / total
        file_weight = 1.0 / total

        # If scanner already marked this file as COMPRESSED, skip expensive
        # verification and record a COMPRESSED result for reporting.
        if skip_if_compressed(f, logger):
            compressed += 1
            from emumanager.common.models import VerifyResult as _VR

            res = _VR(
                filename=f.name,
                status="COMPRESSED",
                match_name="Compressed File",
                crc=None,
                sha1=None,
                md5=None,
                sha256=None,
                full_path=str(f),
            )
            report.results.append(res)
            continue

        res = _verify_single_file(
            f, db, args, progress_cb, start_prog, file_weight, lib_db, logger
        )

        if res.status == "VERIFIED":
            verified += 1
            logger.info(f"✅ VERIFIED: {f.name} -> {res.match_name}")
        elif res.status == "MISMATCH":
            mismatch += 1
            logger.warning(
                f"⚠️ MISMATCH: {f.name} "
                f"(Expected: {res.match_name}, CRC: {res.crc}, "
                f"SHA1: {res.sha1}, MD5: {res.md5})"
            )
        elif res.status == "COMPRESSED":
            compressed += 1
            logger.info(
                f"ℹ️ COMPRESSED: {f.name} "
                f"(Cannot verify against ISO DAT without decompression)"
            )
        elif res.status == "HASH_FAILED":
            # Hashing failed (I/O or permission error). Surface diagnostic info.
            hash_failed += 1
            logger.warning(
                f"❌ HASH FAILED: {f.name} "
                f"({res.match_name or 'Could not calculate hashes'}) "
                f"(CRC: {res.crc}, SHA1: {res.sha1}, MD5: {res.md5})"
            )
        else:
            unknown += 1
            logger.warning(
                f"❌ UNKNOWN: {f.name} "
                f"(CRC: {res.crc}, SHA1: {res.sha1}, MD5: {res.md5})"
            )

        report.results.append(res)

    if progress_cb:
        progress_cb(1.0, "Verification complete")

    report.text = (
        f"Verification complete. Verified: {verified}, "
        f"Unknown: {unknown}, Mismatch: {mismatch}, Compressed: {compressed}, "
        f"HashFailed: {hash_failed}"
    )
    return report


def _check_mismatch(db, crc, md5, sha1) -> Optional[str]:
    """Check if CRC matches but MD5/SHA1 do not. Returns match name if mismatch."""
    if not crc or not (md5 or sha1):
        return None

    crc_candidates = []
    if hasattr(db, "crc_index") and isinstance(db.crc_index, dict):
        crc_candidates = db.crc_index.get(crc.lower(), [])

    if not crc_candidates or not isinstance(crc_candidates, list):
        return None

    for cand in crc_candidates:
        md5_ok = (not md5) or (cand.md5 and cand.md5.lower() == md5.lower())
        sha1_ok = (not sha1) or (cand.sha1 and cand.sha1.lower() == sha1.lower())
        if md5_ok and sha1_ok:
            return None  # Found a full match (or at least consistent one)

    return crc_candidates[0].game_name + " (Hash Mismatch)"


def _verify_single_file(
    f: Path,
    db,
    args,
    progress_cb,
    start_prog,
    file_weight,
    lib_db: Optional[LibraryDB] = None,
    logger: Optional[GuiLogger] = None,
) -> VerifyResult:
    # Prefer an explicitly passed logger, fall back to args.logger if available
    eff_logger = logger or getattr(args, "logger", None)
    # Fast-path: compressed container formats cannot be verified against ISO-style DATs
    # without decompression or a Dolphin-specific verifier.
    compressed_exts = {".rvz", ".cso", ".chd", ".wbfs", ".gcz"}
    # handle multi-suffix like .nkit.iso
    suffix = f.suffix.lower()
    f_to_check = None
    # If it's a CHD and the caller requested on-the-fly decompression, try to
    # extract to a temporary ISO using chdman and verify that instead. This is
    # opt-in via args.decompress_chd to avoid surprises.
    if suffix == ".chd" and getattr(args, "decompress_chd", False):
        chdman = workers_common.find_tool("chdman")
        if chdman:
            tmpfile = None
            try:
                # Create a temp file for the extracted ISO
                fd, tmp_path = tempfile.mkstemp(suffix=".iso")
                os.close(fd)
                tmpfile = Path(tmp_path)
                cmd = [
                    str(chdman),
                    "extract",
                    "-i",
                    str(f),
                    "-o",
                    str(tmpfile),
                ]
                if eff_logger:
                    eff_logger.info(
                        f"Attempting to extract CHD for verification: {f.name}"
                    )
                # Stream extraction so we can surface progress to GUI when
                # available
                res = run_cmd_stream(
                    cmd,
                    progress_cb=getattr(args, "progress_callback", None),
                )
                if getattr(res, "returncode", 1) == 0 and tmpfile.exists():
                    # Use the extracted ISO for subsequent hashing/lookup
                    if eff_logger:
                        eff_logger.info(
                            f"CHD extracted to temporary ISO: {tmpfile.name}"
                        )
                    f_to_check = tmpfile
                else:
                    if eff_logger:
                        eff_logger.warning(
                            f"chdman failed to extract {f.name}; falling back to "
                            "compressed status"
                        )
                    f_to_check = None
            except Exception as e:
                if eff_logger:
                    eff_logger.warning(f"CHD extraction failed for {f.name}: {e}")
                f_to_check = None
        else:
            f_to_check = None

        # If we attempted extraction but failed, treat as compressed
        if f_to_check is None:
            res = VerifyResult(
                filename=f.name,
                status="COMPRESSED",
                match_name="Compressed File",
                crc=None,
                sha1=None,
                md5=None,
                sha256=None,
                full_path=str(f),
            )
            # Still write/update entry so UI can show it as compressed
            if lib_db:
                try:
                    st = f.stat()
                    lib_db.update_entry(
                        LibraryEntry(
                            path=str(f.resolve()),
                            system=getattr(args, "system_name", "unknown"),
                            size=st.st_size,
                            mtime=st.st_mtime,
                            crc32=None,
                            md5=None,
                            sha1=None,
                            sha256=None,
                            status=res.status,
                            match_name=res.match_name,
                            dat_name=None,
                        )
                    )
                except OSError:
                    pass
            return res
        else:
            # Swap f to the extracted ISO for the rest of the function
            original_f = f
            f = f_to_check
    else:
        # Non-CHD path: if a known compressed extension (or nkit), mark compressed
        if f.name.lower().endswith(".nkit.iso") or suffix in compressed_exts:
            res = VerifyResult(
                filename=f.name,
                status="COMPRESSED",
                match_name="Compressed File",
                crc=None,
                sha1=None,
                md5=None,
                sha256=None,
                full_path=str(f),
            )
            if lib_db:
                try:
                    st = f.stat()
                    lib_db.update_entry(
                        LibraryEntry(
                            path=str(f.resolve()),
                            system=getattr(args, "system_name", "unknown"),
                            size=st.st_size,
                            mtime=st.st_mtime,
                            crc32=None,
                            md5=None,
                            sha1=None,
                            sha256=None,
                            status=res.status,
                            match_name=res.match_name,
                            dat_name=None,
                        )
                    )
                except OSError:
                    pass
            return res

    file_prog_cb = create_file_progress_cb(progress_cb, start_prog, file_weight, f.name)

    # Check Library DB first
    if lib_db:
        try:
            abs_path = str(f.resolve())
            entry = lib_db.get_entry(abs_path)
            if entry:
                st = f.stat()
                # Check if file hasn't changed (size and mtime)
                if st.st_size == entry.size and abs(st.st_mtime - entry.mtime) < 1.0:
                    # Ensure cached entry actually contains hashes; if not,
                    # proceed to re-hash
                    has_hash = bool(
                        entry.crc32 or entry.sha1 or entry.md5 or entry.sha256
                    )
                    if not has_hash:
                        # treat as cache miss
                        if progress_cb:
                            progress_cb(
                                start_prog + file_weight,
                                f"Cached entry missing hashes; re-hashing {f.name}",
                            )
                    else:
                        if progress_cb:
                            progress_cb(
                                start_prog + file_weight,
                                f"Using cached result for {f.name}",
                            )

                        return VerifyResult(
                            filename=f.name,
                            status=entry.status,
                            match_name=entry.match_name,
                            crc=entry.crc32,
                            sha1=entry.sha1,
                            md5=entry.md5,
                            sha256=entry.sha256,
                            full_path=str(f),
                            dat_name=entry.dat_name,
                        )
        except (OSError, ValueError):
            # File might have been deleted or path issue
            pass

    if progress_cb:
        progress_cb(start_prog, f"Hashing {f.name}...")

    # Calculate hashes. For speed, default to CRC32 + SHA1;
    # if deep_verify is enabled, include MD5 and SHA256.
    algos = ("crc32", "sha1")
    if getattr(args, "deep_verify", False):
        algos = ("crc32", "md5", "sha1", "sha256")

    hashes = hasher.calculate_hashes(f, algorithms=algos, progress_cb=file_prog_cb)
    crc = hashes.get("crc32")
    md5 = hashes.get("md5")
    sha1 = hashes.get("sha1")
    sha256 = hashes.get("sha256")

    hash_fail = False
    if not hashes or all(v is None for v in [crc, md5, sha1, sha256]):
        hash_fail = True

    matches = db.lookup(crc=crc, md5=md5, sha1=sha1) if not hash_fail else []
    match = matches[0] if matches else None

    fail_reason = None
    if hash_fail:
        fail_reason = "HASH_FAILED: Could not read or hash file."
        # Log detailed error for diagnosis
        try:
            st = f.stat()
        except Exception as e:
            fail_reason += f" Stat failed: {e}"
        # Optionally, log to logger if available
        # Optionally log to provided logger (or args.logger)
        try:
            if eff_logger:
                eff_logger.warning(f"Hash calculation failed for {f}: {fail_reason}")
        except Exception:
            pass

    res = VerifyResult(
        filename=f.name,
        status="UNKNOWN" if not hash_fail else "HASH_FAILED",
        match_name=fail_reason,
        crc=crc,
        sha1=sha1,
        md5=md5,
        sha256=sha256,
        full_path=str(f),
    )

    if match:
        res.status = "VERIFIED"
        res.match_name = match.game_name
        res.dat_name = getattr(match, "dat_name", None)
    else:
        mismatch_reason = _check_mismatch(db, crc, md5, sha1)
        if mismatch_reason:
            res.status = "MISMATCH"
            res.match_name = mismatch_reason
    # COMPRESSED already handled before hashing; if it got here, we
    # keep UNKNOWN/MISMATCH.

    # Update Library DB
    if lib_db:
        try:
            # If we used an extracted temp file, use stats from the original file
            st = original_f.stat() if "original_f" in locals() else f.stat()
            new_entry = LibraryEntry(
                path=str(f.resolve()),
                system=getattr(args, "system_name", "unknown"),
                size=st.st_size,
                mtime=st.st_mtime,
                crc32=res.crc,
                md5=res.md5,
                sha1=res.sha1,
                sha256=res.sha256,
                status=res.status,
                match_name=res.match_name,
                dat_name=res.dat_name,
            )
            lib_db.update_entry(new_entry)
        except OSError:
            pass
    # Cleanup temporary extraction file if created
    if "original_f" in locals():
        try:
            if f.exists():
                f.unlink()
                logger.info(f"Removed temporary extracted ISO: {f}")
        except Exception:
            pass
    return res


@log_call(level=logging.INFO)
def worker_identify_single_file(
    file_path: Path,
    dat_path: Path,
    log_cb: Callable[[str], None],
    progress_cb: Optional[Callable[[float], None]] = None,
    **kwargs
) -> str:
    """Identify a single file against a DAT database."""
    # Initialize correlation id and use structured logger wired to GUI
    set_correlation_id()
    logger = get_logger_for_gui(log_cb, name="emumanager.workers.verification")

    # Initialize LibraryDB
    lib_db = LibraryDB()

    if not dat_path.exists():
        return "Error: DAT file not found."

    logger.info(f"Parsing DAT file: {dat_path}...")
    try:
        db = dat_parser.parse_dat_file(dat_path)
    except Exception as e:
        return f"Error parsing DAT: {e}"

    # Check DB
    cached_hashes = {}
    try:
        entry = lib_db.get_entry(str(file_path.resolve()))
        if entry:
            st = file_path.stat()
            if st.st_size == entry.size and abs(st.st_mtime - entry.mtime) < 1.0:
                logger.info(f"Using cached hashes for {file_path.name}")
                cached_hashes = {
                    "crc32": entry.crc32,
                    "md5": entry.md5,
                    "sha1": entry.sha1,
                }
    except (OSError, ValueError):
        pass

    if not cached_hashes:
        logger.info(f"Calculating hashes for {file_path.name}...")
        cached_hashes = hasher.calculate_hashes(
            file_path, algorithms=("crc32", "md5", "sha1"), progress_cb=progress_cb
        )

    crc = cached_hashes.get("crc32")
    md5 = cached_hashes.get("md5")
    sha1 = cached_hashes.get("sha1")

    logger.info(f"Hashes: CRC={crc}, MD5={md5}, SHA1={sha1}")

    matches = db.lookup(crc=crc, md5=md5, sha1=sha1)
    match = matches[0] if matches else None

    # Update DB with result
    try:
        st = file_path.stat()
        status = "VERIFIED" if match else "UNKNOWN"
        match_name = match.game_name if match else None

        new_entry = LibraryEntry(
            path=str(file_path.resolve()),
            system="unknown",
            size=st.st_size,
            mtime=st.st_mtime,
            crc32=crc,
            md5=md5,
            sha1=sha1,
            sha256=None,
            status=status,
            match_name=match_name,
            dat_name=getattr(match, "dat_name", None),
        )
        lib_db.update_entry(new_entry)
    except OSError:
        pass

    if match:
        return (
            f"MATCH FOUND!\n"
            f"Game: {match.game_name}\n"
            f"ROM:  {match.rom_name}\n"
            f"Size: {match.size} bytes"
        )
    else:
        return "No match found in database."
