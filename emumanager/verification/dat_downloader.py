import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, List, Optional

import requests

logger = logging.getLogger(__name__)

GITHUB_API_BASE = (
    "https://api.github.com/repos/libretro/libretro-database/contents/metadat"
)
RAW_BASE = "https://raw.githubusercontent.com/libretro/libretro-database/master/metadat"

SOURCES = {
    "no-intro": "no-intro",
    "redump": "redump",
}


class DatDownloader:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.session = requests.Session()
        # Set up retry strategy
        adapter = requests.adapters.HTTPAdapter(max_retries=3)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def list_available_dats(self, source: str) -> List[str]:
        """
        List available DAT files for a given source (no-intro, redump) using GitHub API.
        Returns a list of filenames.
        """
        if source not in SOURCES:
            logger.error(f"Unknown source: {source}")
            return []

        folder = SOURCES[source]
        url = f"{GITHUB_API_BASE}/{folder}"

        try:
            logger.info(f"Fetching file list from {url}...")
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()

            data = resp.json()
            files = [
                item["name"]
                for item in data
                if item["type"] == "file" and item["name"].endswith(".dat")
            ]
            return sorted(files)
        except Exception as e:
            logger.error(f"Error listing DATs: {e}")
            return []

    def download_dat(self, source: str, filename: str) -> Optional[Path]:
        """
        Download a specific DAT file.
        """
        if source not in SOURCES:
            return None

        folder = SOURCES[source]
        url = f"{RAW_BASE}/{folder}/{filename}"
        dest_dir = self.output_dir / source
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / filename

        try:
            logger.debug(f"Downloading {filename} from {url}...")
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()

            dest_file.write_bytes(resp.content)
            logger.debug(f"Saved to {dest_file}")
            return dest_file
        except Exception as e:
            logger.error(f"Error downloading {filename}: {e}")
            return None

    def download_all(
        self,
        source: str,
        max_workers: int = 5,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> int:
        """
        Download all available DATs for a source in parallel.

        Args:
            source: 'no-intro' or 'redump'
            max_workers: Number of parallel downloads
            progress_callback: Function(filename, current, total) called on completion

        Returns:
            Number of successfully downloaded files
        """
        files = self.list_available_dats(source)
        if not files:
            return 0

        total = len(files)
        completed = 0
        success_count = 0

        logger.info(
            f"Starting download of {total} DATs for {source} with {max_workers} workers"
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(self.download_dat, source, f): f for f in files
            }

            for future in as_completed(future_to_file):
                filename = future_to_file[future]
                completed += 1
                try:
                    result = future.result()
                    if result:
                        success_count += 1
                except Exception as exc:
                    logger.error(f"{filename} generated an exception: {exc}")

                if progress_callback:
                    progress_callback(filename, completed, total)

        return success_count
