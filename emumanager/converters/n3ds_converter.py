#!/usr/bin/env python3
"""
N3DS Converter (3DS/CIA <-> 7Z)
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from ..common.execution import find_tool, run_cmd


def compress_to_7z(
    source: Path,
    dest: Path,
    level: int = 9,
    dry_run: bool = False,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> bool:
    """
    Compress 3DS/CIA to 7Z using 7z.
    """
    seven_z = find_tool("7z")
    if not seven_z:
        raise FileNotFoundError("7z tool not found")

    # 7z a -t7z -mx=9 -m0=lzma2 dest source
    cmd = [str(seven_z), "a", "-t7z", f"-mx={level}", "-m0=lzma2", "-y", str(dest), str(source)]

    if dry_run:
        return True

    try:
        # 7z output parsing for progress is possible but complex.
        # For now, we just run it.
        # TODO: Implement progress parsing for 7z
        run_cmd(cmd, check=True)
        return dest.exists()
    except Exception:
        return False


def decompress_7z(
    source: Path,
    dest_dir: Path,
    dry_run: bool = False,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> bool:
    """
    Decompress 7Z to dest_dir using 7z.
    """
    seven_z = find_tool("7z")
    if not seven_z:
        raise FileNotFoundError("7z tool not found")

    # 7z x source -o{dest_dir} -y
    cmd = [str(seven_z), "x", str(source), f"-o{dest_dir}", "-y"]

    if dry_run:
        return True

    try:
        run_cmd(cmd, check=True)
        return True
    except Exception:
        return False
