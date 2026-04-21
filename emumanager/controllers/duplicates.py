from __future__ import annotations

from typing import TYPE_CHECKING, Any

from emumanager import common as _common
from emumanager.workers import duplicates as _worker_duplicates

if TYPE_CHECKING:
    from emumanager.gui_main import MainWindowBase

from .duplicates_moves import DuplicatesMoveMixin
from .duplicates_scan import DuplicatesScanMixin
from .duplicates_view import DuplicatesViewMixin

worker_find_duplicates = _worker_duplicates.worker_find_duplicates
safe_move = _common.safe_move


class DuplicatesController(
    DuplicatesMoveMixin,
    DuplicatesScanMixin,
    DuplicatesViewMixin,
):
    def __init__(self, main_window: MainWindowBase):
        self.mw = main_window
        self.ui = main_window.ui
        self._groups: list[dict[str, Any]] = []
        self._current_group: dict[str, Any] | None = None
        self._connect_signals()

    def _connect_signals(self):
        if hasattr(self.ui, "btn_dups_scan"):
            self.ui.btn_dups_scan.clicked.connect(self.scan_duplicates)
        if hasattr(self.ui, "list_dups_groups"):
            self.ui.list_dups_groups.currentItemChanged.connect(self._on_group_selected)
        if hasattr(self.ui, "btn_dups_keep_largest"):
            self.ui.btn_dups_keep_largest.clicked.connect(
                lambda: self._auto_pick("largest")
            )
        if hasattr(self.ui, "btn_dups_keep_smallest"):
            self.ui.btn_dups_keep_smallest.clicked.connect(
                lambda: self._auto_pick("smallest")
            )
        if hasattr(self.ui, "btn_dups_open_location"):
            self.ui.btn_dups_open_location.clicked.connect(self._open_selected_location)
        if hasattr(self.ui, "btn_dups_move_others"):
            self.ui.btn_dups_move_others.clicked.connect(
                self._move_others_to_duplicates
            )
            self.ui.btn_dups_move_others.setEnabled(True)

    def _get_worker_find_duplicates(self):
        return globals()["worker_find_duplicates"]

    def _safe_move(self, *args, **kwargs):
        return globals()["safe_move"](*args, **kwargs)
