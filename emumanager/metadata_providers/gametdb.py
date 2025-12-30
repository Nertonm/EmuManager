from typing import Optional

from .base import GameMetadata, MetadataProvider


class GameTDBProvider(MetadataProvider):
    def __init__(self):
        # Note: GameCube covers are located under the 'wii' path on GameTDB.
        self.system_map = {
            "wii": "wii",
            "gamecube": "wii",
            "switch": "switch",
            "ps2": "ps2",
            "ps3": "ps3",
            "psp": "psp",
            "wiiu": "wiiu",
            "ds": "ds",
            "3ds": "3ds",
        }

    def get_metadata(
        self, system: str, game_id: Optional[str], game_name: Optional[str]
    ) -> Optional[GameMetadata]:
        # GameTDB metadata requires downloading large XMLs, skipping for now.
        # We only implement cover fetching.
        return None

    def get_cover_url(
        self,
        system: str,
        game_id: Optional[str],
        game_name: Optional[str],
        region: Optional[str] = None,
    ) -> Optional[str]:
        if not game_id:
            return None

        gametdb_system = self.system_map.get(system.lower())
        if not gametdb_system:
            return None

        ext = "png"
        if gametdb_system in ["ps2", "ps3", "switch"]:
            ext = "jpg"

        # GameTDB URL structure:
        # https://art.gametdb.com/{system}/cover/{region}/{game_id}.{ext}

        # We return the most likely URL. The downloader may try multiple regions
        # if the first candidate fails. The current interface returns a single
        # URL; changing it to return candidates would allow retries here.

        # To keep this method fast and non-blocking, prefer returning a single
        # likely candidate and let the caller try alternatives if needed.

        # Choose a sensible default region when none is provided.
        target_region = region if region else "US"

        return (
            "https://art.gametdb.com/"
            f"{gametdb_system}/cover/{target_region}/{game_id}.{ext}"
        )

    def get_cover_urls(
        self, system: str, game_id: Optional[str], region: Optional[str] = None
    ) -> list[str]:
        """
        Extension to get multiple candidate URLs for GameTDB
        """
        if not game_id:
            return []

        gametdb_system = self.system_map.get(system.lower())
        if not gametdb_system:
            return []

        ext = "png"
        if gametdb_system in ["ps2", "ps3", "switch"]:
            ext = "jpg"

        regions = [region] if region else []
        regions += ["US", "EN", "JA", "Other"]
        # Deduplicate and filter None
        regions = list(dict.fromkeys([r for r in regions if r]))

        urls = []
        for reg in regions:
            urls.append(
                f"https://art.gametdb.com/{gametdb_system}/cover/{reg}/{game_id}.{ext}"
            )

        return urls
