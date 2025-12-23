#!/usr/bin/env python3
"""Small metadata utilities extracted from legacy switch_organizer.

This module contains pure functions that can be unit-tested independently:
- parse_languages
- detect_languages_from_filename
- get_base_id
- sanitize_name

These helpers avoid depending on heavy external globals and allow incremental
migration of the larger legacy script.
"""
from __future__ import annotations

import re
from typing import Optional

TITLE_ID_RE = re.compile(r"(?:Title ID|Program Id):\s*(?:0x)?([0-9A-FA-F]{16})", re.IGNORECASE)
INVALID_FILENAME_CHARS_RE = re.compile(r'[<>:"/\\|?*]')


def parse_languages(text_output: Optional[str]) -> str:
    """Normalize tool output and guess language short codes.

    Returns a bracketed string like "[En,PtBR]" or an empty string when nothing found.
    """
    if not text_output:
        return ""

    lang_map = {
        "americanenglish": "En",
        "britishenglish": "En",
        "english": "En",
        "japanese": "Ja",
        "french": "Fr",
        "canadianfrench": "Fr",
        "german": "De",
        "italian": "It",
        "spanish": "Es",
        "latinamericanspanish": "Es",
        "portuguese": "Pt",
        "brazilianportuguese": "PtBR",
        "dutch": "Nl",
        "russian": "Ru",
        "korean": "Ko",
        "traditionalchinese": "Zh",
        "simplifiedchinese": "Zh",
    }

    lowered = text_output.lower()
    found = {v for k, v in lang_map.items() if k in lowered}
    if not found:
        return ""

    codes = sorted(found)
    if len(codes) > 5:
        return "[Multi]" + ("+PtBR" if "PtBR" in codes else "")
    return "[" + ",".join(codes) + "]"


def detect_languages_from_filename(filename: str) -> str:
    """Guess language codes from filename tokens like EN, PTBR, JA.

    Keeps token order and returns bracketed codes or empty string.
    """
    token_map = {
        "PTBR": "PtBR",
        "PT-BR": "PtBR",
        "PT": "Pt",
        "EN": "En",
        "JP": "Ja",
        "JA": "Ja",
        "FR": "Fr",
        "DE": "De",
        "ES": "Es",
        "RU": "Ru",
        "KO": "Ko",
        "ZH": "Zh",
        "NL": "Nl",
        "IT": "It",
    }
    up = filename.upper()
    found = []
    for key, code in token_map.items():
        # match token when it's delimited by non-alphanumeric characters or string boundaries
        pattern = rf"(?<![A-Z0-9]){re.escape(key)}(?![A-Z0-9])"
        if re.search(pattern, up):
            found.append(code)
    if not found:
        return ""
    seen = []
    for c in found:
        if c not in seen:
            seen.append(c)
    return "[" + ",".join(seen) + "]"


def get_base_id(title_id: Optional[str]) -> Optional[str]:
    """Return the base title id by masking lower bits, or None for falsy input.

    Example: '0100ABCDEF000011' -> base masked hex string.
    """
    if not title_id:
        return None
    try:
        val = int(title_id, 16) & 0xFFFFFFFFFFFFE000
        return hex(val)[2:].upper().zfill(16)
    except Exception:
        return title_id


def sanitize_name(name: str) -> str:
    """Remove common release tags, control chars and invalid filesystem chars.

    Keeps the result reasonably short and normalized.
    """
    # Remove common release/group tags inside brackets
    name = re.sub(
        r"[\[\(][^\]\)]*(?:nsw2u|switch-xci|cr-|venom|hbg|bigblue)[^\]\)]*[\]\)]",
        "",
        name,
        flags=re.IGNORECASE,
    )
    # Remove explicit titleid brackets and version tokens
    name = re.sub(r"\[[0-9A-Fa-f]{16}\]", "", name)
    name = re.sub(r"v\d+(?:\.\d+)*", "", name, flags=re.IGNORECASE)
    # Strip control chars and reserved filesystem characters
    name = "".join(ch for ch in name if ord(ch) >= 32)
    name = INVALID_FILENAME_CHARS_RE.sub("", name)
    # Normalize whitespace and trailing separators
    name = re.sub(r"\s+", " ", name).strip()
    name = name.rstrip(" -_.")
    if len(name) > 120:
        name = name[:120].rstrip()
    return name


def determine_type(title_id: Optional[str], text_output: Optional[str]) -> str:
    """Heuristic to decide whether a title is Base, DLC or Update.

    Uses textual hints (update/patch/addon/dlc/application) first, then
    falls back to comparing title_id against its base id.
    """
    txt = (text_output or "").lower()
    if "update" in txt or "patch" in txt:
        return "UPD"
    if "addon" in txt or "add-on" in txt or "dlc" in txt:
        return "DLC"
    if "application" in txt or "gamecard" in txt or "program" in txt:
        return "Base"

    if title_id:
        try:
            tid_int = int(title_id, 16)
            suffix = tid_int & 0xFFF
            
            if suffix == 0x000:
                return "Base"
            if suffix == 0x800:
                return "UPD"
            return "DLC"
        except Exception:
            return "DLC"

    return "DLC"


REG_JPN = "(JPN)"
REG_USA = "(USA)"
REG_EUR = "(EUR)"
REG_KOR = "(KOR)"
REG_CHN = "(CHN)"
REG_BRA = "(BRA)"
REG_WORLD = "(World)"

def determine_region(filename: str, langs_str: Optional[str]) -> str:
    """Guess human-friendly region label from filename or languages string.

    Returns a small suffix like '(JPN)', '(USA)', '(World)' or empty string when unknown.
    """
    # Check filename first with regex
    m = re.search(r"\b(USA|EUR|EUR-?JPN|JPN|KOR|CHN|ASIA|WORLD|REGION FREE|EUROPE|JAPAN|BRA|PT-?BR)\b", filename, re.IGNORECASE)
    if m:
        reg = m.group(1).upper()
        if "WORLD" in reg or "REGION" in reg or "EN" in reg:
            return REG_WORLD
        mapping = {
            "USA": REG_USA,
            "EUR": REG_EUR,
            "JPN": REG_JPN,
            "KOR": REG_KOR,
            "CHN": REG_CHN,
            "ASIA": "(ASIA)",
            "EUROPE": REG_EUR,
            "JAPAN": REG_JPN,
            "BRA": REG_BRA,
            "PT-BR": REG_BRA,
            "PTBR": REG_BRA,
        }
        return mapping.get(reg, f"({reg})")

    if langs_str:
        if "Ja" in langs_str:
            return REG_JPN
        if "Ko" in langs_str:
            return REG_KOR
        if "Zh" in langs_str:
            return REG_CHN
        if "PtBR" in langs_str:
            return REG_BRA
        if "En" in langs_str:
            return REG_WORLD
    return ""
