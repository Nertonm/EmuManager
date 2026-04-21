from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from emumanager.gui_messages import MSG_SELECT_BASE


class MainWindowLibraryScanMixin:
    def on_init(self):
        self.log_msg(f"Running core init on: {self._last_base}")
        try:
            self._orchestrator.initialize_library(dry_run=False)
            self.log_msg("Init complete.")
        except Exception as e:
            self.log_msg(f"Init error: {e}")

    def _start_background_scan(self, base: Path, systems: list[str]):
        """Inicia a varredura da biblioteca em background."""
        self._scan_in_progress = True
        progress_cb = self._signaler.progress_signal.emit if self._signaler else None

        def _work():
            op = str(uuid.uuid4())[:8]
            log_cb = self._make_op_log_cb(op)
            try:
                self.status.showMessage(f"Operation {op} started", 3000)
            except Exception:
                pass
            return self._run_scan_worker(base, log_cb, progress_cb)

        def _done(result):
            self._handle_scan_finished(result, systems)

        self._run_in_background(_work, _done)

    def _handle_scan_finished(self, result: Any, systems: list[str]):
        """Processa a conclusão do scan e atualiza a UI."""
        if isinstance(result, Exception):
            self.log_msg(f"Scan error: {result}")
        elif result:
            self.log_msg(f"Scan complete. Total files: {result.get('count', 0)}")
            self._update_dashboard_stats(systems, stats=result)
            self._refresh_library_table()

        self._scan_in_progress = False
        self._auto_select_last_system()

        if self._signaler:
            self._signaler.progress_signal.emit(0, "")
        else:
            self._progress_slot(0, "")

        try:
            self._refresh_quarantine_tab()
        except Exception as e:
            logging.debug(f"Quarantine refresh failed: {e}")

    def on_list(self, force_scan: bool = False):
        if not self._last_base:
            self.log_msg(MSG_SELECT_BASE)
            return

        if self._scan_in_progress and not force_scan:
            return

        self._set_ui_enabled(True)
        systems = self._orchestrator.dat_manager.list_systems()

        self._skip_list_side_effects = True
        try:
            self._refresh_system_list_ui(systems)
        finally:
            self._skip_list_side_effects = False

        self._log_systems(systems)
        self.log_msg("Scanning library...")
        self._start_background_scan(Path(self._last_base), systems)
        self._update_dashboard_stats(systems)

    def _update_dashboard_stats(self, systems=None, stats=None):
        try:
            if systems is None:
                if self._last_base:
                    systems = self._orchestrator.dat_manager.list_systems()
                else:
                    systems = []

            snapshot = self.library_insights.build_dashboard_snapshot(
                systems=systems,
                scan_stats=stats,
            )

            if hasattr(self.ui, "lbl_systems_count"):
                self.ui.lbl_systems_count.setText(
                    f"Systems Configured: {snapshot.systems_count}"
                )
            if hasattr(self.ui, "lbl_total_roms"):
                self.ui.lbl_total_roms.setText(
                    f"Total Files: {snapshot.total_files}"
                )
            if hasattr(self.ui, "lbl_library_size"):
                self.ui.lbl_library_size.setText(
                    f"Library Size: {snapshot.total_size_label}"
                )
            if snapshot.last_scan_label and hasattr(self.ui, "lbl_last_scan"):
                self.ui.lbl_last_scan.setText(
                    f"Last Scan: {snapshot.last_scan_label}"
                )

        except Exception:
            logging.error("Failed to update dashboard stats", exc_info=True)

    def _refresh_system_list_ui(self, systems):
        try:
            if self.sys_list is not None:
                self.sys_list.clear()
                for s in systems:
                    self.sys_list.addItem(s)
                self._auto_select_last_system()

            if hasattr(self.ui, "combo_gallery_system"):
                self.ui.combo_gallery_system.clear()
                self.ui.combo_gallery_system.addItems(systems)
        except Exception:
            pass

    def _auto_select_last_system(self):
        try:
            if getattr(self, "_last_system", None):
                items = [
                    self.sys_list.item(i).text() for i in range(self.sys_list.count())
                ]
                if self._last_system in items:
                    idx = items.index(self._last_system)
                    self.sys_list.setCurrentRow(idx)
                    self._on_system_selected(self.sys_list.item(idx))
        except Exception:
            pass

    def _log_systems(self, systems):
        if not systems:
            self.log_msg("Nenhum sistema encontrado — execute 'init' primeiro.")
            return
        self.log_msg("Sistemas encontrados:")
        for s in systems:
            self.log_msg(f" - {s}")

    def _refresh_library_table(self):
        """Atualiza a tabela de resultados com os dados da biblioteca após o scan."""
        try:
            if not hasattr(self.ui, "table_results"):
                return

            all_entries = self.library_db.get_all_entries()

            if not all_entries:
                self.log_msg("No entries found in library database")
                return

            from types import SimpleNamespace

            results = []
            for entry in all_entries:
                result = SimpleNamespace(
                    status=entry.status or "UNKNOWN",
                    filename=Path(entry.path).name,
                    full_path=entry.path,
                    match_name=entry.match_name or "",
                    dat_name=entry.dat_name or "",
                    crc=entry.crc32 or "",
                    sha1=entry.sha1 or "",
                    md5=entry.md5 or "",
                    sha256=entry.sha256 or "",
                )
                results.append(result)

            self.ui.table_results.setRowCount(len(results))
            for i, result in enumerate(results):
                self._create_result_row(i, result)

            self.log_msg(f"Library table updated with {len(results)} entries")

        except Exception as e:
            logging.exception(f"Failed to refresh library table: {e}")
            self.log_msg(f"Error updating library table: {e}")
