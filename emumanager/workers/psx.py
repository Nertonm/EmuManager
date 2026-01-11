from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional, Any

from emumanager.psx import database as psx_db
from emumanager.psx import metadata as psx_meta
from emumanager.workers.common import BaseWorker, WorkerResult

class PSXWorker(BaseWorker):
    """Worker especializado para o ecossistema PlayStation 1."""

    def _process_item(self, f: Path) -> str:
        if f.suffix.lower() not in {".bin", ".cue", ".iso", ".chd", ".img"}:
            return "skipped"

        src = f
        if f.suffix.lower() == ".cue":
            bin_p = f.with_suffix(".bin")
            if bin_p.exists(): src = bin_p

        serial = psx_meta.get_psx_serial(src)
        if not serial: return "failed"

        title = psx_db.db.get_title(serial) or f.stem
        self.db.update_entry_fields(str(f.resolve()), status="VERIFIED", match_name=title, dat_name=serial)
        return "success"

def worker_psx_process(base_path: Path, log_cb: Callable, progress_cb: Optional[Callable] = None) -> WorkerResult:
    worker = PSXWorker(base_path, log_cb, progress_cb, None)
    roms = [p for p in (base_path / "roms" / "psx").rglob("*") if p.is_file()]
    return worker.run(roms, "PS1 Process", parallel=True)