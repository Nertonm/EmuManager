import sqlite3
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass


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
                (path, system, size, mtime, crc32, md5, sha1, sha256, status, match_name, dat_name)
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
