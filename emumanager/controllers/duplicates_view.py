from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from emumanager.common.formatting import human_readable_size

if TYPE_CHECKING:
    from emumanager.gui_main import MainWindowBase


class _QtConstants:
    def __init__(self, enum, core):
        self.enum = enum
        self.core = core

    @property
    def checked(self):
        return self.enum.CheckState.Checked if self.enum else self.core.Qt.Checked

    @property
    def unchecked(self):
        return self.enum.CheckState.Unchecked if self.enum else self.core.Qt.Unchecked

    @property
    def item_is_user_checkable(self):
        if self.enum:
            return self.enum.ItemFlag.ItemIsUserCheckable
        return self.core.Qt.ItemIsUserCheckable

    @property
    def user_role(self):
        if self.enum and hasattr(self.enum, "ItemDataRole"):
            return self.enum.ItemDataRole.UserRole
        return self.core.Qt.UserRole if self.core else 256

    def alignment(self):
        if self.core:
            return self.core.Qt.AlignRight | self.core.Qt.AlignVCenter
        if self.enum:
            return self.enum.AlignmentFlag.AlignRight | self.enum.AlignmentFlag.AlignVCenter
        return None


class DuplicatesViewMixin:
    mw: "MainWindowBase"
    ui: Any
    _groups: list[dict[str, Any]]
    _current_group: dict[str, Any] | None

    def _get_qt_constants(self) -> _QtConstants:
        return _QtConstants(
            getattr(self.mw, "_Qt_enum", None),
            getattr(self.mw, "_qtcore", None),
        )

    def _on_group_selected(self, current, previous=None):
        del previous
        if not current:
            self._current_group = None
            self._clear_entries_table()
            return

        row = self.ui.list_dups_groups.currentRow()
        if row < 0 or row >= len(self._groups):
            self._current_group = None
            self._clear_entries_table()
            return

        self._current_group = self._groups[row]
        self._render_group(self._current_group)

    def _clear_entries_table(self):
        if hasattr(self.ui, "table_dups_entries"):
            self.ui.table_dups_entries.setRowCount(0)

    def _create_table_entry_items(self, entry: dict, row: int):
        qt = self._get_qt_constants()

        check_item = self.mw._qtwidgets.QTableWidgetItem("")
        try:
            check_item.setFlags(check_item.flags() | qt.item_is_user_checkable)
            check_item.setCheckState(qt.unchecked)
        except Exception as exc:
            logging.debug(f"Failed to set check flags: {exc}")

        system_item = self.mw._qtwidgets.QTableWidgetItem(str(entry.get("system", "")))
        file_item = self.mw._qtwidgets.QTableWidgetItem(Path(entry.get("path", "")).name)

        size_bytes = int(entry.get("size", 0))
        size_item = self.mw._qtwidgets.QTableWidgetItem(human_readable_size(size_bytes))
        try:
            size_item.setData(qt.user_role, size_bytes)
            alignment = qt.alignment()
            if alignment:
                size_item.setTextAlignment(alignment)
            size_item.setToolTip(f"{size_bytes} bytes")
        except Exception as exc:
            logging.debug(f"Failed to set size item data: {exc}")

        path_item = self.mw._qtwidgets.QTableWidgetItem(str(entry.get("path", "")))
        for column, item in enumerate(
            [check_item, system_item, file_item, size_item, path_item]
        ):
            self.ui.table_dups_entries.setItem(row, column, item)

    def _render_group(self, group: dict[str, Any]):
        entries = group.get("entries", [])
        table = self.ui.table_dups_entries
        table.setRowCount(0)

        for row, entry in enumerate(entries):
            table.insertRow(row)
            self._create_table_entry_items(entry, row)

        if entries:
            self._auto_pick("largest", silent=True)

    def _auto_pick(self, mode: str, silent: bool = False):
        if not self._current_group:
            return

        entries = self._current_group.get("entries", [])
        if not entries:
            return

        qt = self._get_qt_constants()
        table = self.ui.table_dups_entries
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item:
                try:
                    item.setCheckState(qt.unchecked)
                except Exception as exc:
                    logging.debug(f"Failed to uncheck: {exc}")

        pick_row = max(0, table.rowCount() - 1) if mode == "smallest" else 0
        item = table.item(pick_row, 0)
        if item:
            try:
                item.setCheckState(qt.checked)
            except Exception as exc:
                logging.debug(f"Failed to check: {exc}")

        if not silent:
            self.mw.log_msg(f"Selected keep={mode} (row {pick_row + 1})")

    def _open_selected_location(self):
        table = self.ui.table_dups_entries
        row = table.currentRow()
        if row < 0:
            return

        path_item = table.item(row, 4)
        if not path_item:
            return

        path = Path(path_item.text())
        if path.exists():
            self.mw._open_file_location(path)
        else:
            logging.info("Selected path no longer exists")
