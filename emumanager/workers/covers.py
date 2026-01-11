import logging
import os
from pathlib import Path

import requests
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal
from typing import Optional

logger = logging.getLogger(__name__)


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

    def _get_target_system(self) -> str:
        """Map internal system names to GameTDB system names."""
        system_map = {
            "switch": "switch",
            "wii": "wii",
            "gamecube": "wii",
            "ps2": "ps2",
            "ps3": "ps3",
            "3ds": "3ds",
            "ds": "ds",
            "psp": "psp",
            "psx": "psx",
        }
        return system_map.get(self.system.lower(), self.system.lower())

    def _search_remote_cover(self, target_system: str) -> tuple[Optional[bytes], Optional[str]]:
        """Try to find cover data by iterating regions and extensions. Returns (data, extension)."""
        regions = [self.region] if self.region else ["US", "EN", "JA", "EU", "Other"]
        extensions = [".png", ".jpg"]

        for reg in regions:
            if not reg:
                continue
            for ext in extensions:
                url = f"https://art.gametdb.com/{target_system}/cover/{reg}/{self.game_id}{ext}"
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        return response.content, ext
                except Exception as e:
                    logger.debug(f"Request failed for {url}: {e}")
                    continue
        return None, None

    def run(self):
        if not self.game_id:
            self.signals.finished.emit(None)
            return

        target_system = self._get_target_system()
        file_path = Path(self.cache_dir) / "covers" / target_system / f"{self.game_id}.jpg"

        # Check cache
        if file_path.exists():
            self.signals.finished.emit(str(file_path))
            return

        # Fetch remote
        found_data, actual_ext = self._search_remote_cover(target_system)

        if found_data and actual_ext:
            # Update path with correct extension if needed
            file_path = file_path.with_suffix(actual_ext)
            
            try:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_bytes(found_data)
                self.signals.finished.emit(str(file_path))
                return
            except Exception as e:
                logger.error(f"Failed to save cover to {file_path}: {e}")

        self.signals.finished.emit(None)
