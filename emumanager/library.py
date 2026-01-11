from __future__ import annotations

import sqlite3
import threading
import unicodedata
import re
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional


@dataclass(slots=True)
class LibraryEntry:
    path: str
    system: str
    size: int
    mtime: float
    status: str = "UNKNOWN"
    crc32: str | None = None
    md5: str | None = None
    sha1: str | None = None
    sha256: str | None = None
    match_name: str | None = None
    dat_name: str | None = None
    extra_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DuplicateGroup:
    key: str
    kind: str  # e.g. 'sha1'|'md5'|'crc32'|'name'
    entries: list[LibraryEntry]

    @property
    def count(self) -> int:
        return len(self.entries)

    @property
    def wasted_bytes(self) -> int:
        if len(self.entries) <= 1:
            return 0
        sizes = sorted((e.size for e in self.entries), reverse=True)
        return sum(sizes[1:])


def normalize_game_name(name: str) -> str:
    """Remove tags (brackets/parens) and normalize for comparison."""
    # Remover extensão se houver
    name = Path(name).stem
    # Remover tudo entre (), [], {}
    name = re.sub(r"\([^)]*\)", "", name)
    name = re.sub(r"\[[^]]*\]", "", name)
    name = re.sub(r"\{[^}]*\}", "", name)
    # Lowercase e remover caracteres especiais
    name = name.lower()
    name = re.sub(r"[^a-z0-9 ]", " ", name)
    # Colapsar espaços e trim
    return " ".join(name.split())


class LibraryDB:
    """Interface de persistência robusta com suporte a WAL e concorrência."""

    _local = threading.local()

    def __init__(self, db_path: Path = Path("library.db")):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(self.db_path, timeout=30)
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    def _init_db(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("""
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
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS library_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT,
                    action TEXT,
                    detail TEXT,
                    ts REAL
                )
            """)
            conn.commit()

    def _row_to_entry(self, row, description) -> LibraryEntry:
        import json
        d = dict(zip([col[0] for col in description], row))
        return LibraryEntry(
            path=d['path'], system=d['system'], size=d['size'], mtime=d['mtime'],
            status=d['status'], crc32=d['crc32'], md5=d['md5'], sha1=d['sha1'],
            sha256=d['sha256'], match_name=d['match_name'], dat_name=d['dat_name'],
            extra_metadata=json.loads(d['extra_json']) if d.get('extra_json') else {}
        )

    def update_entry(self, entry: LibraryEntry):
        import json
        conn = self._get_conn()
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO library 
                (path, system, size, mtime, status, crc32, md5, sha1, sha256, match_name, dat_name, extra_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.path, entry.system, entry.size, entry.mtime, entry.status,
                entry.crc32, entry.md5, entry.sha1, entry.sha256,
                entry.match_name, entry.dat_name, json.dumps(entry.extra_metadata)
            ))

    def update_entry_fields(self, path: str, **fields):
        if not fields: return
        conn = self._get_conn()
        set_clause = ", ".join([f"{k} = ?" for k in fields.keys()])
        values = list(fields.values()) + [path]
        with conn:
            conn.execute(f"UPDATE library SET {set_clause} WHERE path = ?", values)

    def get_entry(self, path: str) -> Optional[LibraryEntry]:
        conn = self._get_conn()
        cursor = conn.execute("SELECT * FROM library WHERE path = ?", (path,))
        row = cursor.fetchone()
        return self._row_to_entry(row, cursor.description) if row else None

    def get_all_entries(self) -> list[LibraryEntry]:
        conn = self._get_conn()
        cursor = conn.execute("SELECT * FROM library")
        return [self._row_to_entry(r, cursor.description) for r in cursor.fetchall()]

    def get_entries_by_system(self, system: str, limit: int = 1000, offset: int = 0) -> list[LibraryEntry]:
        """Retorna uma página de entradas para um sistema específico."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM library WHERE system = ? LIMIT ? OFFSET ?",
            (system, limit, offset)
        )
        return [self._row_to_entry(r, cursor.description) for r in cursor.fetchall()]

    def get_system_count(self, system: str) -> int:
        """Retorna o total de ficheiros de um sistema."""
        conn = self._get_conn()
        res = conn.execute("SELECT COUNT(*) FROM library WHERE system = ?", (system,)).fetchone()
        return res[0] if res else 0

    def remove_entry(self, path: str):

        conn = self._get_conn()
        with conn:
            conn.execute("DELETE FROM library WHERE path = ?", (path,))

    def log_action(self, path: str, action: str, detail: Optional[str] = None):
        import time
        conn = self._get_conn()
        with conn:
            conn.execute(
                "INSERT INTO library_actions (path, action, detail, ts) VALUES (?, ?, ?, ?)",
                (path, action, detail, time.time()),
            )

    def get_recent_actions(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retorna as últimas ações para o Audit Trail."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT path, action, detail, ts FROM library_actions ORDER BY ts DESC LIMIT ?",
            (limit,)
        )
        return [{"path": r[0], "action": r[1], "detail": r[2], "ts": r[3]} for r in cursor.fetchall()]


    def find_duplicates_by_hash(self, prefer: tuple[str, ...] = ("sha1",)) -> list[DuplicateGroup]:
        """Procura duplicados físicos baseados em colunas de hash."""
        groups = []
        conn = self._get_conn()
        for col in prefer:
            if col not in {"sha1", "md5", "crc32", "sha256"}: continue
            
            # Encontrar hashes repetidos
            cursor = conn.execute(f"""
                SELECT {col} FROM library 
                WHERE {col} IS NOT NULL AND {col} != ''
                GROUP BY {col} HAVING COUNT(*) > 1
            """)
            hashes = [r[0] for r in cursor.fetchall()]
            
            for h in hashes:
                cursor2 = conn.execute(f"SELECT * FROM library WHERE {col} = ?", (h,))
                entries = [self._row_to_entry(r, cursor2.description) for r in cursor2.fetchall()]
                groups.append(DuplicateGroup(key=str(h), kind=col, entries=entries))
        return groups

    def find_duplicates_by_normalized_name(self, filter_non_games: bool = True) -> list[DuplicateGroup]:
        """Procura duplicados baseados no nome normalizado do jogo."""
        all_entries = self.get_all_entries()
        by_norm_name: dict[str, list[LibraryEntry]] = {}
        
        for entry in all_entries:
            norm = normalize_game_name(entry.match_name or Path(entry.path).name)
            if not norm: continue
            by_norm_name.setdefault(norm, []).append(entry)
            
        groups = []
        for norm, entries in by_norm_name.items():
            if len(entries) > 1:
                groups.append(DuplicateGroup(key=norm, kind="name", entries=entries))
        return groups
                