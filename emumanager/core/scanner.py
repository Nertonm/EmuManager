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
        stats = {"added": 0, "updated": 0, "removed": 0, "skipped": 0, "verified": 0}
        
        if not root.exists():
            return stats

        existing_entries = {e.path: e for e in self.db.get_all_entries()}
        found_paths = set()

        # 1. Listar pastas de sistema
        systems = [d for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")]
        total_systems = len(systems)

        for i, sys_dir in enumerate(systems):
            if cancel_event and cancel_event.is_set(): break
            
            system_name = sys_dir.name
            provider = registry.get_provider(system_name)
            
            # Carregar DAT para este sistema se disponível
            dat_db = None
            if self.dat_manager:
                dat_path = self.dat_manager.find_dat_for_system(system_name)
                if dat_path:
                    try:
                        dat_db = dat_parser.parse_dat_file(dat_path)
                        self.logger.info(f"DAT carregado para {system_name}: {dat_path.name}")
                    except Exception as e:
                        self.logger.warning(f"Erro ao carregar DAT para {system_name}: {e}")

            if progress_cb:
                progress_cb(i / total_systems, f"Scanning {system_name}...")

            # 2. Varrer ficheiros do sistema
            for file_path in sys_dir.rglob("*"):
                if cancel_event and cancel_event.is_set(): break
                # Ignoramos ficheiros ocultos ou de metadados internos (_)
                if not file_path.is_file() or file_path.name.startswith(".") or file_path.name.startswith("_"):
                    continue


                abs_path = str(file_path.resolve())
                found_paths.add(abs_path)
                
                stat = file_path.stat()
                entry = existing_entries.get(abs_path)

                # Verificar se o ficheiro mudou
                needs_hashing = deep_scan
                if not entry or entry.size != stat.st_size or abs(entry.mtime - stat.st_mtime) >= 1.0:
                    needs_hashing = True

                # Extração de Metadados via Provider (Serial/Title)
                metadata = {}
                if provider:
                    try:
                        metadata = provider.extract_metadata(file_path)
                    except Exception:
                        pass

                # 3. Verificação DAT (Opcional, se houver DAT e o ficheiro mudou)
                status = entry.status if entry else "UNKNOWN"
                match_name = entry.match_name if entry else metadata.get("title")
                dat_name = entry.dat_name if entry else metadata.get("serial")
                
                hashes = {
                    "crc32": entry.crc32 if entry else None,
                    "md5": entry.md5 if entry else None,
                    "sha1": entry.sha1 if entry else None
                }

                if needs_hashing and dat_db:
                    # Calcular hashes apenas se necessário
                    self.logger.debug(f"Calculando hashes para {file_path.name}...")
                    hashes = hasher.calculate_hashes(file_path, algorithms=("crc32", "sha1", "md5"))
                    
                    # ... lógica de lookup DAT ...
                    
                # 4. Verificação RetroAchievements (Opcional)
                ra_status = {}
                if status == "VERIFIED" and hashes.get("md5"):
                    # Aqui assumimos que o extra_metadata do provider pode conter um game_id do RA
                    # No futuro, o MatchEngine pode retornar o ID do RA
                    pass 

                # 5. Atualizar Base de Dados

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

