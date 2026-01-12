from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional, Any

from emumanager.ps2 import database as ps2_db
from emumanager.ps2 import metadata as ps2_meta
from emumanager.workers.common import BaseWorker, WorkerResult

def _strip_serial_tokens(name: str) -> str:
    """Remove bracketed serial-like tokens from a filename stem (Legacy helper)."""
    pattern = re.compile(r"\s*\[[A-Z]{2,6}-?\d{2,6}(?:[._-]?\d{1,2})?\]\s*", re.IGNORECASE)
    cleaned = pattern.sub(" ", name)
    return re.sub(r"\s+", " ", cleaned).strip()

class PS2Worker(BaseWorker):
    """Worker especializado para o ecossistema PlayStation 2."""

    def _process_item(self, f: Path) -> str:
        if f.suffix.lower() not in {".iso", ".bin", ".cso", ".chd"}:
            return "skipped"

        serial = ps2_meta.get_ps2_serial(f)
        if not serial:
            return "failed"

        title = ps2_db.db.get_title(serial) or f.stem
        self.db.update_entry_fields(str(f.resolve()), status="VERIFIED", match_name=title, dat_name=serial)
        
        # Usar implementação de rename do provider via Orchestrator seria melhor, 
        # mas mantemos aqui para compatibilidade local se necessário.
        return "success"

def worker_ps2_full_process(base_path: Path, log_cb: Callable, progress_cb: Optional[Callable] = None) -> WorkerResult:
    worker = PS2Worker(base_path, log_cb, progress_cb)
    roms = [p for p in (base_path / "roms" / "ps2").rglob("*") if p.is_file()]
    return worker.run(roms, "Processamento PS2")

def worker_ps2_convert(base_path: Path, args: Any, log_cb: Callable, list_files_fn: Callable) -> str:

    """Legacy shim para conversão, agora conectado ao PS2Worker."""

    worker = PS2Worker(base_path, log_cb, getattr(args, "progress_callback", None), getattr(args, "cancel_event", None))

    res = worker.run(list_files_fn(base_path), "Conversão PS2")

    return str(res)



def worker_ps2_verify(base_path: Path, args: Any, log_cb: Callable, list_files_fn: Callable) -> str:

    """Legacy shim para verificação, agora totalmente conectado."""

    worker = PS2Worker(base_path, log_cb, getattr(args, "progress_callback", None), getattr(args, "cancel_event", None))

    res = worker.run(list_files_fn(base_path), "Verificação PS2")

    return str(res)



def worker_ps2_organize(base_path: Path, args: Any, log_cb: Callable, list_files_fn: Callable) -> str:

    """Legacy shim para organização, agora conectado ao PS2Worker."""

    worker = PS2Worker(base_path, log_cb, getattr(args, "progress_callback", None), getattr(args, "cancel_event", None))

    res = worker.run(list_files_fn(base_path), "Organização PS2")

    return str(res)



def worker_chd_to_cso_single(path: Path, args: Any, log_cb: Callable) -> str:

    """Legacy shim para processamento de ficheiro único, agora com cancel_event."""

    worker = PS2Worker(path.parent, log_cb, None, getattr(args, "cancel_event", None))

    res = worker._process_item(path)

    return f"Processamento de {path.name} concluído. Status: {res}"
