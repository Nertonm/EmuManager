from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from emumanager.common.models import VerifyReport, VerifyResult
from emumanager.verification import dat_parser, hasher
from emumanager.workers.common import (
    MSG_CANCELLED,
    GuiLogger,
    create_file_progress_cb,
)


def worker_hash_verify(
    base_path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    list_files_fn: Callable[[Path], list[Path]],
) -> VerifyReport:
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

        res = _verify_single_file(f, db, args, progress_cb, start_prog, file_weight)

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
        f"Unknown: {unknown}, Mismatch: {mismatch}"
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
    f: Path, db, args, progress_cb, start_prog, file_weight
) -> VerifyResult:
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
        full_path=str(f),
    )

    if match:
        res.status = "VERIFIED"
        res.match_name = match.game_name
        return res

    mismatch_reason = _check_mismatch(db, crc, md5, sha1)
    if mismatch_reason:
        res.status = "MISMATCH"
        res.match_name = mismatch_reason
        return res

    return res


def worker_identify_single_file(
    file_path: Path,
    dat_path: Path,
    log_cb: Callable[[str], None],
    progress_cb: Optional[Callable[[float], None]] = None,
) -> str:
    """Identify a single file against a DAT database."""
    logger = GuiLogger(log_cb)

    if not dat_path.exists():
        return "Error: DAT file not found."

    logger.info(f"Parsing DAT file: {dat_path}...")
    try:
        db = dat_parser.parse_dat_file(dat_path)
    except Exception as e:
        return f"Error parsing DAT: {e}"

    logger.info(f"Calculating hashes for {file_path.name}...")
    hashes = hasher.calculate_hashes(
        file_path, algorithms=("crc32", "md5", "sha1"), progress_cb=progress_cb
    )

    crc = hashes.get("crc32")
    md5 = hashes.get("md5")
    sha1 = hashes.get("sha1")

    logger.info(f"Hashes: CRC={crc}, MD5={md5}, SHA1={sha1}")

    match = db.lookup(crc=crc, md5=md5, sha1=sha1)

    if match:
        return (
            f"MATCH FOUND!\n"
            f"Game: {match.game_name}\n"
            f"ROM:  {match.rom_name}\n"
            f"Size: {match.size} bytes"
        )
    else:
        return "No match found in database."
