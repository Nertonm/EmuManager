"""File operation helpers extracted from the legacy script.

Provide a testable safe_move that mirrors the original behavior but accepts
injected dependencies (args, get_file_hash, logger) to avoid circular imports.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable, Optional, Any


def safe_move(
    source: Path,
    dest: Path,
    *,
    args: Any,
    get_file_hash: Callable[[Path], str],
    logger: Any,
) -> bool:
    """Move source -> dest safely.

    args: namespace with attributes dry_run and dup_check
    get_file_hash: function that returns a string hash for a Path
    logger: logger-like object for messages

    Returns True if moved, False otherwise. In strict duplicate case the
    source file may be removed and False returned (preserves legacy semantics).
    """
    if getattr(args, "dry_run", False):
        return True

    def handle_duplicate(dst: Path) -> Optional[Path]:
        try:
            if getattr(args, "dup_check", "fast") == "strict":
                s_hash = get_file_hash(source)
                d_hash = get_file_hash(dst)
                if s_hash == d_hash:
                    logger.info(f"Duplicata exata removida: {source.name}")
                    source.unlink()
                    return None
            else:
                if os.path.getsize(source) == os.path.getsize(dst) and int(os.path.getmtime(source)) == int(os.path.getmtime(dst)):
                    logger.info(f"Duplicata exata removida: {source.name}")
                    source.unlink()
                    return None
        except Exception as e:
            logger.debug("dup check failed: %s", e)

        parent = dst.parent
        base = dst.stem
        suffix = dst.suffix
        counter = 1
        new_dest = parent / f"{base}_COPY_{counter}{suffix}"
        while new_dest.exists():
            counter += 1
            new_dest = parent / f"{base}_COPY_{counter}{suffix}"
        return new_dest

    if dest.exists() and source != dest:
        new_path = handle_duplicate(dest)
        if new_path is None:
            return False
        try:
            shutil.move(str(source), str(new_path))
            logger.warning(f"Colisão! Renomeado para: {new_path.name}")
            return True
        except Exception as e:
            logger.error("move collision failed: %s", e)
            return False

    try:
        safe_parent = dest.parent
        safe_parent.mkdir(parents=True, exist_ok=True)

        if len(dest.name) > 240:
            stem = dest.stem[:200]
            dest = dest.with_name(stem + dest.suffix)

        final_dest = dest
        counter = 1
        while final_dest.exists() and final_dest != source:
            final_dest = dest.with_name(f"{dest.stem}_{counter}{dest.suffix}")
            counter += 1

        shutil.move(str(source), str(final_dest))
        logger.info("Movido: %s -> %s", source.name, final_dest)
        return True
    except Exception as e:
        logger.exception("Erro IO ao mover %s -> %s: %s", source, dest, e)
        return False
