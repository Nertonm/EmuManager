from __future__ import annotations
from pathlib import Path
from typing import Any, Callable, Optional
import re
from tempfile import TemporaryDirectory

from emumanager.switch.main_helpers import process_files, run_health_check
from emumanager.switch import metadata, meta_extractor, compression
from emumanager.switch.cli import verify_integrity, scan_for_virus, safe_move
from emumanager.common.execution import run_cmd
from emumanager.workers.common import GuiLogger, MSG_CANCELLED

MSG_NSZ_MISSING = "Error: 'nsz' tool not found."

def worker_organize(base_path: Path, env: dict, args: Any, log_cb: Callable[[str], None], list_files_fn: Callable[[Path], list[Path]], progress_cb: Optional[Callable[[float, str], None]] = None) -> str:
    """Worker function for organizing Switch ROMs."""
    logger = GuiLogger(log_cb)
    
    files = list_files_fn(base_path)
    if not files:
        return "No files found to organize."

    # Context construction
    ctx = {}
    ctx["args"] = args
    ctx["ROMS_DIR"] = env["ROMS_DIR"]
    ctx["CSV_FILE"] = env["CSV_FILE"]
    ctx["logger"] = logger
    ctx["progress_callback"] = progress_cb
    ctx["cancel_event"] = getattr(args, "cancel_event", None)
    
    # Functions
    ctx["get_metadata"] = lambda f: meta_extractor.get_metadata(
        f, 
        tool_metadata=env.get("TOOL_METADATA"), 
        is_nstool=env.get("IS_NSTOOL"), 
        keys_path=env.get("KEYS_PATH"), 
        logger=logger
    )
    ctx["sanitize_name"] = metadata.sanitize_name
    ctx["determine_region"] = metadata.determine_region
    ctx["determine_type"] = metadata.determine_type
    ctx["parse_languages"] = metadata.parse_languages
    ctx["detect_languages_from_filename"] = metadata.detect_languages_from_filename
    
    ctx["safe_move"] = lambda s, d: safe_move(s, d, args=args, logger=logger)
    
    ctx["verify_integrity"] = lambda f, deep=False, return_output=False: verify_integrity(
        f, 
        deep=deep, 
        tool_nsz=env.get("TOOL_NSZ"), 
        roms_dir=env["ROMS_DIR"], 
        cmd_timeout=None, 
        tool_metadata=env.get("TOOL_METADATA"), 
        is_nstool=env.get("IS_NSTOOL"), 
        keys_path=env.get("KEYS_PATH"), 
        tool_hactool=env.get("TOOL_HACTOOL"),
        return_output=return_output
    )
    
    ctx["scan_for_virus"] = lambda f: scan_for_virus(
        f, 
        tool_clamscan=env.get("TOOL_CLAMSCAN"), 
        tool_clamdscan=env.get("TOOL_CLAMDSCAN"),
        roms_dir=env["ROMS_DIR"],
        cmd_timeout=None
    )

    def handle_compression(fpath):
        return fpath
    
    ctx["handle_compression"] = handle_compression
    
    ctx["TOOL_METADATA"] = env.get("TOOL_METADATA")
    ctx["IS_NSTOOL"] = env.get("IS_NSTOOL")
    ctx["TITLE_ID_RE"] = re.compile(r"\[([0-9A-Fa-f]{16})\]")
    
    class Col:
        RESET = ""
        RED = ""
        GREEN = ""
        YELLOW = ""
        BLUE = ""
        MAGENTA = ""
        CYAN = ""
        GREY = ""
        BOLD = ""
    ctx["Col"] = Col

    _catalog, stats = process_files(files, ctx)
    return f"Organization complete. Stats: {stats}"


def worker_health_check(base_path: Path, env: dict, args: Any, log_cb: Callable[[str], None], list_files_fn: Callable[[Path], list[Path]]) -> str:
    """Worker function for health check."""
    logger = GuiLogger(log_cb)
    files = list_files_fn(base_path)
    
    def verify_fn(f, deep=False, return_output=False):
        return verify_integrity(
            f, 
            deep=deep, 
            tool_nsz=env.get("TOOL_NSZ"), 
            roms_dir=env["ROMS_DIR"], 
            cmd_timeout=None, 
            tool_metadata=env.get("TOOL_METADATA"), 
            is_nstool=env.get("IS_NSTOOL"), 
            keys_path=env.get("KEYS_PATH"), 
            tool_hactool=env.get("TOOL_HACTOOL"),
            return_output=return_output
        )
    
    def scan_fn(f):
        return scan_for_virus(
            f, 
            tool_clamscan=env.get("TOOL_CLAMSCAN"), 
            tool_clamdscan=env.get("TOOL_CLAMDSCAN"),
            roms_dir=env["ROMS_DIR"],
            cmd_timeout=None
        )
    
    def safe_move_fn(s, d):
        return safe_move(s, d, args=args, logger=logger)

    summary = run_health_check(files, args, env["ROMS_DIR"], verify_fn, scan_fn, safe_move_fn, logger)
    return f"Health Check complete. Corrupted: {len(summary['corrupted'])}, Infected: {len(summary['infected'])}"

def worker_switch_compress(base_path: Path, env: dict, args: Any, log_cb: Callable[[str], None], list_files_fn: Callable[[Path], list[Path]]) -> str:
    """Worker function for bulk Switch compression."""
    logger = GuiLogger(log_cb)
    files = list_files_fn(base_path)
    
    # Filter for compressible files (NSP, XCI)
    candidates = [f for f in files if f.suffix.lower() in {".nsp", ".xci"}]
    if not candidates:
        return "No compressible files found (NSP/XCI)."
        
    logger.info(f"Found {len(candidates)} files to compress.")
    
    success = 0
    failed = 0
    skipped = 0
    
    total = len(candidates)
    progress_cb = getattr(args, "progress_callback", None)
    cancel_event = getattr(args, "cancel_event", None)
    
    tool_nsz = env.get("TOOL_NSZ")
    if not tool_nsz:
        return MSG_NSZ_MISSING

    def run_wrapper(cmd, **kwargs):
        return run_cmd(cmd, filebase=None, timeout=None, check=kwargs.get("check", False))

    for i, f in enumerate(candidates):
        if cancel_event and cancel_event.is_set():
            logger.warning(MSG_CANCELLED)
            break
            
        if progress_cb:
            progress_cb(i / total, f"Compressing {f.name}...")
            
        status = _compress_single_file(f, str(tool_nsz), env, args, run_wrapper, logger)
        if status == "success":
            success += 1
        elif status == "skipped":
            skipped += 1
        elif status == "failed":
            failed += 1
            
    if progress_cb:
        progress_cb(1.0, "Compression complete")
        
    return f"Compression complete. Success: {success}, Failed: {failed}, Skipped: {skipped}"

def _compress_single_file(f: Path, tool_nsz: str, env: dict, args: Any, run_wrapper: Callable, logger: GuiLogger) -> str:
    # Check if NSZ already exists
    nsz_path = f.with_suffix(".nsz")
    if nsz_path.exists():
        logger.info(f"Skipping {f.name}, NSZ already exists.")
        return "skipped"
        
    # Compress
    res = compression.compress_file(
        f, 
        run_wrapper, 
        tool_nsz=tool_nsz, 
        level=getattr(args, "level", 3), 
        args=args, 
        roms_dir=env["ROMS_DIR"]
    )
    
    if res:
        logger.info(f"Compressed: {f.name} -> {res.name}")
        # Remove original if requested
        if getattr(args, "rm_originals", False) and res != f:
            try:
                if not getattr(args, "dry_run", False):
                    from emumanager.common.fileops import safe_unlink

                    safe_unlink(f, logger)
            except Exception as e:
                logger.error(f"Failed to remove original {f.name}: {e}")
        return "success"
    else:
        logger.error(f"Failed to compress: {f.name}")
        return "failed"


def worker_switch_decompress(base_path: Path, env: dict, args: Any, log_cb: Callable[[str], None], list_files_fn: Callable[[Path], list[Path]]) -> str:
    """Worker function for bulk Switch decompression."""
    logger = GuiLogger(log_cb)
    files = list_files_fn(base_path)
    
    # Filter for decompressible files (NSZ, XCZ)
    candidates = [f for f in files if f.suffix.lower() in {".nsz", ".xcz"}]
    if not candidates:
        return "No decompressible files found (NSZ/XCZ)."
        
    logger.info(f"Found {len(candidates)} files to decompress.")
    
    success = 0
    failed = 0
    
    total = len(candidates)
    progress_cb = getattr(args, "progress_callback", None)
    cancel_event = getattr(args, "cancel_event", None)
    
    tool_nsz = env.get("TOOL_NSZ")
    if not tool_nsz:
        return MSG_NSZ_MISSING

    def run_wrapper(cmd, **kwargs):
        return run_cmd(cmd, filebase=None, timeout=None)

    for i, f in enumerate(candidates):
        if cancel_event and cancel_event.is_set():
            logger.warning(MSG_CANCELLED)
            break
            
        if progress_cb:
            progress_cb(i / total, f"Decompressing {f.name}...")
            
        # Decompress
        res = compression.decompress_and_find_candidate(
            f, 
            run_wrapper, 
            tool_nsz=str(tool_nsz), 
            tool_metadata=str(env.get("TOOL_METADATA")) if env.get("TOOL_METADATA") else None, 
            is_nstool=env.get("IS_NSTOOL", False), 
            keys_path=env.get("KEYS_PATH"), 
            args=args, 
            roms_dir=env["ROMS_DIR"]
        )
        
        if res:
            success += 1
            logger.info(f"Decompressed: {f.name} -> {res.name}")
            # Original removal is handled inside decompress_and_find_candidate if successful
        else:
            failed += 1
            logger.error(f"Failed to decompress: {f.name}")
            
    if progress_cb:
        progress_cb(1.0, "Decompression complete")
        
    return f"Decompression complete. Success: {success}, Failed: {failed}"

def worker_recompress_single(filepath: Path, env: dict, args: Any, log_cb: Callable[[str], None]) -> Optional[Path]:
    """Worker function for recompressing a single Switch file."""
    logger = GuiLogger(log_cb)
    
    tool_nsz = env.get("TOOL_NSZ")
    if not tool_nsz:
        logger.error(MSG_NSZ_MISSING)
        return None

    def run_wrapper(cmd, **kwargs):
        return run_cmd(cmd, filebase=None, timeout=None)

    with TemporaryDirectory(prefix="nsz_recomp_") as td:
        tmpdir = Path(td)
        level = getattr(args, "level", 3)
        attempts = [
            [str(tool_nsz), "-C", "-l", str(level), "-o", str(tmpdir), str(filepath)],
            [str(tool_nsz), "-C", "-l", str(level), str(filepath), "-o", str(tmpdir)],
            [str(tool_nsz), "-C", "-l", str(level), str(filepath)],
        ]

        produced = compression.try_multiple_recompress_attempts(
            tmpdir, 
            attempts, 
            run_wrapper, 
            timeout=None, 
            progress_callback=getattr(args, "progress_callback", None)
        )

        if produced:
            new_file = produced[0]
            try:
                def verify_fn(p, rc):
                    return verify_integrity(
                        p,
                        deep=False,
                        tool_nsz=env.get("TOOL_NSZ"),
                        roms_dir=env["ROMS_DIR"],
                        cmd_timeout=None,
                        tool_metadata=env.get("TOOL_METADATA"),
                        is_nstool=env.get("IS_NSTOOL"),
                        keys_path=env.get("KEYS_PATH"),
                        tool_hactool=env.get("TOOL_HACTOOL")
                    )

                result_path = compression.handle_produced_file(
                    new_file,
                    filepath,
                    run_wrapper,
                    verify_fn=verify_fn,
                    args=args,
                    roms_dir=env["ROMS_DIR"]
                )
                return result_path
            except Exception as e:
                logger.error(f"Recompression failed during verification/move: {e}")
                return None
    return None


def worker_decompress_single(filepath: Path, env: dict, args: Any, log_cb: Callable[[str], None]) -> Optional[Path]:
    """Worker function for decompressing a single Switch file."""
    logger = GuiLogger(log_cb)

    tool_nsz = env.get("TOOL_NSZ")
    if not tool_nsz:
        logger.error(MSG_NSZ_MISSING)
        return None

    def run_wrapper(cmd, **kwargs):
        return run_cmd(cmd, filebase=None, timeout=None)

    res = compression.decompress_and_find_candidate(
        filepath,
        run_wrapper,
        tool_nsz=str(tool_nsz),
        tool_metadata=str(env.get("TOOL_METADATA")) if env.get("TOOL_METADATA") else None,
        is_nstool=env.get("IS_NSTOOL", False),
        keys_path=env.get("KEYS_PATH"),
        args=args,
        roms_dir=env["ROMS_DIR"]
    )

    if res:
        logger.info(f"Decompressed: {filepath.name} -> {res.name}")
        return res
    else:
        logger.error(f"Failed to decompress: {filepath.name}")
        return None


def worker_compress_single(filepath: Path, env: dict, args: Any, log_cb: Callable[[str], None]) -> Optional[Path]:
    """Worker function for compressing a single Switch file."""
    logger = GuiLogger(log_cb)

    tool_nsz = env.get("TOOL_NSZ")
    if not tool_nsz:
        logger.error(MSG_NSZ_MISSING)
        return None

    def run_wrapper(cmd, **kwargs):
        return run_cmd(cmd, filebase=None, timeout=None, check=kwargs.get("check", False))

    # Ensure args has necessary attributes
    if not hasattr(args, "level"):
        args.level = 3
    if not hasattr(args, "rm_originals"):
        args.rm_originals = False

    res = compression.compress_file(
        filepath,
        run_wrapper,
        tool_nsz=str(tool_nsz),
        level=args.level,
        args=args,
        roms_dir=env["ROMS_DIR"]
    )

    if res:
        logger.info(f"Compressed: {filepath.name} -> {res.name}")
        return res
    else:
        logger.error(f"Failed to compress {filepath.name}")
        return None
