from __future__ import annotations
from pathlib import Path
from typing import Any, Callable, Optional
import logging
import re

from emumanager.converters import ps2_converter
from emumanager.common.execution import find_tool
from emumanager.ps2 import metadata as ps2_meta
from emumanager.ps2 import database as ps2_db
from emumanager.workers.common import GuiLogger, GuiLogHandler, MSG_CANCELLED, find_target_dir, calculate_file_hash, create_file_progress_cb

MSG_PS2_DIR_NOT_FOUND = "PS2 ROMs directory not found."
PS2_SUBDIRS = ["roms/ps2", "ps2"]

def worker_ps2_convert(base_path: Path, args: Any, log_cb: Callable[[str], None]) -> str:
    """Worker function for PS2 CSO -> CHD conversion."""
    logger = GuiLogger(log_cb)
    
    target_dir = find_target_dir(base_path, PS2_SUBDIRS)
    if not target_dir:
        return MSG_PS2_DIR_NOT_FOUND
        
    logger.info(f"Starting PS2 conversion in: {target_dir}")
    
    # We need to find tools manually or assume they are in path
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
            progress_callback=getattr(args, "progress_callback", None)
        )
        
        converted = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)
        
        return f"PS2 Conversion complete. Converted: {converted}, Failed: {failed}"
    except Exception as e:
        return f"PS2 Conversion failed: {e}"
    finally:
        ps2_logger.removeHandler(handler)

def _process_ps2_file(f: Path, logger: GuiLogger, deep_verify: bool = False, progress_cb: Optional[Callable[[float], None]] = None) -> str:
    """
    Process a single PS2 file to extract serial and identify title.
    Returns: 'found', 'unknown', or 'skip'.
    """
    suffix = f.suffix.lower()
    if suffix not in {".iso", ".bin", ".cso", ".chd", ".gz"}:
        return "skip"
        
    if suffix == ".cso":
        logger.warning(f"[SKIP] Cannot extract serial from compressed file: {f.name}")
        return "unknown"

    serial = ps2_meta.get_ps2_serial(f)
    info_str = ""
    
    if serial:
        title = ps2_db.db.get_title(serial)
        if title:
            info_str = f"[{serial}] {title}"
        else:
            info_str = f"[{serial}] Unknown Title"
    else:
        info_str = "[NO SERIAL] Could not identify"

    if deep_verify:
        logger.info(f"Hashing {f.name}...")
        md5 = calculate_file_hash(f, "md5", progress_cb=progress_cb)
        info_str += f" | MD5: {md5}"
        
    logger.info(f"{info_str} -> {f.name}")
    
    return "found" if serial else "unknown"

def worker_ps2_verify(base_path: Path, args: Any, log_cb: Callable[[str], None], list_files_fn: Callable[[Path], list[Path]]) -> str:
    """Worker function for PS2 verification (Serial extraction)."""
    logger = GuiLogger(log_cb)
    
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
    
    for i, f in enumerate(files):
        if cancel_event and cancel_event.is_set():
            logger.warning(MSG_CANCELLED)
            break
            
        # Calculate progress range for this file
        start_prog = i / total_files
        file_weight = 1.0 / total_files
        
        file_prog_cb = create_file_progress_cb(progress_cb, start_prog, file_weight, f.name)
            
        if progress_cb:
            progress_cb(start_prog, f"Verifying {f.name}...")
            
        res = _process_ps2_file(f, logger, deep_verify=deep_verify, progress_cb=file_prog_cb)
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
        
    serial = ps2_meta.get_ps2_serial(f)
    if not serial:
        logger.warning(f"Could not extract serial from {f.name}")
        return False
        
    title = ps2_db.db.get_title(serial)
    if not title:
        logger.warning(f"Serial {serial} not found in database for {f.name}")
        return False
        
    # Sanitize title
    safe_title = re.sub(r'[<>:"/\\|?*]', '', title).strip()
    
    # PS2 doesn't have region in metadata easily available yet, but we can keep the format consistent
    # Standard: "Title [Serial]"
    new_name = f"{safe_title} [{serial}]{f.suffix}"
    
    new_path = f.parent / new_name
    
    if f.name == new_name:
        return False
        
    if new_path.exists():
        logger.warning(f"Target file already exists: {new_name}")
        return False
        
    try:
        if not args.dry_run:
            f.rename(new_path)
        logger.info(f"Renamed: {f.name} -> {new_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to rename {f.name}: {e}")
        return False

def worker_ps2_organize(base_path: Path, args: Any, log_cb: Callable[[str], None], list_files_fn: Callable[[Path], list[Path]]) -> str:
    """Worker function for PS2 organization (Rename based on DB)."""
    logger = GuiLogger(log_cb)
    
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
            
        if _organize_ps2_file(f, args, logger):
            renamed += 1
        else:
            skipped += 1
            
    if progress_cb:
        progress_cb(1.0, "PS2 Organization complete")
            
    return f"PS2 Organization complete. Renamed: {renamed}, Skipped: {skipped}"
