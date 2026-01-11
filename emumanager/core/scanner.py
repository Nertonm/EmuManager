from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional, Any

from emumanager.library import LibraryDB, LibraryEntry
from emumanager.logging_cfg import get_logger
from emumanager.common.registry import registry
from emumanager.verification import dat_parser, hasher
from emumanager.core.intelligence import MatchEngine
from emumanager.metadata_providers.retroachievements import RetroAchievementsProvider


class Scanner:
    """Responsável por descobrir, catalogar e validar ficheiros usando SystemProviders, DATs, NLP e RA."""

    def __init__(self, db: LibraryDB, dat_manager: Any = None):
        self.db = db
        self.dat_manager = dat_manager
        self.intelligence = MatchEngine()
        self.ra_provider = RetroAchievementsProvider() # Inicializado sem chaves por defeito
        self.logger = get_logger("core.scanner")



    def scan_directory(
        self,
        root: Path,
        progress_cb: Optional[Callable[[float, str], None]] = None,
        cancel_event: Optional[Any] = None,
        deep_scan: bool = False
    ) -> dict[str, int]:
        """Workflow principal de auditoria: coordena a descoberta e validação do acervo."""
        stats = {"added": 0, "updated": 0, "removed": 0, "skipped": 0, "verified": 0}
        
        if not root.exists():
            return stats

        existing_entries = {e.path: e for e in self.db.get_all_entries()}
        found_paths = set()

        systems = self._get_system_directories(root)
        total_systems = len(systems)

        for i, sys_dir in enumerate(systems):
            if cancel_event and cancel_event.is_set():
                break
            
            if progress_cb:
                progress_cb(i / total_systems, f"Scanning {sys_dir.name}...")
                
            self._process_system(
                sys_dir, deep_scan, stats, found_paths, existing_entries, cancel_event
            )

        self._cleanup_removed_entries(existing_entries, found_paths, stats)
        return stats

    def _get_system_directories(self, root: Path) -> list[Path]:
        """Identifica pastas de sistema candidatas a scan."""
        return [d for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")]

    def _load_dat(self, system_name: str) -> Optional[Any]:
        """Carrega a base de dados DAT para o sistema se disponível."""
        if not self.dat_manager:
            return None
            
        dat_path = self.dat_manager.find_dat_for_system(system_name)
        if not dat_path:
            return None
            
        try:
            dat_db = dat_parser.parse_dat_file(dat_path)
            self.logger.info(f"DAT carregado para {system_name}: {dat_path.name}")
            return dat_db
        except Exception as e:
            self.logger.warning(f"Erro ao carregar DAT para {system_name}: {e}")
            return None

    def _process_system(
        self,
        sys_dir: Path,
        deep_scan: bool,
        stats: dict,
        found_paths: set,
        existing_entries: dict,
        cancel_event: Optional[Any]
    ):
        """Varre recursivamente os ficheiros de uma consola específica."""
        system_name = sys_dir.name
        provider = registry.get_provider(system_name)
        dat_db = self._load_dat(system_name)

        for file_path in sys_dir.rglob("*"):
            if cancel_event and cancel_event.is_set():
                break
                
            if self._is_valid_rom_file(file_path):
                self._process_file(
                    file_path, system_name, provider, dat_db, 
                    deep_scan, stats, found_paths, existing_entries
                )

    def _is_valid_rom_file(self, path: Path) -> bool:
        """Filtra ficheiros ocultos ou de sistema."""
        return path.is_file() and not path.name.startswith(".") and not path.name.startswith("_")

    def _process_file(
        self,
        file_path: Path,
        system_name: str,
        provider: Any,
        dat_db: Optional[Any],
        deep_scan: bool,
        stats: dict,
        found_paths: set,
        existing_entries: dict
    ):
        """Analisa, valida e persiste os metadados de um ficheiro individual."""
        abs_path = str(file_path.resolve())
        found_paths.add(abs_path)
        
        stat = file_path.stat()
        entry = existing_entries.get(abs_path)

        needs_hashing = self._check_needs_hashing(file_path, stat, entry, deep_scan)
        
        # Extração de Metadados via Provider
        metadata = self._extract_provider_metadata(file_path, provider)
        
        # Lógica de Hash e Match DAT
        hashes, match_info = self._handle_verification(
            file_path, entry, dat_db, needs_hashing, metadata
        )
        
        # Consolidação da Entrada
        status = match_info.get("status", entry.status if entry else "UNKNOWN")
        match_name = match_info.get("match_name", entry.match_name if entry else metadata.get("title"))
        dat_name = match_info.get("dat_name", entry.dat_name if entry else metadata.get("serial"))

        new_entry = LibraryEntry(
            path=abs_path,
            system=system_name,
            size=stat.st_size,
            mtime=stat.st_mtime,
            status=status,
            crc32=hashes.get("crc32"),
            md5=hashes.get("md5"),
            sha1=hashes.get("sha1"),
            match_name=match_name,
            dat_name=dat_name,
            extra_metadata=metadata
        )
        self.db.update_entry(new_entry)
        stats["added" if not entry else "updated"] += 1

    def _check_needs_hashing(self, path: Path, stat: Any, entry: Optional[LibraryEntry], deep_scan: bool) -> bool:
        """Determina se o ficheiro requer um novo cálculo de hash."""
        if deep_scan or not entry:
            return True
        return entry.size != stat.st_size or abs(entry.mtime - stat.st_mtime) >= 1.0

    def _extract_provider_metadata(self, path: Path, provider: Any) -> dict:
        """Extrai metadados binários via system provider."""
        if not provider:
            return {}
        try:
            return provider.extract_metadata(path)
        except Exception as e:
            self.logger.debug(f"Erro extração metadados para {path.name}: {e}")
            return {}

    def _handle_verification(
        self, 
        path: Path, 
        entry: Optional[LibraryEntry], 
        dat_db: Any, 
        needs_hashing: bool,
        metadata: dict
    ) -> tuple[dict, dict]:
        """Calcula hashes e procura correspondência na base de dados DAT."""
        hashes = {
            "crc32": entry.crc32 if entry else None,
            "md5": entry.md5 if entry else None,
            "sha1": entry.sha1 if entry else None
        }
        match_info = {}

        if needs_hashing and dat_db:
            self.logger.debug(f"Calculando hashes para {path.name}...")
            hashes = hasher.calculate_hashes(path, algorithms=("crc32", "sha1", "md5"))
            
            # Conexão da lógica de lookup (Rule 3 - Implementar lógica faltante sugestiva)
            matches = dat_db.lookup(crc=hashes.get("crc32"), sha1=hashes.get("sha1"), md5=hashes.get("md5"))
            if matches:
                match = matches[0]
                match_info = {
                    "status": "VERIFIED",
                    "match_name": match.name,
                    "dat_name": match.serial or match.name
                }
                self.logger.debug(f"Correspondência DAT encontrada: {match.name}")

        return hashes, match_info

    def _cleanup_removed_entries(self, existing_entries: dict, found_paths: set, stats: dict):
        """Remove da base de dados ficheiros que já não existem no sistema de ficheiros."""
        for path in existing_entries:
            if path not in found_paths:
                self.db.remove_entry(path)
                stats["removed"] += 1

        # 5. Cleanup de ficheiros removidos
        for path in existing_entries:
            if path not in found_paths:
                self.db.remove_entry(path)
                stats["removed"] += 1

        return stats

    def _build_entry(self, path: Path, system: str, metadata: dict) -> LibraryEntry:
        """Cria um objeto LibraryEntry a partir de um ficheiro e metadados."""
        stat = path.stat()
        return LibraryEntry(
            path=str(path.resolve()),
            system=system,
            size=stat.st_size,
            mtime=stat.st_mtime,
            status="KNOWN" if metadata.get("serial") else "UNKNOWN",
            match_name=metadata.get("title"),
            dat_name=metadata.get("serial"),
            extra_metadata=metadata
        )

