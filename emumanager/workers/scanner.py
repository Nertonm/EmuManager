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

    def scan(self) -> dict:
        set_correlation_id()
        roms_dir = self.base_path / "roms" if (self.base_path / "roms").exists() else self.base_path
        self.logger.info(f"Scanning library at {roms_dir}")
        
        existing_entries = {entry.path: entry for entry in self.db.get_all_entries()}
        found_paths = set()
        
        system_dirs = [d for d in roms_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
        total_systems = len(system_dirs)

        for i, sys_dir in enumerate(system_dirs):
            if self.cancel_event.is_set(): break
            
            system_name = sys_dir.name
            if self.progress_cb:
                self.progress_cb(i / total_systems, f"Scanning {system_name}...")

            for file_path in sys_dir.rglob("*"):
                if self.cancel_event.is_set(): break
                if not file_path.is_file() or file_path.name.startswith("."): continue
                
                str_path = str(file_path.resolve())
                found_paths.add(str_path)
                
                stat = file_path.stat()
                entry = existing_entries.get(str_path)
                
                if entry and entry.size == stat.st_size and abs(entry.mtime - stat.st_mtime) < 1.0:
                    continue

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

        # Cleanup
        for path in existing_entries:
            if path not in found_paths:
                self.db.remove_entry(path)
                self.stats["skipped"] += 1

        if self.progress_cb: self.progress_cb(1.0, "Scan complete")
        return self.stats

def worker_scan_library(base_dir: Path, log_msg: Callable[[str], None], progress_cb: Optional[Callable[[float, str], None]] = None, cancel_event=None):
    worker = ScannerWorker(base_dir, log_msg, progress_cb, cancel_event)
    return worker.scan()