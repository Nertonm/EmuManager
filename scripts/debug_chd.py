#!/usr/bin/env python3
"""Debug helper for CHD extraction issues.

Usage:
    scripts/debug_chd.py /path/to/game.chd [--bytes N]

Tries several `chdman` verbs to extract either a small partial header
(`--inputbytes`) or a full ISO. Prints truncated stdout/stderr to help
diagnose why `chdman` may fail to produce data that other tools can read.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

DEFAULT_BYTES = 4 * 1024 * 1024


def find_chdman() -> Optional[Path]:
    p = shutil.which("chdman")
    return Path(p) if p else None


def _run_cmd(cmd: list[str]) -> tuple[int, str, str]:
    """Run command and return (rc, stdout, stderr)."""
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode, res.stdout or "", res.stderr or ""


def try_partial_extract(chdman: Path, src: Path, bytes_to_read: int) -> Optional[Path]:
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tf:
        tmp = Path(tf.name)

    cmds = [
        [
            str(chdman),
            "extractdvd",
            "-i",
            str(src),
            "-o",
            str(tmp),
            "--inputbytes",
            str(bytes_to_read),
        ],
        [
            str(chdman),
            "extractcd",
            "-i",
            str(src),
            "-o",
            str(tmp),
            "--inputbytes",
            str(bytes_to_read),
        ],
        [
            str(chdman),
            "extract",
            "-i",
            str(src),
            "-o",
            str(tmp),
            "--inputbytes",
            str(bytes_to_read),
        ],
    ]

    for cmd in cmds:
        print("Running:", " ".join(cmd))
        rc, out, err = _run_cmd(cmd)
        print("Return code:", rc)
        if out:
            print("STDOUT (truncated):\n" + out[:1000])
        if err:
            print("STDERR (truncated):\n" + err[:1000])
        if rc == 0 and tmp.exists():
            print("Partial extract succeeded, temp:", tmp)
            return tmp

    print("Partial extract failed for all verbs")
    try:
        if tmp.exists():
            tmp.unlink()
    except Exception:
        pass
    return None


def try_full_extract(chdman: Path, src: Path) -> Optional[Path]:
    with tempfile.NamedTemporaryFile(suffix=".iso", delete=False) as tf:
        tmpiso = Path(tf.name)

    cmds = [
        [str(chdman), "extractdvd", "-i", str(src), "-o", str(tmpiso)],
        [str(chdman), "extractcd", "-i", str(src), "-o", str(tmpiso)],
        [str(chdman), "extract", "-i", str(src), "-o", str(tmpiso)],
    ]

    for cmd in cmds:
        print("Running:", " ".join(cmd))
        rc, out, err = _run_cmd(cmd)
        print("Return code:", rc)
        if out:
            print("STDOUT (truncated):\n" + out[:1000])
        if err:
            print("STDERR (truncated):\n" + err[:1000])
        if rc == 0 and tmpiso.exists():
            print("Full extract succeeded, temp iso:", tmpiso)
            return tmpiso

    print("Full extract failed for all verbs")
    try:
        if tmpiso.exists():
            tmpiso.unlink()
    except Exception:
        pass
    return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("chd", type=Path)
    p.add_argument("--bytes", type=int, default=DEFAULT_BYTES)
    args = p.parse_args()

    chdpath = args.chd
    if not chdpath.exists():
        print(f"CHD not found: {chdpath}")
        return 2

    chdman = find_chdman()
    if not chdman:
        print(
            "chdman not found in PATH. Install mame-tools or ensure "
            "chdman is available."
        )
        return 3

    print(f"Trying partial extract (first {args.bytes} bytes)...")
    part = try_partial_extract(chdman, chdpath, args.bytes)
    if part:
        print("Partial extract written to:", part)
        print("Try inspecting: head -c 65536", part)
        return 0

    print("Partial failed, trying full extract to ISO...")
    full = try_full_extract(chdman, chdpath)
    if full:
        print("Full ISO written to:", full)
        print("Try inspecting: head -c 65536", full)
        return 0

    print("All extraction attempts failed. Check chdman stderr output above for clues.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
