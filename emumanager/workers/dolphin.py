from __future__ import annotations
from pathlib import Path
from typing import Any, Callable, Optional
import re

from emumanager.converters.dolphin_converter import DolphinConverter
from emumanager.gamecube import metadata as gc_meta
from emumanager.gamecube import database as gc_db
from emumanager.wii import metadata as wii_meta
from emumanager.wii import database as wii_db
from emumanager.workers.common import (
    GuiLogger, MSG_CANCELLED, calculate_file_hash, create_file_progress_cb,
    emit_verification_result, make_result_collector, VerifyResult
)

DOLPHIN_CONVERTIBLE_EXTENSIONS = {".iso", ".gcm", ".wbfs"}
DOLPHIN_ALL_EXTENSIONS = {".iso", ".gcm", ".wbfs", ".rvz", ".gcZ"}
MSG_NO_GC_WII = "No GameCube or Wii directories found."

def _convert_dolphin_file(f: Path, converter: DolphinConverter, args: Any, logger: GuiLogger) -> bool:
    if f.suffix.lower() not in DOLPHIN_CONVERTIBLE_EXTENSIONS:
        return False
        
    rvz_file = f.with_suffix(".rvz")
    if rvz_file.exists():
        logger.info(f"Skipping {f.name}, RVZ already exists.")
        return False
        
    logger.info(f"Converting {f.name} -> RVZ...")
    success = converter.convert_to_rvz(f, rvz_file)
    
    if success and getattr(args, "rm_originals", False):
        try:
            f.unlink()
            logger.info(f"Deleted original: {f.name}")
        except Exception as e:
            logger.error(f"Failed to delete {f.name}: {e}")
            
    return success

def worker_dolphin_convert(base_path: Path, args: Any, log_cb: Callable[[str], None], list_files_fn: Callable[[Path], list[Path]]) -> str:
    """Worker function for GameCube/Wii RVZ conversion."""
    logger = GuiLogger(log_cb)
    
    targets = _resolve_dolphin_targets(base_path)
    if not targets:
        return MSG_NO_GC_WII

    converter = DolphinConverter()
    if not converter.check_tool():
        return "Error: 'dolphin-tool' not found. Please install Dolphin Emulator."

    total_converted = 0
    
    # Collect all files first to calculate progress
    all_files = []
    for target_dir in targets:
        logger.info(f"Scanning {target_dir}...")
        files = list_files_fn(target_dir)
        # Filter for convertible files
        convertible = [f for f in files if f.suffix.lower() in DOLPHIN_CONVERTIBLE_EXTENSIONS]
        all_files.extend(convertible)
        
    total_files = len(all_files)
    progress_cb = getattr(args, "progress_callback", None)
    cancel_event = getattr(args, "cancel_event", None)
    
    for i, f in enumerate(all_files):
        if cancel_event and cancel_event.is_set():
            logger.warning(MSG_CANCELLED)
            break
            
        if progress_cb:
            progress_cb(i / total_files if total_files > 0 else 0, f"Converting {f.name}...")
            
        if _convert_dolphin_file(f, converter, args, logger):
            total_converted += 1
            
    if progress_cb:
        progress_cb(1.0, "Dolphin Conversion complete")
                 
    return f"Dolphin Conversion complete. Converted: {total_converted}"

def _verify_dolphin_file(f: Path, converter: DolphinConverter, target_dir: Path, logger: GuiLogger, deep_verify: bool = False, progress_cb: Optional[Callable[[float], None]] = None, per_file_cb: Optional[Callable[[VerifyResult], None]] = None) -> bool:
    if f.suffix.lower() not in DOLPHIN_ALL_EXTENSIONS:
        return False
    
    # Identify first
    meta = {}
    system = "UNKNOWN"
    if "gamecube" in str(target_dir).lower():
        meta = gc_meta.get_metadata(f)
        system = "GAMECUBE"
    elif "wii" in str(target_dir).lower():
        meta = wii_meta.get_metadata(f)
        system = "WII"
        
    game_id = meta.get("game_id", "Unknown")
    title = meta.get("internal_name", "")
    
    info_str = f"[{game_id}] "
    if title:
        info_str += f"{title} "

    md5_val = None
    sha1_val = None

    if deep_verify:
        logger.info(f"Hashing {f.name}...")
        md5_val = calculate_file_hash(f, "md5", progress_cb=progress_cb)
        sha1_val = calculate_file_hash(f, "sha1", progress_cb=None)
        info_str += f"| MD5: {md5_val} "
    
    logger.info(f"{info_str}Verifying {f.name}...")
    
    # Dolphin tool verification
    is_valid = converter.verify_rvz(f)
    
    status = "VERIFIED" if is_valid else "BAD_DUMP"
    if is_valid:
        logger.info(f"✅ OK: {f.name}")
    else:
        logger.error(f"❌ FAIL: {f.name}")
        
    emit_verification_result(
        per_file_cb=per_file_cb,
        filename=f.name,
        status=status,
        system=system,
        serial=game_id,
        title=title,
        md5=md5_val,
        sha1=sha1_val
    )
        
    return is_valid

def _collect_dolphin_files(targets: list[Path], list_files_fn: Callable[[Path], list[Path]], logger: GuiLogger) -> list[tuple[Path, Path]]:
    all_files = []
    for target_dir in targets:
        logger.info(f"Scanning {target_dir}...")
        files = list_files_fn(target_dir)
        # Filter relevant files
        relevant = [f for f in files if f.suffix.lower() in DOLPHIN_ALL_EXTENSIONS]
        all_files.extend([(f, target_dir) for f in relevant])
    return all_files

def _resolve_dolphin_targets(base_path: Path) -> list[Path]:
    candidates = [
        base_path / "roms" / "gamecube",
        base_path / "roms" / "wii",
        base_path / "gamecube",
        base_path / "wii"
    ]
    targets = [d for d in candidates if d.exists()]
    if not targets:
        # Fallback to base_path if it looks like a GC/Wii folder
        if "gamecube" in str(base_path).lower() or "wii" in str(base_path).lower():
            targets = [base_path]
    return targets

def worker_dolphin_verify(base_path: Path, args: Any, log_cb: Callable[[str], None], list_files_fn: Callable[[Path], list[Path]]) -> str:
    """Worker function for GameCube/Wii verification."""
    logger = GuiLogger(log_cb)
    
    targets = _resolve_dolphin_targets(base_path)
    if not targets:
        return MSG_NO_GC_WII

    converter = DolphinConverter()
    if not converter.check_tool():
        return "Error: 'dolphin-tool' not found. Please install Dolphin Emulator."

    passed = 0
    failed = 0
    
    all_files = _collect_dolphin_files(targets, list_files_fn, logger)
        
    total_files = len(all_files)
    progress_cb = getattr(args, "progress_callback", None)
    cancel_event = getattr(args, "cancel_event", None)
    deep_verify = getattr(args, "deep_verify", False)
    
    # Setup result collector
    results_list = getattr(args, "results", None)
    per_file_cb = make_result_collector(results_list, getattr(args, "on_result", None))
    
    for i, (f, target_dir) in enumerate(all_files):
        if cancel_event and cancel_event.is_set():
            logger.warning(MSG_CANCELLED)
            break
            
        # Calculate progress range for this file
        start_prog = i / total_files
        file_weight = 1.0 / total_files
        
        file_prog_cb = create_file_progress_cb(progress_cb, start_prog, file_weight, f.name)
            
        if progress_cb:
            progress_cb(start_prog, f"Verifying {f.name}...")
            
        if _verify_dolphin_file(f, converter, target_dir, logger, deep_verify=deep_verify, progress_cb=file_prog_cb, per_file_cb=per_file_cb):
            passed += 1
        else:
            failed += 1
            
    if progress_cb:
        progress_cb(1.0, "Dolphin Verification complete")
                
    return f"Verification complete. Passed: {passed}, Failed: {failed}"

def _detect_dolphin_platform(f: Path) -> Optional[str]:
    """Returns 'gamecube', 'wii', or None."""
    try:
        with open(f, "rb") as stream:
            header = stream.read(0x20)
            if len(header) < 0x20:
                return None
            
            # Check Wii Magic at 0x18
            if header[0x18:0x1C] == b'\x5D\x1C\x9E\xA3':
                return "wii"
            
            # Check GC Magic at 0x1C
            if header[0x1C:0x20] == b'\xC2\x33\x9F\x3D':
                return "gamecube"
    except Exception:
        pass
    return None

def _get_dolphin_metadata(f: Path, target_dir: Path) -> tuple[dict, Optional[str]]:
    is_gc = "gamecube" in str(target_dir).lower()
    is_wii = "wii" in str(target_dir).lower()
    
    if not is_gc and not is_wii:
        platform = _detect_dolphin_platform(f)
        is_gc = (platform == "gamecube")
        is_wii = (platform == "wii")

    meta = {}
    if is_gc:
        meta = gc_meta.get_metadata(f)
    elif is_wii:
        meta = wii_meta.get_metadata(f)
    else:
        meta = wii_meta.get_metadata(f) or gc_meta.get_metadata(f)
            
    game_id = meta.get("game_id")
    if not game_id:
        return meta, None

    db_title = None
    if is_gc:
        db_title = gc_db.db.get_title(game_id)
    elif is_wii:
        db_title = wii_db.db.get_title(game_id)
    else:
        db_title = gc_db.db.get_title(game_id) or wii_db.db.get_title(game_id)
            
    return meta, db_title

def _organize_dolphin_file(f: Path, target_dir: Path, dry_run: bool, logger: GuiLogger) -> str:
    """Returns 'renamed', 'skipped', or 'error'."""
    try:
        # Get metadata
        meta, db_title = _get_dolphin_metadata(f, target_dir)
        
        game_id = meta.get("game_id")
        internal_title = meta.get("internal_name")
        
        if not game_id:
            logger.warning(f"Skipping {f.name}: Could not determine Game ID")
            return "skipped"
            
        title = db_title if db_title else internal_title
        
        # Sanitize title
        clean_title = title if title else "Unknown"
        clean_title = re.sub(r'[<>:"/\\|?*]', '', clean_title).strip()
        
        # Standardize check (Dolphin metadata might have region/country code)
        # For now we stick to Title [GameID] as it is robust
        new_name = f"{clean_title} [{game_id}]{f.suffix}"
        new_path = f.parent / new_name
        
        if f.name == new_name:
            return "skipped"
            
        if new_path.exists():
            logger.warning(f"Skipping {f.name}: Target {new_name} already exists")
            return "skipped"
            
        logger.info(f"Renaming: {f.name} -> {new_name}")
        if not dry_run:
            f.rename(new_path)
        return "renamed"
        
    except Exception as e:
        logger.error(f"Error processing {f.name}: {e}")
        return "error"

def _load_dolphin_databases(base_path: Path, logger: GuiLogger):
    gc_csv = base_path / "gamecube_db.csv"
    if gc_csv.exists():
        gc_db.db.load_from_csv(gc_csv)
        logger.info(f"Loaded GameCube database from {gc_csv}")
        
    wii_csv = base_path / "wii_db.csv"
    if wii_csv.exists():
        wii_db.db.load_from_csv(wii_csv)
        logger.info(f"Loaded Wii database from {wii_csv}")

def worker_dolphin_organize(base_path: Path, args: Any, log_cb: Callable[[str], None], list_files_fn: Callable[[Path], list[Path]]) -> str:
    """Worker function for GameCube/Wii organization (renaming)."""
    logger = GuiLogger(log_cb)
    
    targets = _resolve_dolphin_targets(base_path)

    _load_dolphin_databases(base_path, logger)

    renamed = 0
    skipped = 0
    errors = 0
    
    # Collect all files with their target dir
    all_files = []
    for target_dir in targets:
        files = list_files_fn(target_dir)
        all_files.extend([(f, target_dir) for f in files])
        
    total_files = len(all_files)
    progress_cb = getattr(args, "progress_callback", None)
    cancel_event = getattr(args, "cancel_event", None)
    dry_run = getattr(args, "dry_run", False)
    
    for i, (f, target_dir) in enumerate(all_files):
        if cancel_event and cancel_event.is_set():
            logger.warning(MSG_CANCELLED)
            break
            
        if progress_cb:
            progress_cb(i / total_files if total_files > 0 else 0, f"Processing {f.name}...")
            
        status = _organize_dolphin_file(f, target_dir, dry_run, logger)
        if status == "renamed":
            renamed += 1
        elif status == "skipped":
            skipped += 1
        elif status == "error":
            errors += 1
            
    if progress_cb:
        progress_cb(1.0, "Dolphin Organization complete")
                
    return f"Organization complete. Renamed: {renamed}, Skipped: {skipped}, Errors: {errors}"
