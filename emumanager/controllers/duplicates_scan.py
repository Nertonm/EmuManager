from __future__ import annotations

from typing import TYPE_CHECKING, Any

from emumanager.common.formatting import human_readable_size

if TYPE_CHECKING:
    from emumanager.gui_main import MainWindowBase


class DuplicatesScanMixin:
    mw: "MainWindowBase"
    ui: Any
    _groups: list[dict[str, Any]]
    _current_group: dict[str, Any] | None

    def _update_dups_summary(self, result: dict):
        total_groups = int(result.get("total_groups", 0))
        total_items = int(result.get("total_items", 0))
        wasted = int(result.get("wasted_bytes", 0))

        if hasattr(self.ui, "lbl_dups_summary"):
            wasted_mb = wasted / 1024 / 1024
            self.ui.lbl_dups_summary.setText(
                f"Groups: {total_groups} | Items: {total_items} | Wasted: {wasted_mb:.1f} MB"
            )

    def _add_group_list_item(self, group: dict):
        kind = group.get("kind", "?")
        count = group.get("count", 0)
        wasted = int(group.get("wasted_bytes", 0))
        key = str(group.get("key", ""))
        key_short = key if len(key) <= 18 else f"{key[:18]}…"
        text = f"[{kind}] x{count} wasted {human_readable_size(wasted)} - {key_short}"

        item = self.mw._qtwidgets.QListWidgetItem(text)
        item.setToolTip(key)
        self.ui.list_dups_groups.addItem(item)

    def scan_duplicates(self):
        if not self.mw._last_base:
            self.mw.log_msg("Please select a base directory first (Open Library).")
            return

        include_name = True
        if hasattr(self.ui, "chk_dups_include_name"):
            include_name = bool(self.ui.chk_dups_include_name.isChecked())

        filter_non_games = True
        if hasattr(self.ui, "chk_dups_filter_non_games"):
            filter_non_games = bool(self.ui.chk_dups_filter_non_games.isChecked())

        self.ui.list_dups_groups.clear()
        self._groups = []
        self._current_group = None
        self._clear_entries_table()
        self.mw.log_msg("Scanning duplicates...")

        progress_cb = self.mw._signaler.progress_signal.emit if self.mw._signaler else None

        def _work():
            return self._get_worker_find_duplicates()(
                db=self.mw.library_db,
                log_cb=self.mw.log_msg,
                progress_cb=progress_cb,
                cancel_event=self.mw._cancel_event,
                include_name=include_name,
                filter_non_games=filter_non_games,
            )

        def _done(result):
            if isinstance(result, Exception):
                self.mw.log_msg(f"Duplicate scan error: {result}")
                return

            self._groups = result.get("groups", [])
            self._update_dups_summary(result)
            for group in self._groups:
                self._add_group_list_item(group)

        self.mw._run_in_background(_work, _done)
