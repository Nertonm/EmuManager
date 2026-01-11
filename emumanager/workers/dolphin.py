from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional, Any

from emumanager.converters import dolphin_converter
from emumanager.workers.common import BaseWorker, WorkerResult

class DolphinWorker(BaseWorker):
    """Worker Dolphin: Compressão RVZ paralela para GC e Wii."""

    def _process_item(self, f: Path) -> str:
        if f.suffix.lower() not in {".iso", ".gcm", ".wbfs"}:
            return "skipped"

        target = f.with_suffix(".rvz")
        if target.exists(): return "skipped"

        try:
            if dolphin_converter.convert_to_rvz(f, target):
                self.db.update_entry_fields(str(target.resolve()), status="COMPRESSED")
                return "success"
            return "failed"
        except Exception:
            return "failed"

def worker_dolphin_compress(base_path: Path, log_cb: Callable, progress_cb: Optional[Callable] = None) -> WorkerResult:
    worker = DolphinWorker(base_path, log_cb, progress_cb, None)
    roms = []
    for sys in ["gamecube", "wii"]:
        path = base_path / "roms" / sys
        if path.exists(): roms.extend(path.rglob("*"))
    return worker.run([r for r in roms if r.is_file()], "Dolphin Process", parallel=True)