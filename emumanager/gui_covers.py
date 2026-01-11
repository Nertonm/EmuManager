import os
from pathlib import Path

import requests
from PyQt6.QtCore import QCoreApplication, QObject, QRunnable, pyqtSignal

from emumanager.metadata_providers import GameTDBProvider, LibretroProvider

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
    log = pyqtSignal(str)  # Returns log messages


# Keep strong references to running downloaders to avoid them being
# garbage-collected while the QRunnable is still queued in QThreadPool.
_active_downloaders: set[object] = set()


class CoverDownloader(QRunnable):
    def __init__(
        self,
        system: str,
        game_id: str | None,
        region: str | None,
        cache_dir: str,
        file_path: str | None = None,
    ):
        super().__init__()
        self.system = system
        self.game_id = game_id
        self.region = region  # Ex: 'US', 'EN', 'JA'
        self.cache_dir = cache_dir
        self.file_path = file_path
        # Create signals with QCoreApplication as parent to ensure the
        # underlying C++ QObject isn't deleted when this runnable is
        # moved between threads or if Python GC runs.
        qa = QCoreApplication.instance()
        try:
            if qa is not None:
                self.signals = CoverSignals(qa)
            else:
                self.signals = CoverSignals()
        except Exception:
            # Fallback to no-parent signals if something goes wrong
            self.signals = CoverSignals()
        # Keep a strong reference until run() completes; removed in run()
        _active_downloaders.add(self)

    def run(self):
        try:
            self.signals.log.emit(
                f"CoverDownloader started for {self.system}, ID: {self.game_id}"
            )

            # Try to extract game_id if missing
            if not self.game_id and self.file_path and os.path.exists(self.file_path):
                self.game_id = self._extract_game_id()
                if self.game_id:
                    self.signals.log.emit(f"Extracted Game ID: {self.game_id}")

            # If we still don't have a game_id, try the filename (without ext).
            # This helps as a fallback for Libretro thumbnails.
            game_name = None
            if self.file_path:
                game_name = Path(self.file_path).stem

            if not self.game_id and not game_name:
                self.signals.log.emit("No Game ID and no Game Name found. Aborting.")
                self.signals.finished.emit(None)
                return

            # Strategy 1: GameTDB (requires Game ID)
            if self.game_id:
                if self._try_gametdb():
                    return

            # Strategy 2: Libretro Thumbnails (Fallback using Game Name)
            if game_name:
                if self._try_libretro(game_name):
                    return

            # Strategy 3: TheGamesDB (fallback search provider). This is
            # optional and will be attempted only if configured or available.
            try:
                from emumanager.metadata_providers import TheGamesDBProvider

                tgdb = TheGamesDBProvider()
                tg_url = tgdb.get_cover_url(
                    self.system, self.game_id, game_name, self.region
                )
                if tg_url:
                    # Use TheGamesDB's URL directly
                    ext = tg_url.split(".")[-1]
                    tgt_path = str(Path(self.cache_dir) / "covers" / self.system / f"{game_name}.{ext}")
                    self.signals.log.emit(f"Trying TheGamesDB URL: {tg_url}")
                    if self._download_file(tg_url, tgt_path):
                        self.signals.log.emit(f"Downloaded from TheGamesDB: {tg_url}")
                        self.signals.finished.emit(tgt_path)
                        return
            except Exception:
                pass

            self.signals.log.emit("Cover not found.")
            self.signals.finished.emit(None)
        finally:
            # Allow GC after the work is done
            try:
                _active_downloaders.discard(self)
            except Exception:
                pass

    def _try_gametdb(self) -> bool:
        provider = GameTDBProvider()
        urls = provider.get_cover_urls(self.system, self.game_id, self.region)

        if not urls:
            return False

        # Determine extension from the first URL. This is a simple heuristic
        # that assumes all candidate URLs share the same extension.
        ext = urls[0].split(".")[-1]

        # Construct local path
        file_path = str(Path(self.cache_dir) / "covers" / self.system / f"{self.game_id}.{ext}")

        # If already exists, return immediately
        if os.path.exists(file_path):
            self.signals.log.emit(f"Cover found in cache: {file_path}")
            self.signals.finished.emit(file_path)
            return True

        for url in urls:
            self.signals.log.emit(f"Trying GameTDB URL: {url}")
            if self._download_file(url, file_path):
                self.signals.log.emit(f"Downloaded from GameTDB: {url}")
                self.signals.finished.emit(file_path)
                return True
        return False

    def _try_libretro(self, game_name: str) -> bool:
        provider = LibretroProvider()
        # Try multiple candidate names: cleaned base title, and a variant
        # that includes the serial/game_id (e.g. "Title [SERIAL]"). Libretro
        # thumbnail names are sensitive to exact names so trying both helps.
        candidates: list[str] = []

        # Candidate 1: use the game_name as provided by GUI (may be stem)
        candidates.append(game_name)

        # Candidate 2: if we have a game_id, append a single bracketed serial
        if self.game_id:
            candidates.append(f"{game_name} [{self.game_id}]")

        for cand in candidates:
            url = provider.get_cover_url(self.system, self.game_id, cand)
            if not url:
                continue

            # Libretro is always png
            file_path = str(Path(self.cache_dir) / "covers" / self.system / f"{cand}.png")

            if os.path.exists(file_path):
                self.signals.log.emit(f"Cover found in cache: {file_path}")
                self.signals.finished.emit(file_path)
                return True

            self.signals.log.emit(f"Trying Libretro URL: {url}")
            if self._download_file(url, file_path):
                self.signals.log.emit(f"Downloaded from Libretro: {url}")
                self.signals.finished.emit(file_path)
                return True

        return False

    def _download_file(self, url: str, dest_path: str) -> bool:
        try:
            # Use a session for connection pooling if we were doing multiple requests,
            # but for a single file, direct get is fine.
            # Add a User-Agent to avoid being blocked by some servers
            headers = {"User-Agent": "EmuManager/1.0"}
            response = requests.get(url, timeout=10, headers=headers)

            if response.status_code == 200:
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with open(dest_path, "wb") as f:
                    f.write(response.content)
                return True
            else:
                self.signals.log.emit(
                    f"Failed to download {url}: Status {response.status_code}"
                )
        except Exception as e:
            self.signals.log.emit(f"Exception downloading {url}: {str(e)}")

        return False

    def _extract_game_id(self) -> str | None:
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
