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


def _read_header_chd(file_path: Path, size: int) -> bytes:
    chdman = find_tool("chdman")
    if not chdman:
        return b""
    logger = logging.getLogger(__name__)

    try:
        # chdman on some systems does not support writing to stdout ('-o -').
        # Instead extract a small portion to a temporary file and read it.
        import tempfile

        # First try a fast, partial extract (only `size` bytes) to a temp file.
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tf:
            tmpname = tf.name

        # Try DVD extract first, then CD, then generic extract commands
        cmds_partial = [
            [
                str(chdman),
                "extractdvd",
                "-i",
                str(file_path),
                "-o",
                tmpname,
                "--inputbytes",
                str(size),
            ],
            [
                str(chdman),
                "extractcd",
                "-i",
                str(file_path),
                "-o",
                tmpname,
                "--inputbytes",
                str(size),
            ],
            [
                str(chdman),
                "extract",
                "-i",
                str(file_path),
                "-o",
                tmpname,
                "--inputbytes",
                str(size),
            ],
        ]

        rc = 1
        for cmd in cmds_partial:
            try:
                proc = subprocess.run(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True
                )
                rc = proc.returncode
                if rc == 0 and Path(tmpname).exists():
                    break
                # Log stderr when a partial extract fails to aid debugging
                if rc != 0:
                    logger.debug(
                        "chdman partial extract failed (%s): %s", rc, proc.stderr
                    )
            except Exception:
                rc = 1
                logger.debug("chdman partial extract raised exception", exc_info=True)
                continue

        if rc == 0 and Path(tmpname).exists():
            # Read up to `size` bytes from the temporary file
            try:
                with open(tmpname, "rb") as fh:
                    data = fh.read(size)
            finally:
                try:
                    Path(tmpname).unlink()
                except Exception:
                    pass
            return data

        # If partial extraction failed, remove tmp and try a full extract to disk
        try:
            if Path(tmpname).exists():
                Path(tmpname).unlink()
        except Exception:
            pass

        # Fallback: perform a full extract (may produce a large temp ISO) and
        # read the header
        with tempfile.NamedTemporaryFile(suffix=".iso", delete=False) as tf_full:
            fulltmp = tf_full.name

        cmds_full = [
            [str(chdman), "extractdvd", "-i", str(file_path), "-o", fulltmp],
            [str(chdman), "extractcd", "-i", str(file_path), "-o", fulltmp],
            [str(chdman), "extract", "-i", str(file_path), "-o", fulltmp],
        ]

        rc_full = 1
        for cmd in cmds_full:
            try:
                proc = subprocess.run(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True
                )
                rc_full = proc.returncode
                if rc_full == 0 and Path(fulltmp).exists():
                    break
                if rc_full != 0:
                    logger.debug(
                        "chdman full extract failed (%s): %s", rc_full, proc.stderr
                    )
            except Exception:
                rc_full = 1
                logger.debug("chdman full extract raised exception", exc_info=True)
                continue

        if rc_full != 0 or not Path(fulltmp).exists():
            try:
                Path(fulltmp).unlink()
            except Exception:
                pass
            return b""

        try:
            with open(fulltmp, "rb") as fh:
                data = fh.read(size)
        finally:
            try:
                Path(fulltmp).unlink()
            except Exception:
                pass

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
