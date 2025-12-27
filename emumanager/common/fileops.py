"""File operation helpers extracted from the legacy script.

Provide a testable safe_move implementation that attempts to perform an
atomic, verified move. The function prefers an atomic rename when possible
(same filesystem) and falls back to copying into the destination directory
to a secure temporary file and then atomically replacing the final path.

It also optionally verifies content (via provided get_file_hash) before
removing the original, and logs audit information via the provided logger.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional


def _is_exact_duplicate_fast(s: Path, d: Path) -> bool:
    try:
        return os.path.getsize(s) == os.path.getsize(d) and int(
            os.path.getmtime(s)
        ) == int(os.path.getmtime(d))
    except Exception:
        return False


def _is_exact_duplicate_strict(
    s: Path, d: Path, get_file_hash: Callable[[Path], str]
) -> bool:
    try:
        return get_file_hash(s) == get_file_hash(d)
    except Exception:
        return False


def _choose_duplicate_target(
    source: Path,
    dst: Path,
    args: Any,
    get_file_hash: Callable[[Path], str],
    logger: Any,
) -> Optional[Path]:
    """Return None if exact duplicate handled (source removed), else a new path."""
    try:
        if getattr(args, "dup_check", "fast") == "strict":
            if _is_exact_duplicate_strict(source, dst, get_file_hash):
                logger.info(
                    "Exact duplicate (strict) detected; removing source file: %s",
                    source.name,
                )
                logger.debug("Exact duplicate (strict) full path: %s", source)
                try:
                    source.unlink()
                except Exception:
                    logger.debug("Failed removing duplicate source: %s", source)
                return None
        else:
            if _is_exact_duplicate_fast(source, dst):
                logger.info(
                    "Exact duplicate (fast) detected; removing source file: %s",
                    source.name,
                )
                logger.debug("Exact duplicate (fast) full path: %s", source)
                try:
                    source.unlink()
                except Exception:
                    logger.debug("Failed removing duplicate source: %s", source)
                return None
    except Exception:
        logger.debug("Duplicate check failed for %s and %s", source, dst)

    parent = dst.parent
    base = dst.stem
    suffix = dst.suffix
    counter = 1
    new_dest = parent / f"{base}_COPY_{counter}{suffix}"
    while new_dest.exists():
        counter += 1
        new_dest = parent / f"{base}_COPY_{counter}{suffix}"
    return new_dest


def _try_atomic_replace(source: Path, dest: Path, logger: Any) -> bool:
    try:
        source.replace(dest)
        logger.info("Moved (atomic): %s -> %s", source.name, dest.name)
        logger.debug("Moved (atomic) full paths: %s -> %s", source, dest)
        return True
    except Exception:
        return False


def _copy_and_replace(
    source: Path,
    dest: Path,
    dest_parent: Path,
    args: Any,
    get_file_hash: Callable[[Path], str],
    logger: Any,
) -> bool:
    tmp_path = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=".emumgr_tmp_", dir=str(dest_parent))
        tmp_path = Path(tmp_name)
        os.close(fd)

        shutil.copy2(str(source), str(tmp_path))

        with open(tmp_path, "rb") as f:
            try:
                os.fsync(f.fileno())
            except Exception:
                logger.debug("fsync failed for temp file %s", tmp_path)

        if getattr(args, "dup_check", "fast") == "strict":
            if not _verify_hashes(source, tmp_path, get_file_hash, logger):
                try:
                    tmp_path.unlink()
                except Exception:
                    logger.debug("Failed removing temp file after hash mismatch")
                return False

        os.replace(str(tmp_path), str(dest))
        logger.info("Moved (copy+replace): %s -> %s", source.name, dest.name)
        logger.debug("Moved (copy+replace) full paths: %s -> %s", source, dest)
        try:
            source.unlink()
        except Exception as e:
            logger.warning(
                "Could not remove original after move: %s -- %s",
                source.name,
                e,
            )
        return True
    except Exception as e:
        logger.exception("safe_move failed copying %s -> %s: %s", source, dest, e)
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                logger.debug("Failed cleaning up tmp file %s", tmp_path)
        return False


def _verify_hashes(
    src: Path, dst: Path, get_file_hash: Callable[[Path], str], logger: Any
) -> bool:
    try:
        return get_file_hash(src) == get_file_hash(dst)
    except Exception as e:
        logger.debug("Hash verification error for %s and %s: %s", src, dst, e)
        return False


def safe_unlink(path: Path, logger: Any) -> None:
    """Best-effort, logged deletion for potentially user-important files.

    INFO logs only the filename; DEBUG logs the full path.
    """
    try:
        if not path.exists():
            logger.debug("Attempted to delete non-existent file: %s", path)
            return

        path.unlink()
        logger.info("Deleted file: %s", path.name)
        logger.debug("Deleted file full path: %s", path)
    except PermissionError as exc:
        logger.warning("Permission denied deleting file %s: %s", path.name, exc)
        logger.debug("Permission denied deleting file full path: %s", path)
    except Exception:
        logger.exception("Unexpected error deleting file: %s", path)


def safe_move(
    source: Path,
    dest: Path,
    *,
    args: Any,
    get_file_hash: Callable[[Path], str],
    logger: Any,
) -> bool:
    """Orchestrate a safe, atomic move using helpers."""
    if getattr(args, "dry_run", False):
        logger.info("[DRY-RUN] safe_move %s -> %s", source.name, dest.name)
        logger.debug("[DRY-RUN] safe_move full paths: %s -> %s", source, dest)
        return True

    try:
        dest_parent = dest.parent
        dest_parent.mkdir(parents=True, exist_ok=True)

        if len(dest.name) > 240:
            stem = dest.stem[:200]
            dest = dest.with_name(stem + dest.suffix)

        if dest.exists() and source.resolve() != dest.resolve():
            chosen = _choose_duplicate_target(source, dest, args, get_file_hash, logger)
            if chosen is None:
                logger.debug(
                    "safe_move: duplicate detected, source removed: %s", source
                )
                return False
            # attempt rename/move to chosen
            try:
                if _try_atomic_replace(source, chosen, logger):
                    logger.warning("Collision: source renamed to: %s", chosen)
                    return True
                shutil.move(str(source), str(chosen))
                logger.warning("Collision: moved (fallback) to: %s", chosen)
                return True
            except Exception as e:
                logger.error("Failed to move on collision to %s: %s", chosen, e)
                return False

        # primary move
        if _try_atomic_replace(source, dest, logger):
            return True
        return _copy_and_replace(source, dest, dest_parent, args, get_file_hash, logger)
    except Exception as e:
        logger.exception("safe_move unexpected error for %s -> %s: %s", source, dest, e)
        return False
