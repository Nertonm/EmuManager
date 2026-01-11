from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Optional

from emumanager.common.models import VerifyReport, VerifyResult
from emumanager.library import LibraryDB, LibraryEntry
from emumanager.verification import dat_parser, hasher
from emumanager.verification.dat_manager import find_dat_for_system
from emumanager.workers.common import BaseWorker, WorkerResult, set_correlation_id

class HashVerifyWorker(BaseWorker):
    """Worker especializado em verificação de integridade via DAT com Multiprocessing."""

    def __init__(self, base_path: Path, log_cb: Callable, progress_cb: Optional[Callable], cancel_event: Any, dat_db: dat_parser.DatDb):
        super().__init__(base_path, log_cb, progress_cb, cancel_event)
        self.dat_db = dat_db

    def _process_item(self, f: Path) -> str:
        abs_path = str(f.resolve())
        entry = self.db.get_entry(abs_path)
        stat = f.stat()
        
        if entry and entry.size == stat.st_size and abs(entry.mtime - stat.st_mtime) < 1.0:
            if entry.sha1 or entry.crc32:
                return self._lookup_and_save(f, entry.crc32, entry.md5, entry.sha1)

        algos = ("crc32", "md5", "sha1")
        hashes = hasher.calculate_hashes(f, algorithms=algos)
        
        return self._lookup_and_save(
            f, 
            hashes.get("crc32"), 
            hashes.get("md5"), 
            hashes.get("sha1")
        )

    def _lookup_and_save(self, f: Path, crc: str | None, md5: str | None, sha1: str | None) -> str:
        matches = self.dat_db.lookup(crc=crc, md5=md5, sha1=sha1)
        match = matches[0] if matches else None
        
        status = "VERIFIED" if match else "UNKNOWN"
        match_name = match.game_name if match else None
        
        self.db.update_entry_fields(
            str(f.resolve()),
            status=status,
            match_name=match_name,
            crc32=crc,
            md5=md5,
            sha1=sha1
        )
        return "success" if match else "skipped"

    @classmethod
    def _dispatch_mp(cls, base_path: Path, item: Path, dat_db: Any) -> str:
        instance = cls(base_path, lambda x: None, None, None, dat_db)
        return instance._process_item(item)

def worker_hash_verify(
    base_path: Path,
    args: Any,
    log_cb: Callable[[str], None],
    list_files_fn: Callable[[Path], list[Path]],
) -> VerifyReport:
    set_correlation_id()
    dat_root = getattr(args, "dats_root", base_path / "dats")
    dat_path = find_dat_for_system(Path(dat_root), base_path.name)
    
    if not dat_path or not dat_path.exists():
        return VerifyReport(text="Erro: DAT não encontrado.")

    dat_db = dat_parser.parse_dat_file(dat_path)
    worker = HashVerifyWorker(base_path, log_cb, getattr(args, "progress_callback", None), getattr(args, "cancel_event", None), dat_db)
    
    files = list_files_fn(base_path)
    result = worker.run(files, task_label="Verificação DAT", parallel=True, mp_args=(dat_db,))
    return VerifyReport(text=str(result))
