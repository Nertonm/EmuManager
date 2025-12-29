from pathlib import Path
from typing import Optional

SYSTEM_TO_DAT_KEYWORDS = {
    "nes": ["Nintendo - Nintendo Entertainment System"],
    "snes": ["Nintendo - Super Nintendo Entertainment System"],
    "n64": ["Nintendo - Nintendo 64"],
    "gba": ["Nintendo - Game Boy Advance"],
    "gb": ["Nintendo - Game Boy"],
    "gbc": ["Nintendo - Game Boy Color"],
    "nds": ["Nintendo - Nintendo DS"],
    "gamecube": ["Nintendo - GameCube"],
    "wii": ["Nintendo - Wii"],
    "wiiu": ["Nintendo - Wii U"],
    "switch": ["Nintendo - Nintendo Switch"],
    "psx": ["Sony - PlayStation"],
    "ps2": ["Sony - PlayStation 2"],
    "ps3": ["Sony - PlayStation 3"],
    "psp": ["Sony - PlayStation Portable"],
    "psvita": ["Sony - PlayStation Vita"],
    "dreamcast": ["Sega - Dreamcast"],
    "saturn": ["Sega - Saturn"],
    "megadrive": ["Sega - Mega Drive - Genesis"],
    "mastersystem": ["Sega - Master System - Mark III"],
    "gamegear": ["Sega - Game Gear"],
    "xbox": ["Microsoft - Xbox"],
    "xbox360": ["Microsoft - Xbox 360"],
    "neogeo": ["SNK - Neo Geo"],
}


def find_dat_for_system(dats_root: Path, system_name: str) -> Optional[Path]:
    """
    Find the best matching DAT file for a given system name.
    Searches in root, no-intro and redump subfolders.
    """
    keywords = SYSTEM_TO_DAT_KEYWORDS.get(system_name.lower())
    if not keywords:
        return None

    # Search locations: root, no-intro, redump
    search_dirs = [dats_root]
    search_dirs.extend([dats_root / sub for sub in ["no-intro", "redump"]])

    candidates = []
    for source_dir in search_dirs:
        if not source_dir.exists():
            continue

        for dat_file in source_dir.glob("*.dat"):
            name = dat_file.stem
            for kw in keywords:
                if kw in name:
                    candidates.append(dat_file)
                    break

    if not candidates:
        return None

    # Sort by name descending (usually puts newer dates first if format is Name
    # (YYYYMMDD))
    candidates.sort(key=lambda p: p.name, reverse=True)
    return candidates[0]
