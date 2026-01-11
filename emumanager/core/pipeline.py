from __future__ import annotations

import asyncio
import multiprocessing
import threading
import time
from pathlib import Path
from queue import Empty
from typing import Callable, Any, Iterable

from emumanager.logging_cfg import get_logger, set_correlation_id

class EnginePipeline:
    """
    Pipeline de Alta Vazão:
    1. Reader (Thread): Varre o disco e alimenta a fila.
    2. Workers (Processos): Processam CPU-bound (Hash/Compress).
    3. Metadata (Async): Processa IO-bound (Covers/API) em paralelo.
    """

    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or max(1, multiprocessing.cpu_count() - 1)
        self.input_queue = multiprocessing.JoinableQueue(maxsize=100)
        self.result_queue = multiprocessing.Queue()
        self.logger = get_logger("core.pipeline")
        self._stop_event = multiprocessing.Event()

    def _cpu_worker(self, base_path: Path, worker_cls: Any, mp_args: tuple):
        """Loop de execução do processo filho."""
        set_correlation_id()
        instance = worker_cls(base_path, lambda x: None, None, None, *mp_args)
        
        while not self._stop_event.is_set():
            try:
                item = self.input_queue.get(timeout=1)
                status = instance._process_item(item)
                self.result_queue.put((item, status))
                self.input_queue.task_done()
            except Empty:
                continue
            except Exception as e:
                self.logger.error(f"Erro no worker: {e}")

    async def _async_metadata_handler(self, orchestrator: Any):
        """Trata efeitos secundários (capas) via IO não-bloqueante."""
        while not self._stop_event.is_set() or not self.result_queue.empty():
            try:
                # Simulamos o consumo da fila de resultados para disparar downloads
                item, status = self.result_queue.get_nowait()
                if status == "success":
                    # Aqui dispararíamos o download assíncrono da capa
                    pass
            except Empty:
                await asyncio.sleep(0.1)

    def run(self, orchestrator: Any, items: Iterable[Path], worker_cls: Any, mp_args: tuple = ()):
        self.logger.info(f"Iniciando Pipeline com {self.max_workers} processos.")
        
        # 1. Iniciar Processos de CPU
        processes = []
        for _ in range(self.max_workers):
            p = multiprocessing.Process(
                target=self._cpu_worker, 
                args=(orchestrator.session.base_path, worker_cls, mp_args)
            )
            p.start()
            processes.append(p)

        # 2. Alimentar Fila (Produtor)
        start_time = time.perf_counter()
        for item in items:
            self.input_queue.put(item)

        # 3. Aguardar conclusão
        self.input_queue.join()
        self._stop_event.set()

        for p in processes:
            p.join()

        duration = time.perf_counter() - start_time
        self.logger.info(f"Pipeline finalizada em {duration:.2f}s.")
