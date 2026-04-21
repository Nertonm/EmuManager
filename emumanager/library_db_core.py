from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any, Optional

from .common.exceptions import DatabaseConnectionError, DatabaseError
from .common.validation import validate_not_empty
from .library_models import LibraryEntry

LIBRARY_SCHEMA = """
CREATE TABLE IF NOT EXISTS library (
    path TEXT PRIMARY KEY,
    system TEXT,
    size INTEGER,
    mtime REAL,
    status TEXT,
    crc32 TEXT,
    md5 TEXT,
    sha1 TEXT,
    sha256 TEXT,
    match_name TEXT,
    dat_name TEXT,
    extra_json TEXT
)
"""
LIBRARY_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_system ON library(system)",
    "CREATE INDEX IF NOT EXISTS idx_sha1 ON library(sha1) WHERE sha1 IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_sha256 ON library(sha256) WHERE sha256 IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_md5 ON library(md5) WHERE md5 IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_crc32 ON library(crc32) WHERE crc32 IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_status ON library(status)",
    "CREATE INDEX IF NOT EXISTS idx_match_name ON library(match_name)",
    "CREATE INDEX IF NOT EXISTS idx_system_status ON library(system, status)",
)
ACTION_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS library_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT,
    action TEXT,
    detail TEXT,
    ts REAL
)
"""
VALID_UPDATE_FIELDS = frozenset(
    {
        "system",
        "size",
        "mtime",
        "status",
        "crc32",
        "md5",
        "sha1",
        "sha256",
        "match_name",
        "dat_name",
        "extra_json",
    }
)


class LibraryDbCoreMixin:
    """SQLite-backed library persistence with thread-local connections."""

    def __init__(self, db_path: Path = Path("library.db")):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            try:
                self._local.conn = sqlite3.connect(self.db_path, timeout=30)
                self._local.conn.execute("PRAGMA journal_mode=WAL")
                self._local.conn.execute("PRAGMA synchronous=NORMAL")
            except sqlite3.Error as exc:
                raise DatabaseConnectionError(
                    f"Failed to connect to database: {self.db_path}"
                ) from exc
        return self._local.conn

    @contextmanager
    def transaction(self):
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_db(self):
        try:
            with closing(sqlite3.connect(self.db_path)) as conn:
                conn.execute(LIBRARY_SCHEMA)
                for statement in LIBRARY_INDEXES:
                    conn.execute(statement)
                conn.execute(ACTION_LOG_SCHEMA)
                conn.commit()
        except sqlite3.Error as exc:
            raise DatabaseError(f"Failed to initialize database schema: {exc}") from exc

    def _row_to_entry(self, row, description) -> LibraryEntry:
        row_dict = dict(zip([col[0] for col in description], row))
        return LibraryEntry(
            path=row_dict["path"],
            system=row_dict["system"],
            size=row_dict["size"],
            mtime=row_dict["mtime"],
            status=row_dict["status"],
            crc32=row_dict["crc32"],
            md5=row_dict["md5"],
            sha1=row_dict["sha1"],
            sha256=row_dict["sha256"],
            match_name=row_dict["match_name"],
            dat_name=row_dict["dat_name"],
            extra_metadata=json.loads(row_dict["extra_json"])
            if row_dict.get("extra_json")
            else {},
        )

    def update_entry(self, entry: LibraryEntry):
        try:
            conn = self._get_conn()
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO library
                    (path, system, size, mtime, status, crc32, md5, sha1, sha256, match_name, dat_name, extra_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.path,
                        entry.system,
                        entry.size,
                        entry.mtime,
                        entry.status,
                        entry.crc32,
                        entry.md5,
                        entry.sha1,
                        entry.sha256,
                        entry.match_name,
                        entry.dat_name,
                        json.dumps(entry.extra_metadata),
                    ),
                )
        except sqlite3.Error as exc:
            raise DatabaseError(f"Failed to update entry {entry.path}: {exc}") from exc

    def update_entry_fields(self, path: str, **fields) -> None:
        validate_not_empty(path, "path")
        if not fields:
            return

        safe_fields = {key: value for key, value in fields.items() if key in VALID_UPDATE_FIELDS}
        if not safe_fields:
            return

        set_clause = ", ".join(f"{key} = ?" for key in safe_fields.keys())
        values = list(safe_fields.values()) + [path]
        try:
            conn = self._get_conn()
            with conn:
                conn.execute(f"UPDATE library SET {set_clause} WHERE path = ?", values)
        except sqlite3.Error as exc:
            raise DatabaseError(f"Failed to update fields for {path}: {exc}") from exc

    def get_entry(self, path: str) -> Optional[LibraryEntry]:
        validate_not_empty(path, "path")
        try:
            conn = self._get_conn()
            cursor = conn.execute("SELECT * FROM library WHERE path = ?", (path,))
            row = cursor.fetchone()
            return self._row_to_entry(row, cursor.description) if row else None
        except sqlite3.Error as exc:
            raise DatabaseError(f"Failed to get entry {path}: {exc}") from exc

    def get_all_entries(self, limit: Optional[int] = None) -> list[LibraryEntry]:
        try:
            conn = self._get_conn()
            query = "SELECT * FROM library"
            if limit:
                query += f" LIMIT {int(limit)}"
            cursor = conn.execute(query)
            return [self._row_to_entry(row, cursor.description) for row in cursor.fetchall()]
        except sqlite3.Error as exc:
            raise DatabaseError(f"Failed to get all entries: {exc}") from exc

    def get_entries_by_system(
        self,
        system: str,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[LibraryEntry]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM library WHERE system = ? LIMIT ? OFFSET ?",
            (system, limit, offset),
        )
        return [self._row_to_entry(row, cursor.description) for row in cursor.fetchall()]

    def get_system_count(self, system: str) -> int:
        conn = self._get_conn()
        result = conn.execute(
            "SELECT COUNT(*) FROM library WHERE system = ?",
            (system,),
        ).fetchone()
        return result[0] if result else 0

    def remove_entry(self, path: str) -> None:
        validate_not_empty(path, "path")
        try:
            conn = self._get_conn()
            with conn:
                conn.execute("DELETE FROM library WHERE path = ?", (path,))
        except sqlite3.Error as exc:
            raise DatabaseError(f"Failed to remove entry {path}: {exc}") from exc

    def log_action(self, path: str, action: str, detail: Optional[str] = None) -> None:
        validate_not_empty(path, "path")
        validate_not_empty(action, "action")
        try:
            conn = self._get_conn()
            with conn:
                conn.execute(
                    "INSERT INTO library_actions (path, action, detail, ts) VALUES (?, ?, ?, ?)",
                    (path, action, detail, time.time()),
                )
        except sqlite3.Error as exc:
            raise DatabaseError(f"Failed to log action {action} for {path}: {exc}") from exc

    def get_recent_actions(self, limit: int = 50) -> list[dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT path, action, detail, ts FROM library_actions ORDER BY ts DESC LIMIT ?",
            (limit,),
        )
        return [
            {"path": row[0], "action": row[1], "detail": row[2], "ts": row[3]}
            for row in cursor.fetchall()
        ]
