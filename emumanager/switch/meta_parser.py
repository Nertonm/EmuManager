"""Parsing helpers for metadata tool output.

This module centralizes the regex-based parsing of stdout from tools like
`nstool`/`hactool` so that parsing can be unit-tested without invoking
external commands.
"""
from __future__ import annotations

import re
from typing import Dict, Optional

# Reuse a Title ID pattern similar to the legacy script
TITLE_ID_RE = re.compile(r"(?:Title ID|Program Id):\s*(?:0x)?([0-9A-Fa-f]{16})", re.IGNORECASE)


def parse_tool_output(stdout: Optional[str]) -> Dict[str, Optional[str]]:
    """Parse tool stdout and extract name, title id, version and language hints.

    Returns a dict with keys: name, id, ver, langs (may be empty strings or None).
    """
    result = {"name": None, "id": None, "ver": None, "langs": ""}
    if not stdout:
        return result

    name_m = re.search(r"(?:Name|Application Name):\s*(.*)", stdout, re.IGNORECASE)
    if name_m:
        result["name"] = name_m.group(1).strip()

    tid_m = TITLE_ID_RE.search(stdout)
    if tid_m:
        result["id"] = tid_m.group(1).upper()

    ver_m = re.search(r"(?:Display Version|Version):\s*(.*)", stdout, re.IGNORECASE)
    if ver_m:
        result["ver"] = ver_m.group(1).strip()

    # languages are heuristically found by looking for known tokens (small subset)
    langs = []
    low = stdout.lower()
    for token, code in (
        ("japanese", "Ja"),
        ("english", "En"),
        ("portuguese", "Pt"),
        ("brazilianportuguese", "PtBR"),
        ("korean", "Ko"),
        ("chinese", "Zh"),
    ):
        if token in low:
            langs.append(code)
    if langs:
        result["langs"] = ",".join(langs)

    return result
