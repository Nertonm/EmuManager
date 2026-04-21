from __future__ import annotations

import uuid
from pathlib import Path

from emumanager.application import strip_status_prefixed_name
from emumanager.gui_messages import MSG_NO_ROM, MSG_NO_SYSTEM, MSG_SELECT_BASE
from emumanager.manager import get_roms_dir


class MainWindowVerificationIdentifyMixin:
    def on_identify_selected(self):
        """Identify the selected ROM using a DAT file."""
        if not self.rom_list:
            return

        sel = self.rom_list.currentItem()
        if not sel:
            self.log_msg(MSG_NO_ROM)
            return

        if not self._last_base:
            self.log_msg(MSG_SELECT_BASE)
            return

        system = self.sys_list.currentItem().text() if self.sys_list.currentItem() else ""
        if not system:
            self.log_msg(MSG_NO_SYSTEM)
            return

        base_roms_dir = get_roms_dir(Path(self._last_base))
        rom_rel_path = strip_status_prefixed_name(sel.text())
        full_path = base_roms_dir / system / rom_rel_path

        if not full_path.exists():
            self.log_msg(f"File not found: {full_path}")
            return

        dat_path = self._resolve_identification_dat_path(system)
        if not dat_path:
            return

        self.log_msg(f"Identifying {full_path.name} using {Path(dat_path).name}...")

        progress_cb = self._signaler.progress_signal.emit if self._signaler else None

        def _work():
            op = uuid.uuid4().hex
            log_cb = self._make_op_log_cb(op)
            try:
                self.status.showMessage(f"Operation {op} started", 3000)
            except Exception:
                pass
            return self._run_identify_single_worker(
                full_path, Path(dat_path), log_cb, progress_cb
            )

        def _done(res):
            self.log_msg(str(res))
            self._qtwidgets.QMessageBox.information(
                self.window, "Identification Result", str(res)
            )
            self._sync_after_verification()

        self._run_in_background(_work, _done)

    def _resolve_identification_dat_path(self, system: str):
        from emumanager.verification.dat_manager import find_dat_for_system

        dat_path = None
        dats_dir = self._last_base / "dats"
        if dats_dir.exists():
            found = find_dat_for_system(dats_dir, system)
            if found:
                dat_path = str(found)

        if not dat_path:
            dat_path, _ = self._qtwidgets.QFileDialog.getOpenFileName(
                self.window,
                "Select DAT File",
                str(self._last_base),
                "DAT Files (*.dat *.xml)",
            )

        return dat_path

    def on_identify_all(self):
        if not self._last_base:
            self.log_msg(MSG_SELECT_BASE)
            return

        if not self._ask_yes_no(
            "Start Full Identification?",
            "This will load ALL DAT files into memory and scan the library. "
            "It may take a significant amount of RAM and time. Continue?",
        ):
            return

        args = self._get_common_args()
        potential_roots = [
            self._last_base / "dats",
            self._last_base,
            self._last_base.parent / "dats",
            self._last_base.parent.parent / "dats",
        ]
        args.dats_roots = [path for path in potential_roots if path.exists()]

        if not args.dats_roots:
            self.log_msg(
                "Error: No DATs locations found. "
                "Please run 'Update DATs' or place .dat files in the library."
            )
            return

        self.ui.table_results.setRowCount(0)
        self.log_msg("Starting full identification...")

        def _work():
            op = uuid.uuid4().hex
            log_cb = self._make_op_log_cb(op)
            try:
                self.status.showMessage(f"Operation {op} started", 3000)
            except Exception:
                pass
            return self._run_identify_all_worker(args, log_cb)

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
