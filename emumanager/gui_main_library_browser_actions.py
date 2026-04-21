from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from emumanager.gui_messages import MSG_SELECT_BASE


class MainWindowLibraryBrowserActionsMixin:
    def on_add(self):
        if not self._last_base:
            self.log_msg(MSG_SELECT_BASE)
            return

        source = self._select_file_dialog("Select ROM file")
        if not source:
            return

        system = self._select_system_dialog(source, Path(self._last_base))
        if not system:
            self.log_msg("Add ROM cancelled: No system selected.")
            return

        move = self._ask_yes_no("Move file?", "Move file instead of copy?")

        def _work_add():
            return self._orchestrator.add_rom(source, system=system, move=move)

        def _done_add(result):
            self._set_ui_enabled(True)
            if isinstance(result, Exception):
                self.log_msg(f"Add ROM error: {result}")
            else:
                self.log_msg(f"Added ROM -> {result}")
                self.on_list()
                self._update_dashboard_stats()

        self._set_ui_enabled(False)
        self._run_in_background(_work_add, _done_add)

    def _select_file_dialog(self, title: str) -> Optional[Path]:
        qt = self._qtwidgets
        filename, _ = qt.QFileDialog.getOpenFileName(self.window, title)
        return Path(filename) if filename else None

    def _select_system_dialog(self, src: Path, base: Path) -> Optional[str]:
        del base
        qt = self._qtwidgets
        from emumanager.common.registry import registry
        from emumanager.config import EXT_TO_SYSTEM

        provider = registry.find_provider_for_file(src)
        guessed = provider.system_id if provider else None
        systems = self._orchestrator.dat_manager.list_systems()
        if not systems:
            systems = sorted(set(EXT_TO_SYSTEM.values()))

        items = sorted(systems)
        index = items.index(guessed) if guessed in items else 0
        system, ok = qt.QInputDialog.getItem(
            self.window,
            "Select System",
            "Target System:",
            items,
            index,
            True,
        )
        return system if ok and system else None

    def _ask_yes_no(self, title: str, msg: str) -> bool:
        qt = self._qtwidgets
        try:
            yes_btn = qt.QMessageBox.StandardButton.Yes
            no_btn = qt.QMessageBox.StandardButton.No
        except AttributeError:
            yes_btn = qt.QMessageBox.Yes
            no_btn = qt.QMessageBox.No

        answer = qt.QMessageBox.question(self.window, title, msg, yes_btn | no_btn)
        return answer == yes_btn

    def on_cancel_requested(self):
        try:
            self._cancel_event.set()
            from emumanager.common.execution import cancel_current_process

            ok = cancel_current_process()
            self.log_msg(
                "Cancel requested" + (" - cancelled" if ok else " - nothing to cancel")
            )
        except Exception:
            self.log_msg("Cancel requested - failed to call cancel")

    def on_open_library(self):
        qt = self._qtwidgets
        dialog = qt.QFileDialog(self.window, "Select Library Directory")
        try:
            dialog.setFileMode(qt.QFileDialog.FileMode.Directory)
        except AttributeError:
            dialog.setFileMode(qt.QFileDialog.Directory)

        if dialog.exec():
            base = Path(dialog.selectedFiles()[0])
            self._rebind_library_runtime(base)
            self.ui.lbl_library.setText(str(base))
            self.ui.lbl_library.setStyleSheet("font-weight: bold; color: #3daee9;")
            self._update_logger(base)
            self.log_msg(f"Library opened: {base}")
            self.ui.btn_verify_dat.setEnabled(True)
            if hasattr(self.ui, "btn_identify_all"):
                self.ui.btn_identify_all.setEnabled(True)
            try:
                self.on_list()
            except Exception:
                pass

    def on_organize_all(self):
        if not self._last_base:
            self.log_msg(MSG_SELECT_BASE)
            return

        reply = self._qtwidgets.QMessageBox.question(
            self.window,
            "Confirm Organization",
            "This will scan, distribute files from root to system folders, and rename everything based on metadata.\n"
            "Are you sure you want to proceed?",
            self._qtwidgets.QMessageBox.StandardButton.Yes
            | self._qtwidgets.QMessageBox.StandardButton.No,
            self._qtwidgets.QMessageBox.StandardButton.No,
        )
        if reply != self._qtwidgets.QMessageBox.StandardButton.Yes:
            return

        self._ensure_env(self._last_base)
        args = self._get_common_args()
        self.log_msg("Starting global organization flow...")

        def _work():
            return self._orchestrator.full_organization_flow(
                dry_run=args.dry_run,
                progress_cb=self.progress_hook,
            )

        def _done(result):
            if isinstance(result, Exception):
                self.log_msg(f"Organization error: {result}")
            else:
                self.log_msg(f"Organization complete: {result}")
            self._set_ui_enabled(True)
            self.on_list()
            self._update_dashboard_stats()

        self._set_ui_enabled(False)
        self._run_in_background(_work, _done)

    def on_verify_all(self):
        if not self._last_base:
            self.log_msg(MSG_SELECT_BASE)
            return
        self.log_msg("Starting batch verification (Not implemented yet for all systems)")
        try:
            self.tools_controller.on_health_check()
        except Exception as exc:
            logging.debug(f"Health check trigger failed: {exc}")
