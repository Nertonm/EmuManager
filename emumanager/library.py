from __future__ import annotations

from .library_db_core import LibraryDbCoreMixin
from .library_db_duplicates import LibraryDbDuplicateMixin
from .library_models import DuplicateGroup, LibraryEntry, normalize_game_name


class LibraryDB(LibraryDbCoreMixin, LibraryDbDuplicateMixin):
    """Facade for the library persistence and deduplication APIs."""


__all__ = [
    "DuplicateGroup",
    "LibraryDB",
    "LibraryEntry",
    "normalize_game_name",
]
                
