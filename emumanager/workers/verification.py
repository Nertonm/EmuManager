from __future__ import annotations
from pathlib import Path
from typing import Any, Callable, List, Optional
from dataclasses import dataclass, field

from emumanager.verification import dat_parser, hasher
from emumanager.workers.common import GuiLogger, MSG_CANCELLED, create_file_progress_cb
from emumanager.common.models import VerifyResult, VerifyReport

def worker_hash_verify(base_path: Path, args: Any, log_cb: Callable[[str], None], list_files_fn: Callable[[Path], list[Path]]) -> VerifyReport:
    """Worker function for DAT-based hash verification."""
    logger = GuiLogger(log_cb)
    report = VerifyReport(text="")
    
    dat_path = getattr(args, "dat_path", None)
    if not dat_path or not Path(dat_path).exists():
        report.text = "Error: No valid DAT file selected."
        return report
        
    logger.info(f"Parsing DAT file: {dat_path}...")
    try:
        db = dat_parser.parse_dat_file(Path(dat_path))
        logger.info(f"DAT Loaded: {db.name} ({db.version})")
    except Exception as e:
        report.text = f"Error parsing DAT: {e}"
        return report
        
    files = list_files_fn(base_path)
    if not files:
        report.text = "No files found to verify."
        return report
        
    logger.info(f"Verifying {len(files)} files against DAT...")
    
    verified = 0
    unknown = 0
    mismatch = 0
    
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
        
        file_prog_cb = create_file_progress_cb(progress_cb, start_prog, file_weight, f.name)
            
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

        match = db.lookup(crc=crc, md5=md5, sha1=sha1)

        res = VerifyResult(
            filename=f.name,
            status="UNKNOWN",
            match_name=None,
            crc=crc,
            sha1=sha1,
            md5=md5,
            sha256=sha256,
            full_path=str(f)
        )

        if match:
            verified += 1
            res.status = "VERIFIED"
            res.match_name = match.game_name
            logger.info(f"✅ VERIFIED: {f.name} -> {match.game_name}")
        else:
            # If CRC matches any entry but MD5/SHA1 do not, mark as MISMATCH
            crc_candidates = []
            try:
                if crc and hasattr(db, "crc_index") and isinstance(db.crc_index, dict):
                    cand = db.crc_index.get(crc.lower(), [])
                    # Ensure it's a list of RomInfo-like objects
                    if isinstance(cand, list) and len(cand) > 0:
                        crc_candidates = cand
            except Exception:
                crc_candidates = []
            if crc_candidates and (md5 or sha1):
                match_any = False
                for cand in crc_candidates:
                    if (sha1 and cand.sha1 and cand.sha1.lower() == sha1.lower()) or (
                        md5 and cand.md5 and cand.md5.lower() == md5.lower()
                    ):
                        match_any = True
                        break
                if not match_any:
                    mismatch += 1
                    res.status = "MISMATCH"
                    # Use the first candidate's name as expected
                    try:
                        res.match_name = crc_candidates[0].game_name
                    except Exception:
                        res.match_name = None
                    logger.warning(f"⚠️ MISMATCH: {f.name} (CRC matched, but other hashes differ)")
                else:
                    unknown += 1
                    res.status = "UNKNOWN"
                    logger.warning(f"❌ UNKNOWN: {f.name} (CRC: {crc}, SHA1: {sha1}, MD5: {md5})")
            else:
                unknown += 1
                res.status = "UNKNOWN"
                logger.warning(f"❌ UNKNOWN: {f.name} (CRC: {crc}, SHA1: {sha1}, MD5: {md5})")
        
        report.results.append(res)
            
    if progress_cb:
        progress_cb(1.0, "Verification complete")
        
    report.text = f"Verification complete. Verified: {verified}, Unknown: {unknown}, Mismatch: {mismatch}"
    return report
