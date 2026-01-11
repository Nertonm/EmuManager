from __future__ import annotations

from typing import Callable, Optional, Any
from pathlib import Path

from emumanager.workers.common import WorkerResult, worker_clean_junk
from emumanager.workers.scanner import worker_scan_library
from emumanager.workers.verification import worker_hash_verify
from emumanager.workers.ps2 import worker_ps2_full_process
from emumanager.workers.psx import worker_psx_process
from emumanager.workers.psp import worker_psp_process
from emumanager.workers.ps3 import worker_ps3_process
from emumanager.workers.n3ds import worker_n3ds_process
from emumanager.workers.switch import worker_switch_compress
from emumanager.workers.dolphin import worker_dolphin_compress

def worker_organize(base_path: Path, env: Any, args: Any, log_cb: Callable, list_files_fn: Callable, progress_cb: Optional[Callable] = None) -> str:
    # Tentar usar o Orchestrator se disponível via args
    orch = getattr(args, "orchestrator", None)
    if orch:
        res = orch.full_organization_flow(dry_run=getattr(args, "dry_run", False), progress_cb=progress_cb)
        return f"Organização concluída: {res}"
    
    # Fallback para o distributor simples
    from emumanager.workers.distributor import worker_distribute_root
    res = worker_distribute_root(base_path, log_cb, progress_cb)
    return f"Distribuição concluída (apenas pastas): {res}"

def _worker_system_organize(system_id: str, base_path: Path, args: Any, log_cb: Callable, progress_cb: Optional[Callable] = None) -> str:
    orch = getattr(args, "orchestrator", None)
    if not orch:
        return "Erro: Orchestrator não disponível para esta tarefa."
    
    res = orch.organize_names(system_id=system_id, dry_run=getattr(args, "dry_run", False), progress_cb=progress_cb)
    return f"Organização {system_id.upper()} concluída: {res}"

worker_ps2_organize = lambda bp, args, lcb, lfn, pcb=None: _worker_system_organize("ps2", bp, args, lcb, pcb)
worker_psx_organize = lambda bp, args, lcb, lfn, pcb=None: _worker_system_organize("psx", bp, args, lcb, pcb)
worker_ps3_organize = lambda bp, args, lcb, lfn, pcb=None: _worker_system_organize("ps3", bp, args, lcb, pcb)
worker_psp_organize = lambda bp, args, lcb, lfn, pcb=None: _worker_system_organize("psp", bp, args, lcb, pcb)
worker_n3ds_organize = lambda bp, args, lcb, lfn, pcb=None: _worker_system_organize("n3ds", bp, args, lcb, pcb)
worker_dolphin_organize = lambda bp, args, lcb, lfn, pcb=None: _worker_system_organize("gamecube", bp, args, lcb, pcb)

worker_health_check = _not_imp
worker_dolphin_decompress_single = _not_imp
worker_dolphin_recompress_single = _not_imp
worker_chd_decompress_single = _not_imp
worker_chd_recompress_single = _not_imp
worker_switch_decompress = _not_imp
worker_compress_single = _not_imp
worker_decompress_single = _not_imp
worker_recompress_single = _not_imp
worker_ps2_convert = _not_imp
worker_ps2_verify = _not_imp
worker_psx_convert = _not_imp
worker_psx_verify = _not_imp
worker_ps3_verify = _not_imp
worker_psp_verify = _not_imp
worker_psp_compress = _not_imp
worker_psp_compress_single = _not_imp
worker_n3ds_verify = _not_imp
worker_n3ds_compress = _not_imp
worker_n3ds_compress_single = _not_imp
worker_n3ds_decompress = _not_imp
worker_n3ds_decompress_single = _not_imp
worker_n3ds_convert_cia = _not_imp
worker_n3ds_decrypt = _not_imp
worker_dolphin_convert = _not_imp
worker_dolphin_convert_single = _not_imp
worker_dolphin_verify = _not_imp

DOLPHIN_CONVERTIBLE_EXTENSIONS = {".iso", ".gcm", ".wbfs"}

def worker_identify_single_file(file_path: Path, dat_path: Path, log_cb: Callable, progress_cb: Optional[Callable] = None) -> str:
    from emumanager.verification import dat_parser
    from emumanager.workers.verification import HashVerifyWorker
    try:
        db = dat_parser.parse_dat_file(dat_path)
        worker = HashVerifyWorker(file_path.parent, log_cb, progress_cb, None, db)
        return worker._process_item(file_path)
    except Exception as e:
        return f"Erro: {e}"

def worker_identify_all(target, args, log_cb, list_fn):
    return worker_hash_verify(target, args, log_cb, list_fn)

__all__ = [
    "worker_scan_library", "worker_hash_verify", "worker_identify_single_file", "worker_identify_all",
    "worker_ps2_full_process", "worker_psx_process", "worker_psp_process", "worker_ps3_process",
    "worker_n3ds_process", "worker_switch_compress", "worker_dolphin_compress", "worker_clean_junk",
    "worker_organize", "worker_health_check", "worker_compress_single", "worker_decompress_single",
    "worker_recompress_single", "worker_ps2_convert", "worker_ps2_verify", "worker_ps2_organize",
    "worker_psx_convert", "worker_psx_verify", "worker_psx_organize", "worker_ps3_verify",
    "worker_ps3_organize", "worker_psp_verify", "worker_psp_organize", "worker_psp_compress",
    "worker_psp_compress_single", "worker_n3ds_verify", "worker_n3ds_organize", "worker_n3ds_compress",
    "worker_n3ds_compress_single", "worker_n3ds_decompress", "worker_n3ds_decompress_single",
    "worker_n3ds_convert_cia", "worker_n3ds_decrypt", "worker_dolphin_convert", "worker_dolphin_convert_single",
    "worker_dolphin_verify", "worker_dolphin_organize", "worker_dolphin_decompress_single",
    "worker_dolphin_recompress_single", "DOLPHIN_CONVERTIBLE_EXTENSIONS", "worker_chd_decompress_single",
    "worker_chd_recompress_single", "worker_switch_decompress"
]