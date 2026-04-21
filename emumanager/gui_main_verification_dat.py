from __future__ import annotations

import logging
import uuid
from pathlib import Path

from emumanager.application import strip_status_prefixed_name
from emumanager.gui_messages import MSG_SELECT_BASE
from emumanager.manager import get_roms_dir


class MainWindowVerificationDatMixin:
    def on_select_dat(self):
        qt = self._qtwidgets
        dlg = qt.QFileDialog(self.window, "Select DAT File")
        try:
            dlg.setFileMode(qt.QFileDialog.FileMode.ExistingFile)
        except AttributeError:
            dlg.setFileMode(qt.QFileDialog.ExistingFile)
        dlg.setNameFilter("DAT Files (*.dat *.xml)")

        if dlg.exec():
            path = Path(dlg.selectedFiles()[0])
            self._current_dat_path = path
            self.ui.lbl_dat_path.setText(path.name)
            self.ui.lbl_dat_path.setStyleSheet("color: #3daee9; font-weight: bold;")
            self.ui.btn_verify_dat.setEnabled(True)
            self.log_msg(f"Selected DAT: {path}")

    def on_verify_dat(self):
        if not self._last_base:
            self.log_msg(MSG_SELECT_BASE)
            return

        target_path = self._resolve_verification_target_path()

        if not getattr(self, "_current_dat_path", None):
            self.on_select_dat()
            if not getattr(self, "_current_dat_path", None):
                return

        args = self._get_common_args()
        args.dat_path = self._current_dat_path
        args.dats_root = self._find_nearest_dats_root()

        self.ui.table_results.setRowCount(0)

        def _work():
            op = uuid.uuid4().hex
            log_cb = self._make_op_log_cb(op)
            try:
                self.status.showMessage(f"Operation {op} started", 3000)
            except Exception:
                pass
            return self._run_hash_verify_worker(target_path, args, log_cb)

        def _done(res):
            if hasattr(res, "results"):
                self.log_msg(res.text)
                self._last_verify_results = res.results
                self.on_verification_filter_changed()
                self._sync_after_verification()
            else:
                self.log_msg(str(res))
            self._set_ui_enabled(True)

        self._set_ui_enabled(False)
        self._run_in_background(_work, _done)

    def _resolve_verification_target_path(self) -> Path:
        target_path = self._last_base
        selected_items = self.ui.sys_list.selectedItems()
        if not selected_items:
            return target_path

        system_name = selected_items[0].text()
        path_candidates = [
            self._last_base / system_name,
            self._last_base / "roms" / system_name,
        ]
        for candidate in path_candidates:
            if candidate.exists():
                self.log_msg(f"Targeting system folder: {system_name}")
                return candidate
        return target_path

    def _find_nearest_dats_root(self):
        candidates = [
            self._last_base / "dats",
            self._last_base.parent / "dats",
            self._last_base.parent.parent / "dats",
        ]
        return next((path for path in candidates if path.exists()), None)

    def _sync_after_verification(self):
        """Sincroniza os dados da biblioteca após verificação."""
        try:
            current_sys_item = self.sys_list.currentItem()
            if current_sys_item:
                system = current_sys_item.text()
                self.log_msg(f"🔄 Refreshing {system} library data...")
                self._populate_roms(system)

            current_rom = self.rom_list.currentItem()
            if current_rom and current_sys_item:
                system = current_sys_item.text()
                rom_text = strip_status_prefixed_name(current_rom.text())

                try:
                    base_roms_dir = get_roms_dir(Path(self._last_base))
                    full_path = base_roms_dir / system / rom_text
                    self._show_rom_metadata(str(full_path.resolve()))
                except Exception as e:
                    logging.debug(
                        f"Failed to update inspector after verification: {e}"
                    )

            self.log_msg("✓ Library data synchronized")
        except Exception as e:
            logging.debug(f"Failed to sync after verification: {e}")
