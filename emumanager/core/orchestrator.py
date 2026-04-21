from __future__ import annotations

from typing import Any, Optional

from emumanager.core.dat_manager import DATManager
from emumanager.core.integrity import IntegrityManager
from emumanager.core.multidisc import MultiDiscManager
from emumanager.core.scanner import Scanner
from emumanager.core.session import Session
from emumanager.library import LibraryDB
from emumanager.common.events import bus
from emumanager.common.exceptions import DatabaseError
from emumanager.logging_cfg import get_logger

from .orchestrator_library import OrchestratorLibraryMixin
from .orchestrator_maintenance import OrchestratorMaintenanceMixin
from .orchestrator_organization import OrchestratorOrganizationMixin


class Orchestrator(
    OrchestratorLibraryMixin,
    OrchestratorOrganizationMixin,
    OrchestratorMaintenanceMixin,
):
    """Core facade that coordinates high-level workflows through dedicated mixins."""

    def __init__(self, session: Session):
        """Inicializa o motor core com base numa sessão ativa."""
        self.session = session

        try:
            self.db = LibraryDB(self.session.base_path / "library.db")
        except Exception as e:
            raise DatabaseError(f"Failed to initialize database: {e}") from e

        self.logger = get_logger("core.orchestrator")
        self.dat_manager = DATManager(self.session.base_path / "dats")
        self.integrity = IntegrityManager(self.session.base_path, self.db)
        self.scanner = Scanner(self.db, dat_manager=self.dat_manager)
        self.multidisc = MultiDiscManager()

        self._start_time: Optional[float] = None
        self._items_processed = 0

    def get_telemetry(self) -> dict[str, Any]:
        """Retorna métricas de performance atuais."""
        import os
        import time

        elapsed = time.time() - self._start_time if self._start_time else 0
        speed = self._items_processed / elapsed if elapsed > 0 else 0

        mem = 0.0
        try:
            import psutil

            process = psutil.Process(os.getpid())
            mem = process.memory_info().rss / 1024 / 1024
        except ImportError:
            self.logger.debug("psutil not available, memory metrics disabled")
        except Exception as e:
            self.logger.warning(f"Failed to get memory metrics: {e}")

        return {
            "speed": f"{speed:.1f} it/s",
            "memory": f"{mem:.1f} MB",
            "uptime": f"{elapsed:.0f}s",
            "items_processed": self._items_processed,
        }

    def _emit_progress(self, percent: float, message: str):
        bus.emit("progress_update", percent=percent, message=message)

    def _emit_task_start(self, task_name: str):
        bus.emit("task_started", name=task_name)
