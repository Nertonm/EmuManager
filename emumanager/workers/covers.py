import os
import requests
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject


class CoverSignals(QObject):
    finished = pyqtSignal(str)  # Returns the path to the image


class CoverDownloader(QRunnable):
    def __init__(self, system, game_id, region, cache_dir):
        super().__init__()
        self.system = system
        self.game_id = game_id
        self.region = region  # e.g., 'US', 'EN', 'JA'
        self.cache_dir = cache_dir
        self.signals = CoverSignals()

    def run(self):
        if not self.game_id:
            self.signals.finished.emit(None)
            return

        # Normalize system names for GameTDB
        # GameTDB uses: wii, switch, ps2, ps3, ds, 3ds, etc.
        gametdb_system = self.system.lower()
        if gametdb_system == "gamecube":
            gametdb_system = "wii"  # GameTDB hosts GC covers under Wii usually, or has a specific section?
            # Checking GameTDB: they have a section for Wii, WiiU, PS3, Switch, DS, 3DS.
            # GameCube covers are often found under Wii section with ID.
            # Let's verify this assumption later, but for now 'wii' is a safe bet for Nintendo consoles on GameTDB often.
            # Actually, GameTDB has 'wii' and 'ds'.
            # For PS2, GameTDB has 'ps2'.
            pass

        # Construct local path
        file_path = os.path.join(
            self.cache_dir, "covers", gametdb_system, f"{self.game_id}.jpg"
        )

        # Check cache
        if os.path.exists(file_path):
            self.signals.finished.emit(file_path)
            return

        # Construct URL
        # GameTDB URL format: https://art.gametdb.com/{system}/cover/{region}/{game_id}.png (or .jpg)
        # We try a few common extensions and regions if not specified

        regions_to_try = (
            [self.region] if self.region else ["US", "EN", "JA", "EU", "Other"]
        )
        extensions = [".png", ".jpg"]

        # Map internal system names to GameTDB system names
        system_map = {
            "switch": "switch",
            "wii": "wii",
            "gamecube": "wii",  # GameTDB mixes them often, or uses 'wii' for both in some contexts?
            # Actually GameTDB has 'wii' covers.
            # Let's try 'wii' for GC for now.
            "ps2": "ps2",
            "ps3": "ps3",
            "3ds": "3ds",
            "ds": "ds",
            "psp": "psp",  # GameTDB might not have PSP?
            "psx": "psx",  # GameTDB might not have PSX?
        }

        target_system = system_map.get(gametdb_system, gametdb_system)

        found_data = None

        for reg in regions_to_try:
            if not reg:
                continue
            for ext in extensions:
                url = f"https://art.gametdb.com/{target_system}/cover/{reg}/{self.game_id}{ext}"
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        found_data = response.content
                        file_path = file_path.replace(".jpg", ext)  # Update extension
                        break
                except Exception:
                    continue
            if found_data:
                break

        if found_data:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(found_data)
            self.signals.finished.emit(file_path)
        else:
            self.signals.finished.emit(None)
