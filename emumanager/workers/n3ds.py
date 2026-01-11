from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional, Any

from emumanager.n3ds import database as n3ds_db
from emumanager.n3ds import metadata as n3ds_meta
from emumanager.workers.common import BaseWorker, WorkerResult

class N3DSWorker(BaseWorker):
    """Worker para 3DS: Identificação e Conversão paralela."""

    def _process_item(self, f: Path) -> str:
        if f.suffix.lower() not in {".3ds", ".cia", ".3dz"}:
            return "skipped"

        meta = n3ds_meta.get_metadata(f)
        serial = meta.get("serial")
        if not serial: return "failed"

        title = n3ds_db.db.get_title(serial) or meta.get("title", "Unknown")
        self.db.update_entry_fields(str(f.resolve()), status="VERIFIED", match_name=title, dat_name=serial)
        return "success"

def worker_n3ds_process(base_path: Path, log_cb: Callable, progress_cb: Optional[Callable] = None) -> WorkerResult:
    worker = N3DSWorker(base_path, log_cb, progress_cb, None)
    roms = [p for p in (base_path / "roms" / "3ds").rglob("*") if p.is_file()]
    return worker.run(roms, "3DS Process", parallel=True)