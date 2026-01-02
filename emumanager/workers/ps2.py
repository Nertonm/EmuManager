from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional

from emumanager.common.execution import run_cmd_stream
from emumanager.converters import ps2_converter
from emumanager.library import LibraryDB, LibraryEntry
from emumanager.logging_cfg import log_call, set_correlation_id
from emumanager.ps2 import database as ps2_db
from emumanager.ps2 import metadata as ps2_meta
from emumanager.workers import common as workers_common
from emumanager.workers.common import (
    MSG_CANCELLED,
    GuiLogger,
    GuiLogHandler,
    calculate_file_hash,
    create_file_progress_cb,
    emit_verification_result,
    find_target_dir,
    get_logger_for_gui,
    identify_game_by_hash,
    make_result_collector,
    skip_if_compressed,
)

# Backwards-compatible aliases so tests that patch module-level helpers
# (e.g. monkeypatch.setattr(ps2_module, 'find_tool', ...)) continue to work.
# These resolve to the dynamic wrappers in workers_common at runtime.
find_tool = workers_common.find_tool
run_cmd = workers_common.run_cmd


def _strip_serial_tokens(name: str) -> str:
    """Remove bracketed serial-like tokens from a filename stem.

    Matches tokens like [SLUS-20946], [SLUS20946], [SLUS-20946.02], etc.
    """
    pattern = re.compile(
        r"\s*\[[A-Z]{2,6}-?\d{2,6}(?:[._-]?\d{1,2})?\]\s*",
        re.IGNORECASE,
    )
    cleaned = pattern.sub(" ", name)
    return re.sub(r"\s+", " ", cleaned).strip()


MSG_PS2_DIR_NOT_FOUND = "PS2 ROMs directory not found."
PS2_SUBDIRS = ["roms/ps2", "ps2"]


@log_call(level=logging.INFO)
def worker_ps2_convert(
    base_path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    list_files_fn: Optional[Callable[[Path], list[Path]]] = None,
) -> str:
    """Worker function for PS2 CSO -> CHD conversion.

    Note: `list_files_fn` is accepted for compatibility with the controller
    dispatch helper which passes a list_files_fn for directory-style workers.
    This worker uses the converter's internal directory scanning and thus may
    ignore `list_files_fn`.
    """
    # Initialize correlation id and use structured logger wired to GUI
    set_correlation_id()
    logger = get_logger_for_gui(log_cb, name="emumanager.workers.ps2")

    target_dir = find_target_dir(base_path, PS2_SUBDIRS)
    if not target_dir:
        return MSG_PS2_DIR_NOT_FOUND

    logger.info(f"Starting PS2 conversion in: {target_dir}")

    # We need to find tools manually or assume they are in path
    # Use the module-level alias `find_tool` so tests can monkeypatch
    # `emumanager.workers.ps2.find_tool` easily.
    maxcso = find_tool("maxcso")
    chdman = find_tool("chdman")

    if not maxcso or not chdman:
        return "Error: 'maxcso' or 'chdman' not found in PATH."

    # Configure logging redirection
    ps2_logger = logging.getLogger("ps2_converter")
    handler = GuiLogHandler(log_cb)
    handler.setFormatter(logging.Formatter("%(message)s"))
    ps2_logger.addHandler(handler)
    # Ensure we capture info logs
    ps2_logger.setLevel(logging.INFO)

    try:
        results = ps2_converter.convert_directory(
            directory=target_dir,
            maxcso=maxcso,
            chdman=chdman,
            backup_dir=target_dir / "_BACKUP_CSO",
            dry_run=args.dry_run,
            remove_original=args.rm_originals,
            progress_callback=getattr(args, "progress_callback", None),
        )

        converted = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)

        return f"PS2 Conversion complete. Converted: {converted}, Failed: {failed}"
    except Exception as e:
        return f"PS2 Conversion failed: {e}"
    finally:
        ps2_logger.removeHandler(handler)


@log_call(level=logging.INFO)
def worker_chd_to_cso_single(
    path: Path, args: Any, log_cb: Callable[[str], None]
) -> str:
    """Extract a single .chd to ISO and compress to .cso using chdman + maxcso.

    Output will be next to the original with a .cso suffix. Does not remove
    the original .chd.
    """
    # Initialize correlation id and use structured logger wired to GUI
    set_correlation_id()
    logger = get_logger_for_gui(log_cb, name="emumanager.workers.ps2")

    chdman = find_tool("chdman")
    maxcso = find_tool("maxcso")
    if not chdman or not maxcso:
        return "Error: 'chdman' or 'maxcso' not found in PATH."

    if path.suffix.lower() != ".chd":
        logger.warning(f"No CHD->CSO handler for {path.suffix}")
        return "No-op"

    out_cso = path.with_suffix(".cso")
    if out_cso.exists():
        logger.info(f"Skipping compress, output exists: {out_cso.name}")
        return f"Skipped (exists): {out_cso.name}"

    tmp_iso = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".iso", delete=False) as tf:
            tmp_iso = Path(tf.name)

        # Try extraction verbs
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

        # compress iso -> cso
        # Use maxcso similar to psp converter
        try:
            cmd = [str(maxcso), "--best", "-o", str(out_cso), str(tmp_iso)]
            res = run_cmd_stream(
                cmd, progress_cb=getattr(args, "progress_callback", None)
            )
            if getattr(res, "returncode", 1) != 0:
                logger.error(f"maxcso failed (rc={getattr(res, 'returncode', 'N/A')})")
                return f"Error: maxcso failed ({getattr(res, 'returncode', 'N/A')})"
        except Exception as e:
            logger.error(f"maxcso error: {e}")
            return f"Error: {e}"
        logger.info(f"Compressed CHD -> CSO: {out_cso.name}")

        # Compute and persist hashes from the extracted ISO so we retain
        # verification info for the resulting CSO even if the original CHD
        # is removed later.
        try:
            from emumanager.library import LibraryDB, LibraryEntry
            from emumanager.workers.common import ensure_hashes_in_db

            md5_val, sha1_val = ensure_hashes_in_db(tmp_iso)
            if out_cso.exists():
                lib_db = LibraryDB()
                try:
                    st = out_cso.stat()
                    # Store path as-written (not forcibly resolved) so tests
                    # that query by the original string path find the entry.
                    new_entry = LibraryEntry(
                        path=str(out_cso),
                        system="ps2",
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
                            str(out_cso), "COMPRESSED", f"Converted from {path.name}"
                        )
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            pass

        return f"Compressed: {out_cso.name}"
    finally:
        try:
            if tmp_iso and tmp_iso.exists():
                tmp_iso.unlink()
        except Exception:
            pass


def _process_ps2_file(
    f: Path,
    logger: GuiLogger,
    args: Any = None,
    deep_verify: bool = False,
    progress_cb: Optional[Callable[[float], None]] = None,
    per_file_cb: Optional[Callable[[Any], None]] = None,
) -> str:
    """
    Process a single PS2 file to extract serial and identify title.
    Returns: 'found', 'unknown', or 'skip'.
    """
    suffix = f.suffix.lower()
    if suffix not in {".iso", ".bin", ".cso", ".chd", ".gz"}:
        return "skip"

    # For CHD files, prefer using chdman verify to check internal integrity
    # before attempting header extraction or other processing. Make this
    # optional via args.verify_chd (default True) so callers can opt-out.
    if suffix == ".chd":
        do_verify = True
        try:
            if args is not None:
                do_verify = bool(getattr(args, "verify_chd", True))
            else:
                do_verify = True
        except Exception:
            do_verify = True

        if do_verify:
            try:
                ok = workers_common.verify_chd(f)
            except Exception:
                ok = False
            if not ok:
                logger.warning(f"[SKIP] CHD integrity check failed: {f.name}")
                return "unknown"

    # Initialize LibraryDB
    lib_db = LibraryDB()

    tmp_iso = None
    hash_source = f
    if suffix == ".cso":
        # If user opted-in, try to extract with maxcso and read header
        try:
            decompress_flag = (
                bool(getattr(args, "decompress_cso", False)) if args else False
            )
        except Exception:
            decompress_flag = False

        if not decompress_flag:
            logger.warning(
                f"[SKIP] Cannot extract serial from compressed file: {f.name}"
            )
            return "unknown"

        maxcso = workers_common.find_tool("maxcso")
        if not maxcso:
            logger.warning("maxcso not found; cannot extract from CSO")
            return "unknown"

        try:
            with tempfile.NamedTemporaryFile(suffix=".iso", delete=False) as tf:
                tmp_iso = Path(tf.name)

            # Decompress CSO -> ISO
            cmd = [str(maxcso), "--decompress", str(f), "-o", str(tmp_iso)]
            res = run_cmd_stream(
                cmd, progress_cb=getattr(args, "progress_callback", None)
            )
            rc = getattr(res, "returncode", 1)
            if rc != 0 or not tmp_iso.exists():
                logger.warning(f"maxcso failed ({rc}) for {f.name}")
                try:
                    if tmp_iso.exists():
                        tmp_iso.unlink()
                except Exception:
                    pass
                return "unknown"

            # Use tmp_iso as the source for serial/header extraction and hashing
            serial = ps2_meta.get_ps2_serial(tmp_iso)
            hash_source = tmp_iso
        except Exception:
            logger.warning(f"Failed to extract CSO for header read: {f.name}")
            try:
                if tmp_iso and tmp_iso.exists():
                    tmp_iso.unlink()
            except Exception:
                pass
            return "unknown"

    serial = ps2_meta.get_ps2_serial(f)
    info_str = ""
    title = None

    if serial:
        title = ps2_db.db.get_title(serial)
        if title:
            info_str = f"[{serial}] {title}"
        else:
            info_str = f"[{serial}] Unknown Title"
    else:
        info_str = "[NO SERIAL] Could not identify"

    # Check Cache for hashes
    cached_md5 = None
    cached_sha1 = None

    try:
        entry = lib_db.get_entry(str(f.resolve()))
        if entry:
            st = f.stat()
            if st.st_size == entry.size and abs(st.st_mtime - entry.mtime) < 1.0:
                cached_md5 = entry.md5
                cached_sha1 = entry.sha1
    except (OSError, ValueError):
        pass

    md5: Optional[str] = cached_md5
    sha1: Optional[str] = cached_sha1

    if deep_verify:
        if not md5 or not sha1:
            logger.info(f"Hashing {hash_source.name}...")
            md5 = calculate_file_hash(hash_source, "md5", progress_cb=progress_cb)
            sha1 = calculate_file_hash(hash_source, "sha1", progress_cb=progress_cb)
        info_str += f" | MD5: {md5} | SHA1: {sha1}"

    logger.info(f"{info_str} -> {f.name}")

    status = "VERIFIED" if serial else "UNKNOWN"

    # Update Cache
    try:
        st = f.stat()
        new_entry = LibraryEntry(
            path=str(f.resolve()),
            system="ps2",
            size=st.st_size,
            mtime=st.st_mtime,
            crc32=None,
            md5=md5,
            sha1=sha1,
            sha256=None,
            status=status,
            match_name=title,
            dat_name=serial,  # Storing serial in dat_name for now
        )
        lib_db.update_entry(new_entry)
    except OSError:
        pass

    emit_verification_result(
        per_file_cb,
        f,
        status=status,
        serial=serial,
        title=title,
        md5=md5,
        sha1=sha1,
    )

    # cleanup any temporary ISO we created
    try:
        if tmp_iso and tmp_iso.exists():
            tmp_iso.unlink()
    except Exception:
        pass

    return "found" if serial else "unknown"


@log_call(level=logging.INFO)
def worker_ps2_verify(
    base_path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    list_files_fn: Callable[[Path], list[Path]],
) -> str:
    """Worker function for PS2 verification (Serial extraction)."""
    # Initialize correlation id and use structured logger wired to GUI
    set_correlation_id()
    logger = get_logger_for_gui(log_cb, name="emumanager.workers.ps2")

    target_dir = find_target_dir(base_path, PS2_SUBDIRS)
    if not target_dir:
        return MSG_PS2_DIR_NOT_FOUND

    # Try to load DB from base path
    db_path = base_path / "ps2_db.csv"
    if db_path.exists():
        ps2_db.db.load_from_csv(db_path)
        logger.info(f"Loaded PS2 database from {db_path}")

    files = list_files_fn(target_dir)
    if not files:
        return "No PS2 files found."

    logger.info(f"Scanning {len(files)} files for PS2 Serials...")

    found = 0
    unknown = 0
    total_files = len(files)
    progress_cb = getattr(args, "progress_callback", None)
    cancel_event = getattr(args, "cancel_event", None)
    deep_verify = getattr(args, "deep_verify", False)

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

        # Skip files flagged as compressed by scanner
        try:
            # If scanner marked as COMPRESSED, normally we skip. For .chd
            # files we still want to attempt PS2-specific processing (serial
            # extraction / chdman verify), so don't skip .chd here.
            if skip_if_compressed(f, logger) and f.suffix.lower() != ".chd":
                unknown += 1
                continue
        except Exception:
            pass

        # Calculate progress range for this file
        start_prog = i / total_files
        file_weight = 1.0 / total_files

        file_prog_cb = create_file_progress_cb(
            progress_cb, start_prog, file_weight, f.name
        )

        if progress_cb:
            progress_cb(start_prog, f"Verifying {f.name}...")

        res = _process_ps2_file(
            f,
            logger,
            args,
            deep_verify=deep_verify,
            progress_cb=file_prog_cb,
            per_file_cb=collector,
        )
        if res == "found":
            found += 1
        elif res == "unknown":
            unknown += 1

    if progress_cb:
        progress_cb(1.0, "PS2 Verification complete")

    return f"Scan complete. Identified: {found}, Unknown: {unknown}"


def _organize_ps2_file(f: Path, args: Any, logger: GuiLogger) -> bool:
    if f.suffix.lower() not in {".iso", ".bin", ".cso", ".chd", ".gz"}:
        return False
    # Try to get serial from file metadata first
    serial = ps2_meta.get_ps2_serial(f)
    title = ps2_db.db.get_title(serial) if serial else None

    # If we couldn't get a useful serial/title, try to identify by hash
    if not serial or not title:
        try:
            lib_db = LibraryDB()
            found = identify_game_by_hash(f, db=lib_db)
            if found:
                # Prefer dat_name for serial if present
                if not serial and found.dat_name:
                    serial = found.dat_name
                # Prefer match_name for title if present
                if not title and found.match_name:
                    # match_name may include [SERIAL] suffix; strip if present
                    title = found.match_name.split("[")[0].strip()
                logger.info(f"Identified by hash: using library match for {f.name}")
        except Exception:
            # Identification failed silently; we'll continue to fallback warnings
            pass

    if not serial:
        logger.warning(f"Could not extract serial from {f.name}")
        return False

    # If serial exists but title not found in ps2 DB, fall back to filename
    if not title:
        logger.warning(
            "Serial %s not found in DB for %s; falling back to filename",
            serial,
            f.name,
        )
        # Use the file stem but strip any existing bracketed serial tokens
        # to avoid appending duplicate [SERIAL] tags on repeated runs.
        raw = f.stem
        # Strip common serial-like tokens in brackets. Accept variations like:
        # [SLUS-20946], [SLUS20946], [SLUS-20946.02], [SLUS20946_02]
        cleaned = _strip_serial_tokens(raw)
        if cleaned != raw:
            logger.info(
                "Stripped existing serial tags from filename: '%s' -> '%s'",
                raw,
                cleaned,
            )
        title = cleaned

    # Sanitize title
    safe_title = re.sub(r'[<>:"/\\|?*]', "", title).strip()

    # PS2 doesn't have region in metadata easily available yet
    # Standard: "Title [Serial]"
    new_name = f"{safe_title} [{serial}]{f.suffix}"

    new_path = f.parent / new_name

    if f.name == new_name:
        return False

    if new_path.exists():
        logger.warning(f"Target file already exists: {new_name}")
        return False

    try:
        lib_db = LibraryDB()
        if not args.dry_run:
            f.rename(new_path)
        logger.info(f"Renamed: {f.name} -> {new_name}")
        # Record audit log for rename
        try:
            lib_db.log_action(str(f.resolve()), "RENAMED", f"{f.name} -> {new_name}")
        except Exception:
            logger.warning(f"Failed to write rename action for {f.name}")
        return True
    except Exception as e:
        logger.error(f"Failed to rename {f.name}: {e}")
        return False


@log_call(level=logging.INFO)
def worker_ps2_organize(
    base_path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    list_files_fn: Callable[[Path], list[Path]],
) -> str:
    """Worker function for PS2 organization (Rename based on DB)."""
    # Initialize correlation id and use structured logger wired to GUI
    set_correlation_id()
    logger = get_logger_for_gui(log_cb, name="emumanager.workers.ps2")

    target_dir = find_target_dir(base_path, PS2_SUBDIRS)
    if not target_dir:
        return MSG_PS2_DIR_NOT_FOUND

    # Try to load DB from base path
    db_path = base_path / "ps2_db.csv"
    if db_path.exists():
        ps2_db.db.load_from_csv(db_path)
        logger.info(f"Loaded PS2 database from {db_path}")

    files = list_files_fn(target_dir)
    if not files:
        return "No PS2 files found."

    logger.info(f"Organizing {len(files)} PS2 files...")

    renamed = 0
    skipped = 0
    total_files = len(files)
    progress_cb = getattr(args, "progress_callback", None)
    cancel_event = getattr(args, "cancel_event", None)

    for i, f in enumerate(files):
        if cancel_event and cancel_event.is_set():
            logger.warning(MSG_CANCELLED)
            break

        if progress_cb:
            progress_cb(i / total_files, f"Organizing {f.name}...")
        try:
            if skip_if_compressed(f, logger):
                skipped += 1
                continue
        except Exception:
            pass

        if _organize_ps2_file(f, args, logger):
            renamed += 1
        else:
            skipped += 1

    if progress_cb:
        progress_cb(1.0, "PS2 Organization complete")

    return f"PS2 Organization complete. Renamed: {renamed}, Skipped: {skipped}"
