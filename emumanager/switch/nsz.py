"""Helpers to parse NSZ/tool outputs and detect compression levels.

Small, pure functions that interpret stdout/stderr from NSZ or related tools.
These are intentionally conservative and return Optional values to allow the
caller to fallback to other heuristics.
"""

from __future__ import annotations

import re
from typing import Optional


def detect_nsz_level_from_stdout(stdout: Optional[str]) -> Optional[int]:
    """Try to extract a zstd compression level from NSZ tool output.

    Returns the level as int if found (1-22), otherwise None.
    """
    if not stdout:
        return None
    s = stdout
    # common patterns: 'zstd level: 3', 'compression level: 19', '-19' or 'level 3'
    m = re.search(
        r"(?:zstd|compression|level)[^0-9]{0,10}([1-9]|1[0-9]|2[0-2])\b",
        s,
        re.IGNORECASE,
    )
    if m:
        try:
            val = int(m.group(1))
            if 1 <= val <= 22:
                return val
        except Exception:
            return None

    # sometimes tools embed '-19' or ' -19 ' flags in logs
    m2 = re.search(r"-([1-9]|1[0-9]|2[0-2])\b", s)
    if m2:
        try:
            val = int(m2.group(1))
            if 1 <= val <= 22:
                return val
        except Exception:
            return None

    # Filename-like hints: look for 'level3' or 'l3'
    m3 = re.search(r"\b(?:level|l)([1-9]|1[0-9]|2[0-2])\b", s, re.IGNORECASE)
    if m3:
        try:
            val = int(m3.group(1))
            if 1 <= val <= 22:
                return val
        except Exception:
            return None

    return None


def parse_nsz_verify_output(stdout: Optional[str]) -> bool:
    """Return True if verify output indicates success, False otherwise.

    This is a conservative text-based check: many NSZ tools return 0 on success
    but we use stdout heuristics when only text is available.
    """
    if not stdout:
        return False
    low = stdout.lower()
    # Negative indicators
    if "error" in low or "failed" in low or "corrupt" in low or "invalid" in low:
        return False
    # Positive indicators
    if "ok" in low or "verified" in low or "success" in low or "checksum: ok" in low:
        return True
    # If unsure, return False to be conservative
    return False
