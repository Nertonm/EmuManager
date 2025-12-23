
import re
import gzip
import subprocess
from pathlib import Path
from typing import Optional
from ..common.execution import find_tool

# Regex for PS2 Serial: 4 letters, underscore/dash, 3 digits, dot, 2 digits
# e.g. SLUS_200.02, SLES-50003
SERIAL_RE = re.compile(rb"([A-Z]{4})[_-](\d{3})\.?(\d{2})")
BOOT2_RE = re.compile(rb"BOOT2\s*=\s*cdrom0:\\?([A-Z]{4})[_-](\d{3})\.?(\d{2})", re.IGNORECASE)

def _read_header_chd(file_path: Path, size: int) -> bytes:
    chdman = find_tool("chdman")
    if not chdman:
        return b""
    
    try:
        # chdman extract -i input.chd -o -
        # We rely on chdman writing to stdout when -o - is used.
        # If this fails (chdman version dependent), we might need another way.
        proc = subprocess.Popen(
            [str(chdman), "extract", "-i", str(file_path), "-o", "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        try:
            data = proc.stdout.read(size)
        finally:
            proc.terminate()
            proc.wait()
        return data
    except Exception:
        return b""

def get_ps2_serial(file_path: Path) -> Optional[str]:
    """
    Attempts to find the PS2 Game Serial (e.g. SLUS-20002) in the file.
    Reads the first 4MB of the file to find the pattern.
    Supports .iso, .bin, .gz, and .chd.
    """
    data = b""
    try:
        suffix = file_path.suffix.lower()
        if suffix == ".gz":
            with gzip.open(file_path, "rb") as f:
                data = f.read(4 * 1024 * 1024)
        elif suffix == ".chd":
            data = _read_header_chd(file_path, 4 * 1024 * 1024)
        else:
            with open(file_path, "rb") as f:
                data = f.read(4 * 1024 * 1024)
        
        if not data:
            return None

        # Try finding BOOT2 first (more accurate)
        match = BOOT2_RE.search(data)
        if match:
            prefix = match.group(1).decode("ascii")
            part1 = match.group(2).decode("ascii")
            part2 = match.group(3).decode("ascii")
            return f"{prefix}-{part1}{part2}"

        # Fallback to raw serial search
        match = SERIAL_RE.search(data)
        if match:
            # Normalize to XXXX-YYYYY format
            prefix = match.group(1).decode("ascii")
            part1 = match.group(2).decode("ascii")
            part2 = match.group(3).decode("ascii")
            return f"{prefix}-{part1}{part2}"
    except Exception:
        pass
    return None
