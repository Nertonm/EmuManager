"""
Cockpit TUI v5.5 - Achievements & Intelligence Edition.
Explorador de Biblioteca, Inspector de Metadados, Telemetria e RetroAchievements.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from emumanager.application import (
    CollectionReportService,
    LibraryInsightsService,
    RomBrowserRow,
)
from textual.app import App

from .manager import get_orchestrator
from .core.config_manager import ConfigManager
from .tui_components import TUI_BINDINGS, TUI_CSS
from .tui_layout import TuiLayoutMixin
from .tui_library import TuiLibraryMixin
from .tui_workflows import TuiWorkflowMixin

# --- App Principal ---

class AsyncFeedbackTui(
    TuiLayoutMixin,
    TuiLibraryMixin,
    TuiWorkflowMixin,
    App,
):
    TITLE = "EmuManager Cockpit v5.5"
    CSS = TUI_CSS
    BINDINGS = TUI_BINDINGS

    MAX_LOG_LINES = 1000  # Limite para evitar crescimento infinito

    def __init__(self, base: Path) -> None:
        super().__init__()
        self.config_mgr = ConfigManager()
        configured_base = base or self.config_mgr.get("base_dir")
        self.base = Path(configured_base).resolve()
        self.orchestrator = get_orchestrator(self.base)
        self.library_insights = LibraryInsightsService(self.orchestrator.db)
        self.collection_reports = CollectionReportService(self.orchestrator.db)
        self.cancel_event = threading.Event()
        self._dry_run = False
        self._workflow_in_progress = False
        self._sys_id_map: dict[str, str] = {}
        self._rom_path_map: dict[str, str] = {}
        self._loaded_rom_rows: list[RomBrowserRow] = []
        self._selected_system: Optional[str] = None
        self._selected_rom_path: Optional[str] = None

def main():
    cm = ConfigManager()
    app = AsyncFeedbackTui(Path(cm.get("base_dir")))
    app.run()

if __name__ == "__main__":
    main()
