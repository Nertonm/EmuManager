import os
import requests
from pathlib import Path
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject

# Import metadata extractors
try:
    from emumanager.gamecube.metadata import get_metadata as get_gc_metadata
except ImportError:
    get_gc_metadata = None

try:
    from emumanager.wii.metadata import get_metadata as get_wii_metadata
except ImportError:
    get_wii_metadata = None

try:
    from emumanager.ps2.metadata import get_ps2_serial
except ImportError:
    get_ps2_serial = None


class CoverSignals(QObject):
    finished = pyqtSignal(str)  # Returns the path of the image
    log = pyqtSignal(str)       # Returns log messages


class CoverDownloader(QRunnable):
    def __init__(self, system, game_id, region, cache_dir, file_path=None):
        super().__init__()
        self.system = system
        self.game_id = game_id
        self.region = region  # Ex: 'US', 'EN', 'JA'
        self.cache_dir = cache_dir
        self.file_path = file_path
        self.signals = CoverSignals()

    def run(self):
        self.signals.log.emit(
            f"CoverDownloader started for {self.system}, ID: {self.game_id}"
        )

        # Try to extract game_id if missing
        if not self.game_id and self.file_path and os.path.exists(self.file_path):
            self.game_id = self._extract_game_id()
            if self.game_id:
                self.signals.log.emit(f"Extracted Game ID: {self.game_id}")

        # If we still don't have a game_id, try to use the filename (without extension)
        # This is useful for Libretro thumbnails fallback
        game_name = None
        if self.file_path:
            game_name = Path(self.file_path).stem

        if not self.game_id and not game_name:
            self.signals.log.emit("No Game ID and no Game Name found. Aborting.")
            self.signals.finished.emit(None)
            return

        # Map system names to GameTDB system codes
        system_map = {
            "wii": "wii",
            "gamecube": "wii",  # GameTDB stores GC covers under wii/cover/
            "switch": "switch",
            "ps2": "ps2",
            "ps3": "ps3",
            "psp": "psp",  # GameTDB might not have PSP, need to check or use fallback
            "wiiu": "wiiu",
            "ds": "ds",
            "3ds": "3ds",
        }

        gametdb_system = system_map.get(self.system.lower())

        # Strategy 1: GameTDB (requires Game ID)
        if self.game_id and gametdb_system:
            # Determine file extension and URL pattern based on system
            ext = "png"
            if gametdb_system in ["ps2", "ps3", "switch"]:
                ext = "jpg"

            # Construct local path
            file_path = os.path.join(
                self.cache_dir, "covers", self.system, f"{self.game_id}.{ext}"
            )

            # If already exists, return immediately
            if os.path.exists(file_path):
                self.signals.log.emit(f"Cover found in cache: {file_path}")
                self.signals.finished.emit(file_path)
                return

            # Construct URL
            # GameTDB URL structure:
            # https://art.gametdb.com/{system}/cover/{region}/{game_id}.{ext}
            # Region mapping might be needed.
            # For now, try passed region or default to US/EN

            regions_to_try = [self.region, "US", "EN", "JA", "Other"]
            # Filter out None or empty regions
            regions_to_try = [r for r in regions_to_try if r]

            # Add a generic fallback if no specific region worked
            if "US" not in regions_to_try:
                regions_to_try.append("US")

            for reg in regions_to_try:
                url = (
                    f"https://art.gametdb.com/{gametdb_system}/cover/{reg}/"
                    f"{self.game_id}.{ext}"
                )
                self.signals.log.emit(f"Trying GameTDB URL: {url}")
                if self._download_file(url, file_path):
                    self.signals.log.emit(f"Downloaded from GameTDB: {url}")
                    self.signals.finished.emit(file_path)
                    return

        # Strategy 2: Libretro Thumbnails (Fallback using Game Name)
        # https://thumbnails.libretro.com/{System}/Named_Boxarts/{Name}.png
        # We need to map our system names to Libretro system names
        libretro_map = {
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
            "mastersystem": "Sega - Master System - Mark III",
            "saturn": "Sega - Saturn",
            "dreamcast": "Sega - Dreamcast",
        }

        libretro_system = libretro_map.get(self.system.lower())
        if libretro_system and game_name:
            # Libretro uses specific characters replacement
            # & -> _
            # * -> _
            # / -> _
            # : -> _
            # ` -> _
            # < -> _
            # > -> _
            # ? -> _
            # \ -> _
            # | -> _
            safe_name = (
                game_name.replace("&", "_")
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

            url = (
                f"https://thumbnails.libretro.com/{libretro_system}/"
                f"Named_Boxarts/{safe_name}.png"
            )
            # Use URL encoding for spaces etc
            import urllib.parse

            url = urllib.parse.quote(url, safe=":/")

            file_path = os.path.join(
                self.cache_dir, "covers", self.system, f"{safe_name}.png"
            )

            if os.path.exists(file_path):
                self.signals.log.emit(
                    f"Cover found in cache (Libretro): {file_path}"
                )
                self.signals.finished.emit(file_path)
                return

            self.signals.log.emit(f"Trying Libretro URL: {url}")
            if self._download_file(url, file_path):
                self.signals.log.emit(f"Downloaded from Libretro: {url}")
                self.signals.finished.emit(file_path)
                return

        self.signals.log.emit("Cover not found.")
        self.signals.finished.emit(None)

    def _download_file(self, url, dest_path):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with open(dest_path, "wb") as f:
                    f.write(response.content)
                return True
            else:
                # self.signals.log.emit(
                #     f"Failed to download {url}: Status {response.status_code}"
                # )
                pass
        except Exception:
            # self.signals.log.emit(f"Exception downloading {url}: {e}")
            pass
        return False

    def _extract_game_id(self):
        if not self.file_path:
            return None

        path = Path(self.file_path)
        sys_lower = self.system.lower()

        try:
            if sys_lower in ["gamecube", "gc"] and get_gc_metadata:
                meta = get_gc_metadata(path)
                return meta.get("game_id")
            elif sys_lower == "wii" and get_wii_metadata:
                meta = get_wii_metadata(path)
                return meta.get("game_id")
            elif sys_lower == "ps2" and get_ps2_serial:
                return get_ps2_serial(path)
        except Exception:
            pass

        return None
