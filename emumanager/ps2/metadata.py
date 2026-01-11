import gzip
import logging
import re
import subprocess
from pathlib import Path
from typing import Optional

from ..common.execution import find_tool

# Regex for PS2 Serial: 4 letters, underscore/dash, 3 digits, dot, 2 digits
# e.g. SLUS_200.02, SLES-50003
SERIAL_RE = re.compile(rb"([A-Z]{4})[_-](\d{3})\.?(\d{2})")
BOOT2_RE = re.compile(
    rb"BOOT2\s*=\s*cdrom0:\\?([A-Z]{4})[_-](\d{3})\.?(\d{2})", re.IGNORECASE
)


def _run_chdman_cmds(cmds: list[list[str]], tmp_path: str, logger: logging.Logger) -> int:
    """Executes a list of chdman commands until one succeeds or all fail."""
    rc = 1
    for cmd in cmds:
        try:
            proc = subprocess.run(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True
            )
            rc = proc.returncode
            if rc == 0 and Path(tmp_path).exists():
                break
            if rc != 0:
                logger.debug("chdman command failed (%s): %s", rc, proc.stderr)
        except Exception as e:
            rc = 1
            logger.debug(f"chdman command raised exception: {e}", exc_info=True)
            continue
    return rc


def _extract_chd_partial(file_path: Path, size: int, chdman: Path, logger: logging.Logger) -> bytes:
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tf:
        tmpname = tf.name

    try:
        cmds = [
            [str(chdman), cmd, "-i", str(file_path), "-o", tmpname, "--inputbytes", str(size)]
            for cmd in ["extractdvd", "extractcd", "extract"]
        ]
        
        if _run_chdman_cmds(cmds, tmpname, logger) == 0:
            with open(tmpname, "rb") as fh:
                return fh.read(size)
    except Exception as e:
        logger.debug(f"Partial extraction failed: {e}")
    finally:
        try:
            Path(tmpname).unlink(missing_ok=True)
        except Exception as e:
            logger.debug(f"Failed to cleanup partial tmp: {e}")
    return b""


def _extract_chd_full(file_path: Path, size: int, chdman: Path, logger: logging.Logger) -> bytes:
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".iso", delete=False) as tf:
        tmpname = tf.name

    try:
        cmds = [
            [str(chdman), cmd, "-i", str(file_path), "-o", tmpname]
            for cmd in ["extractdvd", "extractcd", "extract"]
        ]
        
        if _run_chdman_cmds(cmds, tmpname, logger) == 0:
            with open(tmpname, "rb") as fh:
                return fh.read(size)
    except Exception as e:
        logger.debug(f"Full extraction failed: {e}")
    finally:
        try:
            Path(tmpname).unlink(missing_ok=True)
        except Exception as e:
            logger.debug(f"Failed to cleanup full tmp: {e}")
    return b""


def _read_header_chd(file_path: Path, size: int) -> bytes:
    chdman = find_tool("chdman")
    if not chdman:
        return b""
    
    logger = logging.getLogger(__name__)
    
    # Strategy 1: Fast partial extraction
    data = _extract_chd_partial(file_path, size, chdman, logger)
    if data:
        return data

    # Strategy 2: Fallback to full extraction (slower, requires disk space)
    return _extract_chd_full(file_path, size, chdman, logger)


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
