from __future__ import annotations

import sqlite3
import threading
import unicodedata
import re
import logging
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from .common.exceptions import (
    DatabaseError,
    DatabaseConnectionError,
    DatabaseIntegrityError,
    EntryNotFoundError,
)
from .common.validation import (
    validate_path_exists,
    validate_not_empty,
)

logger = logging.getLogger(__name__)


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

    def __init__(self, db_path: Path = Path("library.db")):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Obtém conexão thread-local com a base de dados.
        
        Returns:
            Conexão SQLite configurada
            
        Raises:
            DatabaseConnectionError: Se falhar ao conectar
        """
        if not hasattr(self._local, "conn"):
            try:
                self._local.conn = sqlite3.connect(self.db_path, timeout=30)
                self._local.conn.execute("PRAGMA journal_mode=WAL")
                self._local.conn.execute("PRAGMA synchronous=NORMAL")
            except sqlite3.Error as e:
                raise DatabaseConnectionError(
                    f"Failed to connect to database: {self.db_path}"
                ) from e
        return self._local.conn

    @contextmanager
    def transaction(self):
        """Context manager para transações batch seguras."""
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_db(self):
        """Inicializa schema da base de dados.
        
        Raises:
            DatabaseError: Se falhar ao criar schema
        """
        try:
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
                
                # Criar índices para queries comuns
                conn.execute("CREATE INDEX IF NOT EXISTS idx_system ON library(system)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_sha1 ON library(sha1) WHERE sha1 IS NOT NULL")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_sha256 ON library(sha256) WHERE sha256 IS NOT NULL")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_md5 ON library(md5) WHERE md5 IS NOT NULL")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_crc32 ON library(crc32) WHERE crc32 IS NOT NULL")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON library(status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_match_name ON library(match_name)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_system_status ON library(system, status)")  # Índice composto
                
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
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to initialize database schema: {e}") from e

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
        """Atualiza ou insere entrada na biblioteca.
        
        Args:
            entry: Entrada a atualizar/inserir
            
        Raises:
            DatabaseError: Se falhar ao atualizar
        """
        import json
        
        try:
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
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to update entry {entry.path}: {e}") from e

    def update_entry_fields(self, path: str, **fields) -> None:
        """Atualiza campos específicos de uma entrada existente.
        
        Args:
            path: Caminho da entrada a atualizar
            **fields: Campos e valores a atualizar
            
        Raises:
            ValidationError: Se path for vazio
            DatabaseError: Se falhar ao atualizar
            
        Note:
            Apenas campos válidos são atualizados (SQL injection-safe)
        """
        validate_not_empty(path, "path")
        if not fields:
            return
            
        try:
            conn = self._get_conn()
            # Lista de campos válidos para evitar SQL injection
            valid_fields = {'system', 'size', 'mtime', 'status', 'crc32', 'md5', 'sha1', 'sha256', 'match_name', 'dat_name', 'extra_json'}
            safe_fields = {k: v for k, v in fields.items() if k in valid_fields}
            if not safe_fields:
                return
            set_clause = ", ".join([f"{k} = ?" for k in safe_fields.keys()])
            values = list(safe_fields.values()) + [path]
            with conn:
                conn.execute(f"UPDATE library SET {set_clause} WHERE path = ?", values)
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to update fields for {path}: {e}") from e

    def get_entry(self, path: str) -> Optional[LibraryEntry]:
        """Recupera uma entrada específica pelo path.
        
        Args:
            path: Caminho do arquivo
            
        Returns:
            Entrada encontrada ou None se não existir
            
        Raises:
            ValidationError: Se path for vazio
            DatabaseError: Se falhar ao consultar
        """
        validate_not_empty(path, "path")
        try:
            conn = self._get_conn()
            cursor = conn.execute("SELECT * FROM library WHERE path = ?", (path,))
            row = cursor.fetchone()
            return self._row_to_entry(row, cursor.description) if row else None
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to get entry {path}: {e}") from e

    def get_all_entries(self, limit: Optional[int] = None) -> list[LibraryEntry]:
        """Recupera todas as entradas da biblioteca.
        
        Args:
            limit: Limite opcional de resultados (None = sem limite)
            
        Returns:
            Lista de todas as entradas
            
        Raises:
            DatabaseError: Se falhar ao consultar
            
        Warning:
            Sem limit, pode retornar muitos resultados. Use get_entries_by_system
            ou paginação para grandes bibliotecas.
        """
        try:
            conn = self._get_conn()
            query = "SELECT * FROM library"
            if limit:
                query += f" LIMIT {int(limit)}"
            cursor = conn.execute(query)
            return [self._row_to_entry(r, cursor.description) for r in cursor.fetchall()]
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to get all entries: {e}") from e

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

    def remove_entry(self, path: str) -> None:
        """Remove uma entrada da biblioteca.
        
        Args:
            path: Caminho da entrada a remover
            
        Raises:
            ValidationError: Se path for vazio
            DatabaseError: Se falhar ao remover
        """
        validate_not_empty(path, "path")
        try:
            conn = self._get_conn()
            with conn:
                conn.execute("DELETE FROM library WHERE path = ?", (path,))
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to remove entry {path}: {e}") from e

    def log_action(self, path: str, action: str, detail: Optional[str] = None) -> None:
        """Registra uma ação realizada na biblioteca (audit trail).
        
        Args:
            path: Caminho do arquivo afetado
            action: Tipo de ação (e.g., 'ADD', 'UPDATE', 'DELETE', 'VERIFY')
            detail: Detalhes adicionais opcionais
            
        Raises:
            ValidationError: Se path ou action forem vazios
            DatabaseError: Se falhar ao registrar
        """
        validate_not_empty(path, "path")
        validate_not_empty(action, "action")
        
        import time
        try:
            conn = self._get_conn()
            with conn:
                conn.execute(
                    "INSERT INTO library_actions (path, action, detail, ts) VALUES (?, ?, ?, ?)",
                    (path, action, detail, time.time()),
                )
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to log action {action} for {path}: {e}") from e

    def get_recent_actions(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retorna as últimas ações para o Audit Trail."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT path, action, detail, ts FROM library_actions ORDER BY ts DESC LIMIT ?",
            (limit,)
        )
        return [{"path": r[0], "action": r[1], "detail": r[2], "ts": r[3]} for r in cursor.fetchall()]


    def find_duplicates_by_hash(self, prefer: tuple[str, ...] = ("sha1",)) -> list[DuplicateGroup]:
        """Procura duplicados físicos baseados em colunas de hash.
        
        Args:
            prefer: Tupla de colunas de hash a verificar (ordem de preferência)
                    Opções: 'sha1', 'sha256', 'md5', 'crc32'
                    
        Returns:
            Lista de grupos de duplicados encontrados
            
        Raises:
            DatabaseError: Se falhar ao consultar
            
        Note:
            Usa índices otimizados para performance. Retorna apenas grupos
            com 2+ entradas.
        """
        groups = []
        try:
            conn = self._get_conn()
            valid_cols = {"sha1", "md5", "crc32", "sha256"}
            
            for col in prefer:
                if col not in valid_cols:
                    logger.warning(f"Invalid hash column '{col}' ignored")
                    continue
                
                # Encontrar hashes repetidos (usa índice otimizado)
                cursor = conn.execute(f"""
                    SELECT {col} FROM library 
                    WHERE {col} IS NOT NULL AND {col} != ''
                    GROUP BY {col} HAVING COUNT(*) > 1
                """)
                hashes = [r[0] for r in cursor.fetchall()]
                
                for h in hashes:
                    cursor2 = conn.execute(f"SELECT * FROM library WHERE {col} = ?", (h,))
                    entries = [self._row_to_entry(r, cursor2.description) for r in cursor2.fetchall()]
                    if len(entries) > 1:  # Apenas grupos com duplicados
                        groups.append(DuplicateGroup(key=str(h), kind=col, entries=entries))
            return groups
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to find duplicates by hash: {e}") from e

    def find_duplicates_by_normalized_name(self) -> list[DuplicateGroup]:
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
                