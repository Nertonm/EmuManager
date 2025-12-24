from __future__ import annotations

import re
import gzip
import subprocess
from pathlib import Path
from typing import Optional
from ..common.execution import find_tool

# PS1 boot line typically in SYSTEM.CNF as: BOOT = cdrom:\SLUS_005.94;1
PSX_BOOT_RE = re.compile(rb"BOOT\s*=\s*cdrom0?:\\?([A-Z]{4})[_-](\d{3})\.?((?:\d{2})?)", re.IGNORECASE)
SERIAL_RE = re.compile(rb"([A-Z]{4})[_-](\d{3})\.?((?:\d{2})?)")

def _read_header_chd(file_path: Path, size: int) -> bytes:
    chdman = find_tool("chdman")
    if not chdman:
        return b""
    try:
        proc = subprocess.Popen(
            [str(chdman), "extract", "-i", str(file_path), "-o", "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        try:
            data = proc.stdout.read(size)
        finally:
            proc.terminate()
            proc.wait()
        return data or b""
    except Exception:
        return b""

def get_psx_serial(file_path: Path) -> Optional[str]:
    """Attempt to extract PS1 serial (e.g., SLUS-00594) from image.

    Supports .bin/.iso/.gz/.chd. Reads up to 8MB from start to locate SYSTEM.CNF
    or raw serial tokens. Returns normalized form XXXX-YYYYY.
    """
    data = b""
    try:
        suffix = file_path.suffix.lower()
        if suffix == ".gz":
            with gzip.open(file_path, "rb") as f:
                data = f.read(8 * 1024 * 1024)
        elif suffix == ".chd":
            data = _read_header_chd(file_path, 8 * 1024 * 1024)
        else:
            with open(file_path, "rb") as f:
                data = f.read(8 * 1024 * 1024)
        if not data:
            return None

        m = PSX_BOOT_RE.search(data)
        if not m:
            m = SERIAL_RE.search(data)
        if m:
            prefix = m.group(1).decode("ascii")
            part1 = m.group(2).decode("ascii")
            part2 = m.group(3).decode("ascii") if m.group(3) else "00"
            return f"{prefix}-{part1}{part2}"
    except Exception:
        pass
    return None
