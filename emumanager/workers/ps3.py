from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional, Any

from emumanager.ps3 import database as ps3_db
from emumanager.ps3 import metadata as ps3_meta
from emumanager.workers.common import BaseWorker, WorkerResult

PARAM_SFO = "PARAM.SFO"

class PS3Worker(BaseWorker):
    """Worker PS3: Suporta ISOs e Pastas JB em paralelo."""

    def _process_item(self, f: Path) -> str:
        # Deteção de Jogo PS3 (Ficheiro ou Pasta JB)
        is_jb = f.is_dir() and ((f / PARAM_SFO).exists() or (f / "PS3_GAME" / PARAM_SFO).exists())
        if not (f.suffix.lower() in {".iso", ".pkg"} or is_jb):
            return "skipped"

        meta = ps3_meta.get_metadata(f)
        serial = meta.get("serial")
        if not serial: return "failed"

        title = ps3_db.db.get_title(serial) or meta.get("title", "Unknown")
        self.db.update_entry_fields(str(f.resolve()), status="VERIFIED", match_name=title, dat_name=serial)
        
        return "success"

def worker_ps3_process(base_path: Path, log_cb: Callable, progress_cb: Optional[Callable] = None) -> WorkerResult:
    worker = PS3Worker(base_path, log_cb, progress_cb, None)
    target = base_path / "roms" / "ps3"
    # Inclui pastas de primeiro nível para JB format
    items = list(target.iterdir()) 
    return worker.run(items, "PS3 Verify", parallel=True)
