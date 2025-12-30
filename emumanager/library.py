import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass
class LibraryEntry:
    path: str
    system: str
    size: int
    mtime: float
    crc32: Optional[str]
    md5: Optional[str]
    sha1: Optional[str]
    sha256: Optional[str]
    status: str
    match_name: Optional[str]
    dat_name: Optional[str]


class LibraryDB:
    def __init__(self, db_path: Path = Path("library.db")):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS library (
                    path TEXT PRIMARY KEY,
                    system TEXT,
                    size INTEGER,
                    mtime REAL,
                    crc32 TEXT,
                    md5 TEXT,
                    sha1 TEXT,
                    sha256 TEXT,
                    status TEXT,
                    match_name TEXT,
                    dat_name TEXT
                )
            """)
            # Action log table for traceability of worker decisions
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS library_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT,
                    action TEXT,
                    detail TEXT,
                    ts REAL
                )
                """
            )
            conn.commit()

    def get_entry(self, path: str) -> Optional[LibraryEntry]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM library WHERE path = ?", (path,))
            row = cursor.fetchone()
            if row:
                return LibraryEntry(*row)
        return None

    def update_entry(self, entry: LibraryEntry):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO library
                (path, system, size, mtime, crc32, md5, sha1, sha256, status,
                 match_name, dat_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    entry.path,
                    entry.system,
                    entry.size,
                    entry.mtime,
                    entry.crc32,
                    entry.md5,
                    entry.sha1,
                    entry.sha256,
                    entry.status,
                    entry.match_name,
                    entry.dat_name,
                ),
            )
            conn.commit()

    def remove_entry(self, path: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM library WHERE path = ?", (path,))
            conn.commit()

    def get_all_entries(self) -> List[LibraryEntry]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM library")
            return [LibraryEntry(*row) for row in cursor.fetchall()]

    def find_entry_by_hash(self, hash_value: str) -> Optional[LibraryEntry]:
        """Return a library entry that matches the given hash
        (sha1/md5/sha256) or None.
        """
        if not hash_value:
            return None
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                (
                    "SELECT * FROM library WHERE sha1 = ? OR md5 = ? "
                    "OR sha256 = ? LIMIT 1"
                ),
                (hash_value, hash_value, hash_value),
            )
            row = cur.fetchone()
            if row:
                return LibraryEntry(*row)
        return None

    def get_total_count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM library")
            val = cursor.fetchone()[0]
            try:
                return int(val)
            except Exception:
                return 0

    def get_count_by_system(self) -> dict[str, int]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT system, COUNT(*) FROM library GROUP BY system"
            )
            return dict(cursor.fetchall())

    def get_entries_by_system(self, system: str) -> List[LibraryEntry]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM library WHERE system = ?", (system,))
            return [LibraryEntry(*row) for row in cursor.fetchall()]

    def get_total_size(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT SUM(size) FROM library")
            result = cursor.fetchone()[0]
            return result if result else 0

    def log_action(self, path: str, action: str, detail: Optional[str] = None):
        """Insert an action record for a library file for audit/tracing.

        Example actions: SKIPPED_COMPRESSED, MOVED, RENAMED
        """
        import time

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO library_actions (path, action, detail, ts) "
                "VALUES (?, ?, ?, ?)",
                (path, action, detail, time.time()),
            )
            conn.commit()

    def get_actions(self, limit: int = 100) -> list[tuple]:
        """Return recent library actions as list of tuples
        (path, action, detail, ts).
        """
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                (
                    "SELECT path, action, detail, ts "
                    "FROM library_actions "
                    "ORDER BY ts DESC LIMIT ?"
                ),
                (limit,),
            )
            return cur.fetchall()

    def _group_duplicates_by_column(self, column: str) -> list["DuplicateGroup"]:
        # backward-compatible default: filter non-game files
        return self._group_duplicates_by_column_impl(column, filter_non_games=True)

    def _group_duplicates_by_column_impl(
        self, column: str, filter_non_games: bool = True
    ) -> list["DuplicateGroup"]:
        if column not in {"sha1", "md5", "crc32", "sha256"}:
            raise ValueError(f"Unsupported hash column: {column}")

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                f"""
                SELECT {column}
                FROM library
                WHERE {column} IS NOT NULL AND {column} != ''
                GROUP BY {column}
                HAVING COUNT(*) > 1
                """
            )
            keys = [r[0] for r in cur.fetchall()]

            groups: list[DuplicateGroup] = []
            for k in keys:
                cur2 = conn.execute(
                    (
                        "SELECT * FROM library WHERE "
                        f"{column} = ? "
                        "ORDER BY size DESC, path ASC"
                    ),
                    (k,),
                )
                all_entries = [LibraryEntry(*row) for row in cur2.fetchall()]
                entries = all_entries
                if filter_non_games:
                    # Filter out non-game files: use guess_system_for_file heuristic
                    try:
                        from emumanager.manager import guess_system_for_file

                        # Build filtered entries list using the guessing helper.
                        filtered: list[LibraryEntry] = []
                        for e in all_entries:
                            try:
                                if guess_system_for_file(Path(e.path)):
                                    filtered.append(e)
                            except Exception:
                                # If guessing fails for an entry, include it
                                filtered.append(e)

                        entries = filtered
                    except Exception:
                        # If guessing fails globally, fall back to including all entries
                        entries = all_entries

                if not entries:
                    # If no entries remain after filtering, skip this group
                    continue

                groups.append(DuplicateGroup(key=str(k), kind=column, entries=entries))
            return groups

    def find_duplicates_by_hash(
        self,
        prefer: Iterable[str] = ("sha1", "md5", "crc32"),
        filter_non_games: bool = True,
    ) -> list["DuplicateGroup"]:
        """Return duplicate groups by hash.

        Notes:
        - If a file has multiple hashes filled in, it may appear in multiple groups
          depending on `prefer`.
        - Callers typically show these grouped by `kind`.
        """

        groups: list[DuplicateGroup] = []
        for col in prefer:
            groups.extend(
                self._group_duplicates_by_column_impl(
                    col, filter_non_games=filter_non_games
                )
            )
        return groups

    def find_duplicates_by_normalized_name(
        self, filter_non_games: bool = True
    ) -> list["DuplicateGroup"]:
        """Return duplicate groups by normalized filename (heuristic)."""
        entries = self.get_all_entries()
        # Optionally filter to only include game-like files using guess_system_for_file
        if filter_non_games:
            try:
                from emumanager.manager import guess_system_for_file

                entries = [e for e in entries if guess_system_for_file(Path(e.path))]
            except Exception:
                # If guessing unavailable, keep original list
                pass
        buckets: dict[str, list[LibraryEntry]] = {}
        for e in entries:
            key = normalize_game_name(Path(e.path).name)
            if not key:
                continue
            buckets.setdefault(key, []).append(e)

        groups: list[DuplicateGroup] = []
        for k, bucket in buckets.items():
            if len(bucket) <= 1:
                continue
            bucket_sorted = sorted(bucket, key=lambda x: (-x.size, x.path))
            groups.append(DuplicateGroup(key=k, kind="name", entries=bucket_sorted))
        return groups


def normalize_game_name(name: str) -> str:
    """Normalize a ROM filename into a canonical name for duplicate grouping.

    This is intentionally heuristic and conservative:
    - strips extension
    - removes common tags like (USA), [v1.1], (Rev 2)
    - normalizes unicode and whitespace
    """
    stem = Path(name).stem
    # Normalize unicode (accents etc) + casefold
    s = unicodedata.normalize("NFKD", stem)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.casefold()

    # Remove bracketed tags: (...) or [...]
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"\[[^\]]*\]", " ", s)

    # Remove common separators/noise
    s = re.sub(r"[_\-]+", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


@dataclass
class DuplicateGroup:
    key: str
    kind: str  # e.g. 'sha1'|'md5'|'crc32'|'name'
    entries: List[LibraryEntry]

    @property
    def count(self) -> int:
        return len(self.entries)

    @property
    def wasted_bytes(self) -> int:
        if len(self.entries) <= 1:
            return 0
        sizes = sorted((e.size for e in self.entries), reverse=True)
        return sum(sizes[1:])
