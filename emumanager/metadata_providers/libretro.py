import urllib.parse
from typing import Optional

from .base import GameMetadata, MetadataProvider


class LibretroProvider(MetadataProvider):
    def __init__(self):
        self.system_map = {
            "gamecube": "Nintendo - GameCube",
            "wii": "Nintendo - Wii",
            "wiiu": "Nintendo - Wii U",
            "switch": "Nintendo - Switch",
            "ps2": "Sony - PlayStation 2",
            "ps3": "Sony - PlayStation 3",
            "psp": "Sony - PlayStation Portable",
            "psx": "Sony - PlayStation",
            "3ds": "Nintendo - Nintendo 3DS",
            "ds": "Nintendo - Nintendo DS",
            "n64": "Nintendo - Nintendo 64",
            "snes": "Nintendo - Super Nintendo Entertainment System",
            "nes": "Nintendo - Nintendo Entertainment System",
            "gba": "Nintendo - Game Boy Advance",
            "gb": "Nintendo - Game Boy",
            "gbc": "Nintendo - Game Boy Color",
            "megadrive": "Sega - Mega Drive - Genesis",
            "dreamcast": "Sega - Dreamcast",
            "saturn": "Sega - Saturn",
            "mastersystem": "Sega - Master System - Mark III",
        }

    def get_metadata(
        self, system: str, game_id: Optional[str], game_name: Optional[str]
    ) -> Optional[GameMetadata]:
        return None

    def get_cover_url(
        self,
        system: str,
        game_id: Optional[str],
        game_name: Optional[str],
        region: Optional[str] = None,
    ) -> Optional[str]:
        if not game_name:
            return None

        libretro_system = self.system_map.get(system.lower())
        if not libretro_system:
            return None

        # https://thumbnails.libretro.com/{System}/Named_Boxarts/{Name}.png
        # Libretro uses specific naming, usually matching No-Intro.
        # We need to ensure special characters are handled if necessary,
        # but usually requests handles encoding.

        # Libretro thumbnails are sensitive to exact naming. Filenames that
        # include repeated bracketed tokens (e.g. "Game Title [SLUS-20946]")
        # frequently cause 404s. Strip bracketed tokens and prefer the base
        # title when constructing the URL.
        import re

        # Remove all bracketed tokens like [SLUS-20946] to get a base title
        base_title = re.sub(r"\s*\[[^\]]+\]\s*", " ", game_name).strip()
        if not base_title:
            base_title = game_name

        # Prefer using the cleaned base title for libretro naming.
        cleaned = base_title

        safe_name = (
            cleaned.replace("&", "_")
            .replace("*", "_")
            .replace("/", "_")
            .replace(":", "_")
            .replace("`", "_")
            .replace("<", "_")
            .replace(">", "_")
            .replace("?", "_")
            .replace("\\", "_")
            .replace("|", "_")
        )

        # URL encode the rest (like spaces)
        safe_name = urllib.parse.quote(safe_name)

        url = (
            "https://thumbnails.libretro.com/"
            f"{libretro_system}/Named_Boxarts/{safe_name}.png"
        )
        return url
