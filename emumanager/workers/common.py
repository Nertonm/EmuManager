from __future__ import annotations

import abc
import hashlib
import logging
import threading
import time
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, TypeVar

from emumanager.library import LibraryDB
from emumanager.logging_cfg import get_correlation_id, set_correlation_id, get_logger

@dataclass(slots=True)
class WorkerResult:
    """Objeto de retorno estruturado para operações de workers."""
    task_name: str
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    slowest_items: list[tuple[str, float]] = field(default_factory=list) # (nome, segundos)
    processed_items: list[dict[str, Any]] = field(default_factory=list) # Detalhes para o relatório
    duration_ms: float = 0.0

    def add_item_result(self, path: Path, status: str, duration: float, original_size: int = 0, final_size: int = 0, system: str = "Unknown"):
        """Regista o resultado individual de um item para o relatório HTML."""
        self.processed_items.append({
            "name": path.name,
            "system": system,
            "status": status,
            "duration": f"{duration:.2f}s",
            "original_size": original_size,
            "final_size": final_size,
            "savings": f"{(1 - (final_size/original_size))*100:.1f}%" if final_size and original_size else "0%"
        })
        self.add_timing(path, duration)

    def add_timing(self, path: Path, duration: float):
        """Regista o tempo de processamento de um item."""
        self.slowest_items.append((path.name, duration))
        self.slowest_items.sort(key=lambda x: x[1], reverse=True)
        self.slowest_items = self.slowest_items[:10]

    def add_error(self, path: Path, message: str):
        """Regista um erro ocorrido num item."""
        self.failed_count += 1
        self.errors.append({"file": path.name, "message": message})

    def __getitem__(self, key: str) -> Any:
        """Permite acesso estilo dicionário para compatibilidade legada."""
        mapping = {
            "renamed": self.success_count,
            "errors": self.failed_count,
            "skipped": self.skipped_count,
            "success": self.success_count,
            "failed": self.failed_count
        }
        if key in mapping:
            return mapping[key]
        return getattr(self, key)




    def __str__(self) -> str:
        return (f"{self.task_name} concluído em {self.duration_ms:.2f}ms. "
                f"Sucesso: {self.success_count}, Falhas: {self.failed_count}, "
                f"Ignorados: {self.skipped_count}")

def _mp_worker_init(cid: str | None):
    """Inicializador para processos filhos."""
    set_correlation_id(cid)

class BaseWorker(abc.ABC):
    """Motor de execução para tarefas em lote com suporte a Multiprocessing."""

    def __init__(
        self, 
        base_path: Path, 
        log_cb: Callable[[str], None], 
        progress_cb: Optional[Callable[[float, str], None]] = None, 
        cancel_event: Optional[threading.Event] = None
    ):
        self.base_path = Path(base_path).resolve()
        self.log_cb = log_cb
        self.progress_cb = progress_cb
        self.cancel_event = cancel_event or threading.Event()
        self.logger = get_logger(self.__class__.__name__)
        self.db = LibraryDB()
        self._result = WorkerResult(task_name=self.__class__.__name__)

    def run(self, items: Iterable[Path], task_label: str = "Processando", parallel: bool = False, mp_args: tuple = ()) -> WorkerResult:
        """Executa a tarefa. Se 'parallel' for True, usa múltiplos núcleos."""
        start_time = time.perf_counter()
        set_correlation_id()
        
        item_list = list(items)
        total = len(item_list)
        if total == 0:
            return self._result

        self.logger.info(f"Iniciando {task_label} ({'PARALELO' if parallel else 'SEQUENCIAL'}) em {total} itens.")

        if parallel:
            self._run_parallel(item_list, task_label, mp_args)
        else:
            self._run_sequential(item_list, task_label)

        self._result.duration_ms = (time.perf_counter() - start_time) * 1000
        if self.progress_cb:
            self.progress_cb(1.0, f"{task_label} Finalizado")
            
        return self._result

    def _run_sequential(self, items: list[Path], label: str):
        total = len(items)
        for i, item in enumerate(items):
            if self.cancel_event.is_set(): break
            if self.progress_cb and total > 0:
                self.progress_cb(i / total, f"{label}: {item.name}")
            
            start_item = time.perf_counter()
            try:
                status = self._process_item(item)
                self._update_stats(status)
                self._result.add_timing(item, time.perf_counter() - start_item)
            except Exception as e:
                self._result.add_error(item, str(e))


    def _run_parallel(self, items: list[Path], label: str, mp_args: tuple):
        total = len(items)
        max_workers = max(1, multiprocessing.cpu_count() - 1)
        
        with ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=_mp_worker_init,
            initargs=(get_correlation_id(),)
        ) as executor:
            futures = {executor.submit(self.__class__._dispatch_mp, self.base_path, item, *mp_args): item for item in items}
            
            for i, future in enumerate(as_completed(futures)):
                if self.cancel_event.is_set():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                
                item = futures[future]
                if self.progress_cb and total > 0:
                    self.progress_cb(i / total, f"{label}: {item.name}")
                
                try:
                    status, duration = future.result()
                    self._update_stats(status)
                    self._result.add_timing(item, duration)
                except Exception as e:
                    self._result.add_error(item, str(e))

    @classmethod
    def _dispatch_mp(cls, base_path: Path, item: Path, *args) -> tuple[str, float]:
        """Ponto de entrada estático para o processo filho."""
        start = time.perf_counter()
        # Inicializar sem cancel_event pois não é serializável
        instance = cls(base_path, lambda x: None, None, None)
        status = instance._process_item(item)
        return status, time.perf_counter() - start


    def _update_stats(self, status: str):
        if status == "success": self._result.success_count += 1
        elif status == "skipped": self._result.skipped_count += 1
        else: self._result.failed_count += 1

    @abc.abstractmethod
    def _process_item(self, item: Path) -> str:
        """Processa um item individual. Deve ser implementado por subclasses."""
        raise NotImplementedError("Subclasses must implement _process_item")

    def safe_hash(self, path: Path, algo: str = "sha1") -> str | None:
        try:
            h = hashlib.new(algo)
            with path.open("rb") as f:
                while chunk := f.read(256 * 1024):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return None

    def atomic_move(self, src: Path, dst: Path) -> bool:
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.replace(dst)
            return True
        except Exception:
            return False

class GuiLogger:
    """Wrapper para encaminhar logs para o callback de log da GUI."""
    def __init__(self, log_cb: Callable[[str], None]):
        self.log_cb = log_cb
    def info(self, msg: str, *args): self.log_cb(msg % args if args else msg)
    def warning(self, msg: str, *args): self.log_cb(f"WARN: {msg % args if args else msg}")
    def error(self, msg: str, *args): self.log_cb(f"ERROR: {msg % args if args else msg}")
    def debug(self, msg: str, *args): 
        # Debug messages are ignored in GUI to keep log clean
        pass
    def exception(self, msg: str, *args): self.log_cb(f"EXCEPTION: {msg % args if args else msg}")

def get_logger_for_gui(log_cb: Callable[[str], None], name: str = "gui") -> logging.Logger:
    """Retorna um logger configurado para enviar mensagens para a GUI."""
    logger_instance = logging.getLogger(name)
    class GuiHandler(logging.Handler):
        def emit(self, record):
            log_cb(self.format(record))
    handler = GuiHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger_instance.addHandler(handler)
    logger_instance.setLevel(logging.INFO)
    return logger_instance

def find_tool(name: str) -> Optional[Path]:
    from emumanager.common.execution import find_tool as _ft
    return _path_resolve(_ft(name))

def _path_resolve(p: Optional[Path]) -> Optional[Path]:
    return p.resolve() if p and p.exists() else p

def calculate_file_hash(path: Path, algo: str = "sha1", chunk_size: int = 1024 * 1024, progress_cb: Optional[Callable[[float], None]] = None) -> str:
    from emumanager.verification.hasher import calculate_hashes
    # Simulação de progresso se progress_cb for passado
    if progress_cb: progress_cb(0.5) # Simplificado
    res = calculate_hashes(path, algorithms=(algo,), chunk_size=chunk_size)
    if progress_cb: progress_cb(1.0)
    return res.get(algo, "")

def create_file_progress_cb(main_cb: Callable, start: float, end: float, name: str) -> Callable:
    def _cb(p: float):
        pct = start + (p * (end - start))
        main_cb(pct, f"Processando {name}...")
    return _cb

def find_target_dir(base: Path, candidates: list[str]) -> Optional[Path]:
    for c in candidates:
        p = base / c
        if p.is_dir(): return p
    return None

def emit_verification_result(cb: Callable, **kwargs):
    if cb: cb(SimpleNamespace(**kwargs))

def verify_chd(path: Path) -> bool:
    from emumanager.common.execution import run_cmd
    chdman = find_tool("chdman")
    if not chdman: return False
    try:
        res = run_cmd([str(chdman), "verify", "-i", str(path)], timeout=60)
        return res.returncode == 0 or "verify ok" in (getattr(res, "stdout", "") or "").lower()
    except Exception: return False

def skip_if_compressed(path: Path, logger: logging.Logger, db: Optional[LibraryDB] = None) -> bool:
    if db is None:
        db = LibraryDB()
    entry = db.get_entry(str(path.resolve()))
    if entry and entry.status == "COMPRESSED":
        logger.info(f"Pular (já comprimido): {path.name}")
        db.log_action(str(path), "SKIP_COMPRESSED", "Skipped by worker")
        return True
    return False

def worker_clean_junk(base_path: Path, args: Any, log_cb: Callable[[str], None], list_files_fn: Callable, list_dirs_fn: Callable) -> str:
    """Legacy entry point para clean junk."""
    set_correlation_id()
    from emumanager.logging_cfg import get_logger
    logger = get_logger("worker.clean_junk")
    files = list_files_fn(base_path)
    
    # Inicializar conexão com banco de dados
    db = LibraryDB()
    
    count = 0
    junk_exts = {".txt", ".nfo", ".url", ".lnk", ".website"}
    for f in files:
        if f.suffix.lower() in junk_exts:
            if not getattr(args, "dry_run", False):
                try:
                    f.unlink(missing_ok=True)
                    # Remover do banco de dados também
                    try:
                        db.remove_entry(str(f.resolve()))
                        db.log_action(str(f.resolve()), "DELETED", "Removed junk file")
                    except Exception as e:
                        logger.debug(f"DB cleanup failed for {f}: {e}")
                except Exception as e:
                    logger.debug(f"Failed to delete junk file {f}: {e}")
            count += 1
            
    # Deletar pastas vazias
    dirs = list_dirs_fn(base_path)
    # Ordenar por profundidade (reversa)
    for d in sorted(dirs, key=lambda x: len(x.parts), reverse=True):
        try:
            if not any(d.iterdir()) and not getattr(args, "dry_run", False):
                d.rmdir()
        except Exception as e:
            logger.debug(f"Failed to remove empty directory {d}: {e}")
        
    return f"Limpeza concluída. {count} ficheiros removidos."
from types import SimpleNamespace

