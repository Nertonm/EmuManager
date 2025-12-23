#!/usr/bin/env python3
"""
PSP Converter (ISO -> CSO / CHD)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Callable

from ..common.execution import find_tool, run_cmd

def compress_to_cso(
    source: Path, 
    dest: Path, 
    level: int = 9, 
    block_size: Optional[int] = None,
    dry_run: bool = False,
    progress_cb: Optional[Callable[[float, str], None]] = None
) -> bool:
    """
    Compress ISO to CSO using maxcso.
    """
    maxcso = find_tool("maxcso")
    if not maxcso:
        raise FileNotFoundError("maxcso tool not found")

    cmd = [str(maxcso)]
    if level:
        cmd.extend(["--fast" if level < 5 else "--best"])
    
    if block_size:
        cmd.extend(["--block", str(block_size)])
        
    cmd.extend(["-o", str(dest), str(source)])
    
    if dry_run:
        return True
        
    try:
        # maxcso output is not easily parseable for progress, but we can try
        run_cmd(cmd, check=True)
        return dest.exists()
    except Exception:
        return False

def compress_to_chd(
    source: Path, 
    dest: Path, 
    num_processors: int = 4,
    dry_run: bool = False,
    progress_cb: Optional[Callable[[float, str], None]] = None
) -> bool:
    """
    Compress ISO/CUE/GDI to CHD using chdman.
    """
    chdman = find_tool("chdman")
    if not chdman:
        raise FileNotFoundError("chdman tool not found")

    cmd = [
        str(chdman), "createcd",
        "-i", str(source),
        "-o", str(dest),
        "-c", "zstd,huff", # Standard compression
        "-p", str(num_processors),
        "-f" # Force overwrite
    ]
    
    if dry_run:
        return True
        
    try:
        run_cmd(cmd, check=True)
        return dest.exists()
    except Exception:
        return False
