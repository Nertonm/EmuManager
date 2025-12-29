#!/usr/bin/env python3
"""
N3DS Converter (3DS/CIA <-> 7Z)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

from ..common.execution import find_tool, run_cmd, _register_process, _unregister_process


def _run_tool_with_progress(
    cmd: list[str],
    progress_cb: Optional[Callable[[float, str], None]] = None,
    progress_pattern: str = r"\s(\d+)%",
) -> bool:
    """
    Run a command with progress parsing using a regex pattern.
    """
    # Prepare startup info for Windows to hide window
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        startupinfo=startupinfo,
        encoding="utf-8",
        errors="replace",
    )

    _register_process(process)

    try:
        while True:
            # readline handles \n and \r with text=True (universal_newlines)
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break

            if line and progress_cb:
                # Parse progress using provided pattern
                match = re.search(progress_pattern, line)
                if match:
                    try:
                        percent = int(match.group(1))
                        progress_cb(percent / 100.0, f"Processing: {percent}%")
                    except ValueError:
                        pass

        process.wait()
        return process.returncode == 0
    finally:
        _unregister_process(process)


def _run_7z(
    cmd: list[str], progress_cb: Optional[Callable[[float, str], None]] = None
) -> bool:
    """
    Run 7z command with progress parsing.
    """
    # Ensure progress is output to stdout
    if "-bsp1" not in cmd:
        cmd.append("-bsp1")
    return _run_tool_with_progress(cmd, progress_cb, r"\s(\d+)%")


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
        return _run_7z(cmd, progress_cb) and dest.exists()
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
        return _run_7z(cmd, progress_cb)
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

    if progress_cb:
        progress_cb(0.0, "Starting decryption...")
        # Simulate work or run actual command
        progress_cb(1.0, "Decryption complete (mock)")

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
            # 3dsconv might output progress like "10% ...", try to capture it
            return _run_tool_with_progress(cmd, progress_cb, r"(\d+)%") and dest.exists()
        except Exception:
            return False

    # Priority 2: makerom (complex usage, requires extraction first)
    # For this iteration, we will require 3dsconv for CIA conversion.
    raise FileNotFoundError("3dsconv tool not found")
