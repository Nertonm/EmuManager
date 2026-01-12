"""Helpers to parse NSZ/tool outputs and detect compression levels.

Small, pure functions that interpret stdout/stderr from NSZ or related tools.
These are intentionally conservative and return Optional values to allow the
caller to fallback to other heuristics.
"""

from __future__ import annotations

import re
from typing import Optional


def _validate_level(match: Optional[re.Match]) -> Optional[int]:
    """Converts a regex match group to a valid compression level (1-22)."""
    if not match:
        return None
    try:
        val = int(match.group(1))
        if 1 <= val <= 22:
            return val
    except (ValueError, TypeError, IndexError) as e:
        import logging
        logging.debug(f"Failed to validate level from match: {e}")
    return None


def detect_nsz_level_from_stdout(stdout: Optional[str]) -> Optional[int]:
    """Try to extract a zstd compression level from NSZ tool output.

    Returns the level as int if found (1-22), otherwise None.
    """
    if not stdout:
        return None

    # Strategy 1: Explicit labels (e.g. 'zstd level: 3', 'compression level: 19')
    lvl = _validate_level(re.search(
        r"(?:zstd|compression|level)\D{0,10}([1-9]|1\d|2[0-2])\b",
        stdout, re.IGNORECASE
    ))
    if lvl:
        return lvl

    # Strategy 2: CLI flags embedded in logs (e.g. '-19')
    lvl = _validate_level(re.search(r"-([1-9]|1\d|2[0-2])\b", stdout))
    if lvl:
        return lvl

    # Strategy 3: Filename-like hints (e.g. 'level3', 'l3')
    return _validate_level(re.search(
        r"\b(?:level|l)([1-9]|1\d|2[0-2])\b", stdout, re.IGNORECASE
    ))


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
