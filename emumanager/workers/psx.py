from __future__ import annotations
from pathlib import Path
from typing import Any, Callable, Optional
import re
import subprocess

from emumanager.common.execution import find_tool
from emumanager.psx import metadata as psx_meta
from emumanager.psx import database as psx_db
from emumanager.workers.common import (
    GuiLogger, 
    MSG_CANCELLED, 
    find_target_dir, 
    calculate_file_hash, 
    create_file_progress_cb,
    emit_verification_result,
    make_result_collector
)
from emumanager.common.models import VerifyResult

MSG_PSX_DIR_NOT_FOUND = "PS1 ROMs directory not found."
PSX_SUBDIRS = ["roms/psx", "psx"]

def _chdman_create(output: Path, input_path: Path) -> subprocess.Popen:
    chdman = find_tool("chdman")
    if not chdman:
        raise RuntimeError("'chdman' not found in PATH")
    # Use -i input -o output -f to force overwrite if exists? We'll avoid -f for safety.
    return subprocess.Popen([str(chdman), "createcd", "-i", str(input_path), "-o", str(output)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

def _collect_psx_inputs_for_conversion(target_dir: Path) -> list[Path]:
    """Collect candidate source files for PS1 conversion, preferring CUE over BIN.

    Also skip all BIN files in any directory that contains a CUE (handles multi-bin cuesheets).
    """
    raw = [p for p in target_dir.rglob("*") if p.is_file() and p.suffix.lower() in {".cue", ".bin", ".iso"}]
    cue_dirs = {p.parent for p in raw if p.suffix.lower() == ".cue"}
    filtered: list[Path] = []
    for f in raw:
        suf = f.suffix.lower()
        if suf == ".bin":
            # Skip if matching CUE exists or any CUE exists in same directory (multi-bin)
            if f.with_suffix(".cue").exists() or f.parent in cue_dirs:
                continue
        filtered.append(f)
    return filtered

def _convert_one_with_chdman(src: Path, logger: GuiLogger, dry_run: bool) -> tuple[bool, bool]:
    """Run chdman for a single source. Returns (converted, skipped)."""
    out = src.with_suffix(".chd")
    if out.exists():
        logger.warning(f"Skip (exists): {out.name}")
        return False, True
    if dry_run:
        logger.info(f"[DRY] chdman createcd -i {src.name} -o {out.name}")
        return True, False
    try:
        proc = _chdman_create(out, src)
        if proc.stdout:
            for line in proc.stdout:
                try:
                    logger.info(line.decode("utf-8", errors="ignore").rstrip())
                except Exception:
                    pass
        rc = proc.wait()
        if rc == 0:
            return True, False
        logger.error(f"chdman failed ({rc}) for {src.name}")
        return False, False
    except Exception as e:
        logger.error(f"Conversion error for {src.name}: {e}")
        return False, False

def worker_psx_convert(base_path: Path, args: Any, log_cb: Callable[[str], None]) -> str:
    """Convert PS1 CUE/BIN/ISO to CHD using chdman."""
    logger = GuiLogger(log_cb)
    target_dir = find_target_dir(base_path, PSX_SUBDIRS)
    if not target_dir:
        return MSG_PSX_DIR_NOT_FOUND

    chdman = find_tool("chdman")
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
        if progress_cb:
            progress_cb(i / total, f"Converting {src.name}...")
        did_convert, did_skip = _convert_one_with_chdman(src, logger, dry_run)
        if did_convert:
            converted += 1
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
        sha1=sha1 if deep_verify else None
    )
    return "found" if serial else "unknown"



def worker_psx_verify(base_path: Path, args: Any, log_cb: Callable[[str], None], list_files_fn: Callable[[Path], list[Path]]) -> str:
    logger = GuiLogger(log_cb)
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
    collector = make_result_collector(per_file_cb_attr, results_list_attr) if (callable(per_file_cb_attr) or isinstance(results_list_attr, list)) else None

    for i, f in enumerate(files):
        if cancel_event and cancel_event.is_set():
            logger.warning(MSG_CANCELLED)
            break
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

def _organize_psx_file(f: Path, args: Any, logger: GuiLogger) -> tuple[bool, Optional[str]]:
    if f.suffix.lower() not in {".bin", ".cue", ".iso", ".chd", ".gz", ".img"}:
        return False, None
    # If CUE present, prefer reading serial from BIN alongside
    src_for_serial = f
    if f.suffix.lower() == ".cue":
        bin_path = f.with_suffix(".bin")
        if bin_path.exists():
            src_for_serial = bin_path
    serial = psx_meta.get_psx_serial(src_for_serial)
    if not serial:
        logger.warning(f"Could not extract serial from {f.name}")
        return False, None
    title = psx_db.db.get_title(serial) or "Unknown Title"
    safe_title = re.sub(r'[<>:"/\\|?*]', '', title).strip()
    new_name = f"{safe_title} [{serial}]{f.suffix}"
    new_path = f.parent / new_name
    if f.name == new_name or new_path.exists():
        return False, None
    try:
        if not args.dry_run:
            f.rename(new_path)
        logger.info(f"Renamed: {f.name} -> {new_name}")
        return True, new_name
    except Exception as e:
        logger.error(f"Failed to rename {f.name}: {e}")
        return False, None

def worker_psx_organize(base_path: Path, args: Any, log_cb: Callable[[str], None], list_files_fn: Callable[[Path], list[Path]]) -> str:
    logger = GuiLogger(log_cb)
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
