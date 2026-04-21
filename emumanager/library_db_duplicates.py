from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from .common.exceptions import DatabaseError
from .library_models import DuplicateGroup, LibraryEntry, normalize_game_name

logger = logging.getLogger(__name__)
HASH_COLUMNS = frozenset({"sha1", "sha256", "md5", "crc32"})


class LibraryDbDuplicateMixin:
    def find_duplicates_by_hash(
        self,
        prefer: tuple[str, ...] = ("sha1",),
    ) -> list[DuplicateGroup]:
        groups: list[DuplicateGroup] = []
        try:
            conn = self._get_conn()
            for column in prefer:
                if column not in HASH_COLUMNS:
                    logger.warning("Invalid hash column '%s' ignored", column)
                    continue

                cursor = conn.execute(
                    f"""
                    SELECT {column} FROM library
                    WHERE {column} IS NOT NULL AND {column} != ''
                    GROUP BY {column} HAVING COUNT(*) > 1
                    """
                )
                for (hash_value,) in cursor.fetchall():
                    entries_cursor = conn.execute(
                        f"SELECT * FROM library WHERE {column} = ?",
                        (hash_value,),
                    )
                    entries = [
                        self._row_to_entry(row, entries_cursor.description)
                        for row in entries_cursor.fetchall()
                    ]
                    if len(entries) > 1:
                        groups.append(
                            DuplicateGroup(
                                key=str(hash_value),
                                kind=column,
                                entries=entries,
                            )
                        )
            return groups
        except sqlite3.Error as exc:
            raise DatabaseError(f"Failed to find duplicates by hash: {exc}") from exc

    def find_duplicates_by_normalized_name(self) -> list[DuplicateGroup]:
        grouped_entries: dict[str, list[LibraryEntry]] = {}
        for entry in self.get_all_entries():
            normalized_name = normalize_game_name(
                entry.match_name or Path(entry.path).name
            )
            if normalized_name:
                grouped_entries.setdefault(normalized_name, []).append(entry)

        return [
            DuplicateGroup(key=name, kind="name", entries=entries)
            for name, entries in grouped_entries.items()
            if len(entries) > 1
        ]
