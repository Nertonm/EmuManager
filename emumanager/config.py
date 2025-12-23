"""Configuration and constants for EmuManager package."""
from __future__ import annotations

from typing import Dict

# Default base directory for collections
BASE_DEFAULT = "./Acervo_Games_Ultimate"

# Date format used across modules
DATE_FMT = "%d/%m/%Y às %H:%M"

# Minimal extension -> system mapping for guessing where to put ROMs
EXT_TO_SYSTEM: Dict[str, str] = {
    # Nintendo
    ".nes": "nes",
    ".sfc": "snes",
    ".smc": "snes",
    ".z64": "n64",
    ".n64": "n64",
    ".gba": "gba",
    ".nds": "nds",
    ".3ds": "3ds",
    ".cia": "3ds",
    ".cci": "3ds",
    ".gcm": "gamecube",
    ".rvz": "gamecube", # Dolphin (GC/Wii)
    ".gcz": "gamecube",  # Legacy Dolphin compressed format (GC/Wii)
    ".wbfs": "wii",
    ".wad": "wii",      # WiiWare titles
    ".wud": "wiiu",
    ".wux": "wiiu",
    ".wua": "wiiu",
    ".rpx": "wiiu",
    # Sony
    ".iso": "ps2",  # Ambiguous: could be psx, psp, gc, wii, ps3, xbox
    ".chd": "ps2",  # Ambiguous: could be psx, dc, saturn, etc.
    ".bin": "psx",  # Ambiguous
    ".cue": "psx",
    ".cso": "psp",
    ".pbp": "psp",
    ".pkg": "ps3",  # Ambiguous: ps3, ps4, psvita
    ".vpk": "psvita",
    # Sega
    ".md": "megadrive",
    ".gen": "megadrive",
    ".sms": "mastersystem",
    ".gdi": "dreamcast",
    ".cdi": "dreamcast",
    # Switch/Xbox
    ".xci": "switch",
    ".nsp": "switch",
    ".nsz": "switch",
    ".xiso": "xbox_classic",
    ".xex": "xbox360",
    # Retro/Arcade
    ".a26": "atari2600",
    ".zip": "mame", # Highly ambiguous (could be any retro system)
}
