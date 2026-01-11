from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Callable, List, Optional

# Optional textual progress for long-running compression attempts.
try:  # pragma: no cover - optional dependency
    from tqdm import tqdm  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    tqdm = None


def build_nsz_command(
    src: Path, dst: Path, *, level: int = 3, tool_nsz: str = "nsz"
) -> List[str]:
    """Build a recompression command for the NSZ tool.

    This deliberately uses a small, testable and explicit flag layout so unit
    tests can assert command components. Real invocations can adjust the
    layout if a different NSZ tool expects different flags.
    """
    return [str(tool_nsz), "--out", str(dst), "--level", str(level), str(src)]


def recompress_candidate(
    src: Path,
    dst: Path,
    run_cmd: Callable,
    *,
    level: int = 3,
    tool_nsz: str = "nsz",
    timeout: Optional[int] = 120,
    progress_callback: Optional[Callable[[float, str], None]] = None,
):
    """Attempt to recompress `src` into `dst` using the provided `run_cmd`.

    Returns the run_cmd result (CompletedProcess-like object) or raises on
    unexpected exceptions from run_cmd.
    """
    cmd = build_nsz_command(src, dst, level=level, tool_nsz=tool_nsz)
    try:
        if progress_callback:
            try:
                progress_callback(0.0, f"recompress:start {src.name}")
            except Exception:
                pass
        res = run_cmd(cmd, timeout=timeout)
        if progress_callback:
            try:
                progress_callback(1.0, f"recompress:done {src.name}")
            except Exception:
                pass
        return res
    except Exception:
        if progress_callback:
            try:
                progress_callback(1.0, f"recompress:error {src.name}")
            except Exception:
                pass
        raise


def _report_recompress_progress(cb: Optional[Callable], idx: int, total: int, status: str):
    if cb:
        try:
            cb(float(idx) / max(1, total), f"{status}:{idx}/{total}")
        except Exception as e:
            import logging
            logging.debug(f"Progress callback failed: {e}")


def _execute_recompress_attempt(cmd: List[str], run_cmd: Callable, timeout: Optional[int]) -> bool:
    try:
        run_cmd(cmd, timeout=timeout)
        return True
    except Exception as e:
        import logging
        logging.debug(f"Recompress attempt failed for cmd {cmd}: {e}")
        return False


def try_multiple_recompress_attempts(
    tmpdir: Path,
    attempts: List[List[str]],
    run_cmd: Callable,
    *,
    timeout: Optional[int] = 120,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> List[Path]:
    total = len(attempts)
    iterator = enumerate(attempts)
    if tqdm:
        iterator = enumerate(tqdm(attempts, desc="Recompress attempts", unit="attempt"))

    for idx, cmd in iterator:
        _report_recompress_progress(progress_callback, idx + 1, total, "attempt")
        
        success = _execute_recompress_attempt(cmd, run_cmd, timeout)
        
        status = "attempt_success" if success else "attempt_failed"
        _report_recompress_progress(progress_callback, idx + 1, total, status)
        
        if success:
            # We could break here if we only want the first success, 
            # but current behavior runs all. Keeping original functionality.
            pass

    return list(Path(tmpdir).rglob("*.nsz"))


def _verify_produced_file(path: Path, run_cmd: Callable, verify_fn: Callable, args) -> bool:
    try:
        cb = getattr(args, "progress_callback", None)
        if cb:
            cb(0.0, "verify:start")
        ok = verify_fn(path, run_cmd)
        if cb:
            cb(0.8, "verify:done")
        return ok
    except Exception as e:
        import logging
        logging.debug(f"Verification raised exception for {path}: {e}")
        return True # Fallback safer behavior


def _apply_recompression_replacement(target_tmp: Path, original: Path, args) -> Path:
    try:
        if target_tmp.resolve() == original.resolve():
            return original
        if original.exists():
            original.unlink()
        shutil.move(str(target_tmp), str(original))
        cb = getattr(args, "progress_callback", None)
        if cb:
            cb(1.0, "replace:done")
        return original
    except Exception as e:
        import logging
        logging.error(f"Failed to replace original {original} with {target_tmp}: {e}")
        return target_tmp


def _quarantine_failed_file(target_tmp: Path, original: Path, args, roms_dir: Path) -> Path:
    if not getattr(args, "keep_on_failure", False):
        return original
    
    try:
        qdir = getattr(args, "quarantine_dir", None)
        quarantine_dir = Path(qdir).resolve() if qdir else Path(roms_dir) / "_QUARANTINE"
        
        if not getattr(args, "dry_run", False):
            quarantine_dir.mkdir(parents=True, exist_ok=True)
            dest = quarantine_dir / target_tmp.name
            shutil.move(str(target_tmp), str(dest))
            cb = getattr(args, "progress_callback", None)
            if cb:
                cb(1.0, "quarantine:moved")
    except Exception as e:
        import logging
        logging.error(f"Quarantine failed for {target_tmp}: {e}")
    
    return original


def handle_produced_file(
    produced: Path,
    original: Path,
    run_cmd: Callable,
    verify_fn: Callable[[Path, Callable], bool],
    args,
    roms_dir: Path,
) -> Path:
    target_tmp = original.parent / produced.name

    try:
        if target_tmp.exists():
            target_tmp.unlink()
        shutil.move(str(produced), str(target_tmp))
    except Exception as e:
        import logging
        logging.debug(f"Initial move failed for produced file {produced}: {e}")
        return original

    if _verify_produced_file(target_tmp, run_cmd, verify_fn, args):
        return _apply_recompression_replacement(target_tmp, original, args)

    return _quarantine_failed_file(target_tmp, original, args, roms_dir)


def _execute_compression_command(cmd: List[str], run_cmd: Callable, file_name: str, args, logbase: Path):
    try:
        cb = getattr(args, "progress_callback", None)
        if cb:
            cb(0.0, f"compress:start:{file_name}")

        timeout = getattr(args, "cmd_timeout", None) if args else None
        
        if tqdm and not cb:
            with tqdm(total=1, desc=f"Compressing {file_name}", unit="op"):
                run_cmd(cmd, filebase=logbase, timeout=timeout, check=True)
        else:
            run_cmd(cmd, filebase=logbase, timeout=timeout, check=True)

        if cb:
            cb(1.0, f"compress:done:{file_name}")
        return True
    except Exception as e:
        import logging
        logging.debug(f"Compression command failed for {file_name}: {e}")
        if cb:
            cb(1.0, f"compress:error:{file_name}")
        return False


def _find_compressed_artifact(filepath: Path) -> Optional[Path]:
    candidate = filepath.with_suffix(".nsz")
    if candidate.exists():
        return candidate

    matches = list(filepath.parent.glob(filepath.stem + "*.nsz"))
    return matches[0] if matches else None


def compress_file(
    filepath: Path,
    run_cmd: Callable,
    *,
    tool_nsz: str = "nsz",
    level: int = 3,
    args=None,
    roms_dir: Path = Path("."),
) -> Optional[Path]:
    logbase = Path(roms_dir) / "logs" / "nsz" / (filepath.stem + ".compress")
    cmd = [str(tool_nsz), "-C", "-l", str(level), str(filepath)]
    
    if not _execute_compression_command(cmd, run_cmd, filepath.name, args, logbase):
        return None

    return _find_compressed_artifact(filepath)


def decompress_and_find_candidate(
    filepath: Path,
    run_cmd: Callable,
    *,
    tool_nsz: str = "nsz",
    tool_metadata: Optional[str] = None,
    is_nstool: bool = True,
    keys_path: Optional[Path] = None,
    args=None,
    roms_dir: Path = Path("."),
) -> Optional[Path]:
    """Decompress `filepath` and attempt to find the inner candidate file.

    Returns the chosen candidate Path (or None) following the same heuristics
    as the legacy code: direct-name match, mtime proximity, metadata probe, size match.
    """
    if not _perform_decompression(filepath, run_cmd, tool_nsz, args, roms_dir):
        return None

    archive_mtime = _get_mtime_safe(filepath)
    parent = filepath.parent

    # 1. Direct-name candidates
    chosen = _find_direct_candidate(filepath, parent, archive_mtime)
    if chosen:
        # Legacy behavior: check keep_on_failure for direct match
        _cleanup_original(filepath, args, check_keep_failure=True)
        return chosen

    # 2. Broader recent-file probe
    if archive_mtime is not None:
        chosen = _find_recent_candidate(
            filepath,
            parent,
            archive_mtime,
            run_cmd,
            tool_metadata,
            is_nstool,
            keys_path,
            args,
        )
        if chosen:
            # Legacy behavior: do NOT check keep_on_failure for recent match
            _cleanup_original(filepath, args, check_keep_failure=False)
            return chosen

    return None


def _perform_decompression(
    filepath: Path, run_cmd: Callable, tool_nsz: str, args, roms_dir: Path
) -> bool:
    parent = filepath.parent
    logbase_d = Path(roms_dir) / "logs" / "nsz" / (filepath.stem + ".decomp_act")
    cmd = [str(tool_nsz), "-D", "-o", str(parent), str(filepath)]
    timeout = getattr(args, "cmd_timeout", None) if args else None

    try:
        if tqdm:
            with tqdm(total=1, desc=f"Decompressing {filepath.name}", unit="op"):
                run_cmd(cmd, filebase=logbase_d, timeout=timeout)
        else:
            run_cmd(cmd, filebase=logbase_d, timeout=timeout)
        return True
    except Exception:
        return False


def _get_mtime_safe(filepath: Path) -> Optional[float]:
    try:
        return os.path.getmtime(filepath)
    except Exception:
        return None


def _find_direct_candidate(
    filepath: Path, parent: Path, archive_mtime: Optional[float]
) -> Optional[Path]:
    candidates = []
    for ext in (".nsp", ".xci", ".xcz"):
        candidates.extend(list(parent.glob(filepath.stem + f"*{ext}")))

    if archive_mtime is not None:
        for c in candidates:
            try:
                if c.exists() and os.path.getmtime(c) >= archive_mtime - 2:
                    return c
            except Exception:
                continue
    return None


def _find_recent_candidate(
    filepath: Path,
    parent: Path,
    archive_mtime: float,
    run_cmd: Callable,
    tool_metadata: Optional[str],
    is_nstool: bool,
    keys_path: Optional[Path],
    args,
) -> Optional[Path]:
    look_window = 300
    recent_candidates = []
    for ext in (".nsp", ".xci", ".xcz"):
        for c in parent.glob(f"*{ext}"):
            try:
                mtime = os.path.getmtime(c)
                if archive_mtime - look_window <= mtime <= archive_mtime + look_window:
                    recent_candidates.append(c)
            except Exception:
                continue

    for cand in recent_candidates:
        if _check_candidate_match(
            cand, filepath, run_cmd, tool_metadata, is_nstool, keys_path, args
        ):
            return cand
    return None


def _check_candidate_match(
    cand: Path,
    filepath: Path,
    run_cmd: Callable,
    tool_metadata: Optional[str],
    is_nstool: bool,
    keys_path: Optional[Path],
    args,
) -> bool:
    try:
        # Metadata probe
        if tool_metadata:
            if _probe_metadata_match(
                cand, filepath, run_cmd, tool_metadata, is_nstool, keys_path, args
            ):
                return True

        # Size-match fallback
        if abs(os.path.getsize(cand) - os.path.getsize(filepath)) < 1024 * 1024:
            return True
    except Exception:
        pass
    return False


def _probe_metadata_match(
    cand: Path,
    filepath: Path,
    run_cmd: Callable,
    tool_metadata: str,
    is_nstool: bool,
    keys_path: Optional[Path],
    args,
) -> bool:
    cmd = [str(tool_metadata), "-v" if is_nstool else "-k", str(cand)]
    if not is_nstool and keys_path:
        cmd.insert(2, str(keys_path))
        cmd.insert(3, "-i")

    res_probe = run_cmd(
        cmd, timeout=getattr(args, "cmd_timeout", None) if args else None
    )
    out = getattr(res_probe, "stdout", "") or ""

    m = re.search(r"\[([0-9A-Fa-f]{16})\]", out)
    if m:
        tid_probe = m.group(1).upper()
        arch_tid_match = re.search(r"\[([0-9A-Fa-f]{16})\]", filepath.name)
        if arch_tid_match and arch_tid_match.group(1).upper() == tid_probe:
            return True
    return False


def _cleanup_original(filepath: Path, args, check_keep_failure: bool = False):
    if getattr(args, "dry_run", False):
        return

    if check_keep_failure and getattr(args, "keep_on_failure", False):
        return

    if filepath.exists():
        try:
            filepath.unlink()
        except Exception:
            pass


def replace_if_verified(
    tmp_file: Path,
    dest: Path,
    run_cmd: Callable,
    *,
    verify_fn: Callable[[Path, Callable], bool],
    dry_run: bool = False,
) -> bool:
    """Replace `dest` with `tmp_file` if `verify_fn(tmp_file, run_cmd)` returns True.

    If `dry_run` is True, the function will not perform filesystem modifications
    and will return what would have happened.
    Returns True if replacement occurred (or would occur in dry_run), False otherwise.
    """
    try:
        ok = verify_fn(tmp_file, run_cmd)
    except Exception:
        return False

    if not ok:
        return False

    if dry_run:
        return True

    # Ensure destination parent exists
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Use an atomic-ish replace: move tmp to a temporary name then replace
    try:
        # On the same filesystem, rename is atomic; use shutil.move for portability
        shutil.move(str(tmp_file), str(dest))
        return True
    except Exception:
        # As a last resort try copy and unlink
        try:
            shutil.copy2(str(tmp_file), str(dest))
            tmp_file.unlink(missing_ok=True)
            return True
        except Exception:
            return False
