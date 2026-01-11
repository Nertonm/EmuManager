from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

from emumanager.library import LibraryDB, LibraryEntry
from emumanager.workers.common import BaseWorker, set_correlation_id

ARCHIVE_EXTS = {".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz", ".tgz", ".tbz2"}

def is_compressed_file(p: Path) -> bool:
    return any(suffix.lower() in ARCHIVE_EXTS for suffix in p.suffixes)

class ScannerWorker(BaseWorker):
    def _process_file(self, f: Path) -> str:
        # A lógica do scanner é um pouco diferente da BaseWorker padrão
        # pois ele decide se deve atualizar ou não.
        return "success"

    def _resolve_roms_dir(self) -> Path:
        """Determina a diretoria raiz para o scan."""
        roms_path = self.base_path / "roms"
        return roms_path if roms_path.exists() else self.base_path

    def _cleanup_missing_files(self, existing_entries: dict, found_paths: set):
        """Remove entradas órfãs da base de dados."""
        for path in existing_entries:
            if path not in found_paths:
                try:
                    self.db.remove_entry(path)
                    self.stats["skipped"] += 1
                except Exception as e:
                    self.logger.error(f"Erro ao remover entrada órfã {path}: {e}")

    def _scan_single_file(self, file_path: Path, system_name: str, existing_entries: dict, found_paths: set):
        """Analisa um ficheiro individual e atualiza a base de dados se necessário."""
        str_path = str(file_path.resolve())
        found_paths.add(str_path)
        
        try:
            stat = file_path.stat()
            entry = existing_entries.get(str_path)
            
            # Skip se o ficheiro não mudou (performance optimization)
            if entry and entry.size == stat.st_size and abs(entry.mtime - stat.st_mtime) < 1.0:
                return

            status = "COMPRESSED" if is_compressed_file(file_path) else (entry.status if entry else "UNKNOWN")
            if status == "COMPRESSED":
                self.logger.info(f"Compressed file detected: {file_path.name}")

            new_entry = LibraryEntry(
                path=str_path,
                system=system_name,
                size=stat.st_size,
                mtime=stat.st_mtime,
                status=status,
                crc32=entry.crc32 if entry else None,
                md5=entry.md5 if entry else None,
                sha1=entry.sha1 if entry else None,
                match_name=entry.match_name if entry else None,
                dat_name=entry.dat_name if entry else None,
            )
            self.db.update_entry(new_entry)
            self.stats["success"] += 1
        except Exception as e:
            self.logger.error(f"Erro ao processar ficheiro {file_path}: {e}")

    def _process_system_directory(self, sys_dir: Path, existing_entries: dict, found_paths: set):
        """Varre recursivamente os ficheiros de um sistema."""
        system_name = sys_dir.name
        for file_path in sys_dir.rglob("*"):
            if self.cancel_event.is_set():
                break
            if file_path.is_file() and not file_path.name.startswith("."):
                self._scan_single_file(file_path, system_name, existing_entries, found_paths)

    def scan(self) -> dict:
        """Workflow mestre de auditoria de ficheiros."""
        set_correlation_id()
        roms_dir = self._resolve_roms_dir()
        self.logger.info(f"Scanning library at {roms_dir}")
        
        existing_entries = {entry.path: entry for entry in self.db.get_all_entries()}
        found_paths = set()
        
        system_dirs = [d for d in roms_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
        total_systems = len(system_dirs)

        for i, sys_dir in enumerate(system_dirs):
            if self.cancel_event.is_set():
                break
            
            if self.progress_cb:
                self.progress_cb(i / total_systems, f"Scanning {sys_dir.name}...")
            
            self._process_system_directory(sys_dir, existing_entries, found_paths)

        self._cleanup_missing_files(existing_entries, found_paths)

        if self.progress_cb:
            self.progress_cb(1.0, "Scan complete")
        return self.stats

def worker_scan_library(base_dir: Path, log_msg: Callable[[str], None], progress_cb: Optional[Callable[[float, str], None]] = None, cancel_event=None):
    worker = ScannerWorker(base_dir, log_msg, progress_cb, cancel_event)
    return worker.scan()