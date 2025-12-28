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


def decrypt_3ds(
    source: Path,
    dest: Path,
    dry_run: bool = False,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> bool:
    """
    Decrypt 3DS file using ctrtool (if available).
    Note: This is a placeholder for actual decryption logic which is complex.
    It currently checks for 'ctrtool' availability.
    """
    ctrtool = find_tool("ctrtool")
    if not ctrtool:
        raise FileNotFoundError("ctrtool not found")

    # TODO: Implement actual decryption command.
    # This usually involves extracting NCCH partitions and rebuilding,
    # or using a specific flag if supported.
    # For now, we'll just log that we found the tool.

    if dry_run:
        return True

    return False


def convert_to_cia(
    source: Path,
    dest: Path,
    dry_run: bool = False,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> bool:
    """
    Convert 3DS to CIA using 3dsconv (if available) or makerom/ctrtool.
    """
    # Priority 1: 3dsconv (Python script often in path)
    conv_tool = find_tool("3dsconv")
    if conv_tool:
        cmd = [str(conv_tool), "--output", str(dest), "--overwrite", str(source)]
        if dry_run:
            return True
        try:
            run_cmd(cmd, check=True)
            return dest.exists()
        except Exception:
            return False

    # Priority 2: makerom (complex usage, requires extraction first)
    # For this iteration, we will require 3dsconv for CIA conversion.
    raise FileNotFoundError("3dsconv tool not found")
