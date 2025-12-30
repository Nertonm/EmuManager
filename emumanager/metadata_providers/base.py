from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class GameMetadata:
    title: Optional[str] = None
    description: Optional[str] = None
    release_date: Optional[str] = None
    developer: Optional[str] = None
    publisher: Optional[str] = None
    genres: Optional[list] = None
    rating: Optional[float] = None
    cover_url: Optional[str] = None
    backdrop_url: Optional[str] = None


class MetadataProvider(ABC):
    @abstractmethod
    def get_metadata(
        self, system: str, game_id: Optional[str], game_name: Optional[str]
    ) -> Optional[GameMetadata]:
        """
        Fetch metadata for a game.
        """
        pass

    @abstractmethod
    def get_cover_url(
        self,
        system: str,
        game_id: Optional[str],
        game_name: Optional[str],
        region: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get the URL for the game cover.
        """
        pass
