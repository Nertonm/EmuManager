from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional, Any

from emumanager.psp import database as psp_db
from emumanager.psp import metadata as psp_meta
from emumanager.workers.common import BaseWorker, WorkerResult

class PSPWorker(BaseWorker):
    """Worker especializado para PSP com suporte a compressão CSO paralela."""

    def _process_item(self, f: Path) -> str:
        if f.suffix.lower() not in {".iso", ".cso", ".pbp"}:
            return "skipped"

        meta = psp_meta.get_metadata(f)
        serial = meta.get("serial")
        if not serial: return "failed"

        title = psp_db.db.get_title(serial) or meta.get("title", "Unknown")
        self.db.update_entry_fields(str(f.resolve()), status="VERIFIED", match_name=title, dat_name=serial)
        return "success"

def worker_psp_process(base_path: Path, log_cb: Callable, progress_cb: Optional[Callable] = None) -> WorkerResult:
    worker = PSPWorker(base_path, log_cb, progress_cb, None)
    roms = [p for p in (base_path / "roms" / "psp").rglob("*") if p.is_file()]
    return worker.run(roms, "PSP Process", parallel=True)
