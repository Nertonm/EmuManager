from typing import Optional

from .base import GameMetadata, MetadataProvider


class TheGamesDBProvider(MetadataProvider):
    def __init__(
        self, api_key: str = "1234567890"
    ):  # Placeholder or free key if available
        self.api_key = api_key
        self.base_url = "https://api.thegamesdb.net/v1"
        # TGDB requires platform IDs. We need a mapping.
        self.platform_ids = {
            "nes": 7,
            "snes": 6,
            "n64": 3,
            "gamecube": 2,
            "wii": 9,
            "wiiu": 38,
            "switch": 4971,
            "gb": 4,
            "gba": 5,
            "ds": 8,
            "3ds": 4912,
            "psx": 10,
            "ps2": 11,
            "ps3": 12,
            "ps4": 4919,
            "psp": 13,
            "psvita": 39,
            "xbox_classic": 14,
            "xbox360": 15,
            "dreamcast": 16,
            "megadrive": 18,
            "saturn": 17,
        }

    def get_metadata(
        self, system: str, game_id: Optional[str], game_name: Optional[str]
    ) -> Optional[GameMetadata]:
        # Without a valid API key, this won't work.
        # But this is the structure.
        if not game_name:
            return None

        platform_id = self.platform_ids.get(system.lower())
        if not platform_id:
            return None

        try:
            # Search for the game. Example request payload would include:
            # {"apikey": self.api_key, "name": game_name, "platform_id": platform_id}
            # Note: This is a mock implementation of the call structure
            # Example request (mocked):
            # response = requests.get(
            #     f"{self.base_url}/Games/ByGameName",
            #     params=params,
            # )
            # data = response.json()
            # Parse data...
            pass
        except Exception:
            pass

        return None

    def get_cover_url(
        self,
        system: str,
        game_id: Optional[str],
        game_name: Optional[str],
        region: Optional[str] = None,
    ) -> Optional[str]:
        # TGDB requires fetching metadata first to get image URLs
        return None
