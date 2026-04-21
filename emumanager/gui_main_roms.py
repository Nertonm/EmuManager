from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from emumanager.application import strip_status_prefixed_name
from emumanager.gui_messages import MSG_NO_ROM, MSG_NO_SYSTEM
from emumanager.manager import get_roms_dir


class MainWindowRomsMixin:
    def on_delete_selected(self):
        if not self.rom_list:
            return
        try:
            sel_items = self.rom_list.selectedItems()
            if not sel_items:
                self.log_msg(MSG_NO_ROM)
                return

            sys_item = self.sys_list.currentItem() if self.sys_list else None
            if not sys_item:
                self.log_msg(MSG_NO_SYSTEM)
                return

            system = sys_item.text()
            roms_root = self._orchestrator.session.roms_path

            files_to_delete = []
            for item in sel_items:
                filepath = roms_root / system / strip_status_prefixed_name(item.text())
                if filepath.exists():
                    files_to_delete.append(filepath)

            if not files_to_delete:
                return

            msg = f"Are you sure you want to delete {len(files_to_delete)} files?"
            if not self._ask_yes_no("Confirm Delete", msg):
                return

            count = 0
            for fp in files_to_delete:
                if self._orchestrator.delete_rom_file(fp):
                    count += 1
                    self.log_msg(f"Deleted: {fp.name}")
                else:
                    self.log_msg(f"Failed to delete {fp.name}")

            if count > 0:
                self._populate_roms(system)
                self._update_dashboard_stats()

        except Exception as e:
            self.log_msg(f"Error deleting files: {e}")
            logging.error("Failed deletion operation", exc_info=True)

    def on_verify_selected(self):
        if not self.rom_list:
            return
        try:
            sel = self.rom_list.currentItem()
            if sel is None:
                self.log_msg(MSG_NO_ROM)
                return

            rom_name = strip_status_prefixed_name(sel.text())
            sys_item = self.sys_list.currentItem() if self.sys_list else None
            if not sys_item:
                self.log_msg(MSG_NO_SYSTEM)
                return

            system = sys_item.text()
            roms_root = self._orchestrator.session.roms_path
            filepath = roms_root / system / rom_name

            if not filepath.exists():
                self.log_msg(f"File not found: {filepath}")
                return

            self.log_msg(f"Identifying {rom_name}...")

            def _work():
                return self._orchestrator.identify_single_file(filepath)

            def _done(res):
                self._set_ui_enabled(True)
                if not res:
                    self.log_msg(f"Failed to identify {rom_name}")
                else:
                    self.log_msg(f"Metadata for {rom_name}: {res}")
                    self._qtwidgets.QMessageBox.information(
                        self.window, "Identification", str(res)
                    )

            self._set_ui_enabled(False)
            self._run_in_background(_work, _done)

        except Exception as e:
            self.log_msg(f"Error verifying file: {e}")
            logging.error("Failed verification operation", exc_info=True)

    def on_rename_to_standard_selected(self):
        """Renomeia a ROM selecionada para o padrão canónico via Orchestrator."""
        if not self.rom_list:
            return
        try:
            sel_items = self.rom_list.selectedItems()
            if not sel_items:
                self.log_msg(MSG_NO_ROM)
                return

            sys_item = self.sys_list.currentItem() if self.sys_list else None
            if not sys_item:
                self.log_msg(MSG_NO_SYSTEM)
                return

            system = sys_item.text()
            self.log_msg(f"Organizando nomes para: {system}")

            def _work():
                return self._orchestrator.organize_names(system_id=system, dry_run=False)

            def _done(res):
                self._set_ui_enabled(True)
                self.log_msg(f"Renomeação concluída: {res}")
                self._populate_roms(system)
                self._update_dashboard_stats()
                self._sync_after_verification()

            self._set_ui_enabled(False)
            self._run_in_background(_work, _done)

        except Exception as e:
            self.log_msg(f"Error renaming files: {e}")
            logging.error("Failed rename operation", exc_info=True)

    def _guess_rom_region(self, path_str: str) -> Optional[str]:
        if "(USA)" in path_str or "(US)" in path_str:
            return "US"
        if "(Europe)" in path_str or "(EU)" in path_str:
            return "EN"
        if "(Japan)" in path_str or "(JP)" in path_str:
            return "JA"
        return None

    def _on_rom_selection_changed(self, current, previous):
        if not current:
            self.cover_label.clear()
            self.cover_label.setText("No ROM selected")
            return

        sys_item = self.sys_list.currentItem()
        if not sys_item or not self._last_base:
            return

        system = sys_item.text()
        rom_rel_path = current.text()

        rom_display_name = strip_status_prefixed_name(rom_rel_path)

        try:
            base_roms_dir = get_roms_dir(Path(self._last_base))
            full_path = base_roms_dir / system / rom_display_name

            self._show_rom_metadata(str(full_path.resolve()))

            cache_dir = Path(self._last_base) / ".covers"
            cache_dir.mkdir(exist_ok=True)

            self.log_msg(
                f"Fetching cover for {rom_display_name} (System: {system})..."
            )
            region = self._guess_rom_region(rom_display_name)

            self._start_cover_downloader(system, region, cache_dir, full_path)
        except Exception as e:
            logging.error(f"Selection change failed: {e}")

    def _show_rom_metadata(self, full_path: str):
        """Mostra metadados da ROM no log a partir do banco de dados."""
        try:
            inspection = self.library_insights.get_rom_inspection(full_path)
            if not inspection:
                self.log_msg("⚠ No metadata found in library for this file")
                return

            for line in inspection.metadata_lines:
                self.log_msg(line)

        except Exception as e:
            logging.debug(f"Failed to show ROM metadata: {e}")

    def _start_cover_downloader(self, system, region, cache_dir, full_path):
        downloader = self._create_cover_downloader(system, region, cache_dir, full_path)

        conn_type = (
            self._Qt_enum.ConnectionType.QueuedConnection
            if self._Qt_enum and hasattr(self._Qt_enum, "ConnectionType")
            else self._qtcore.Qt.QueuedConnection
        )

        downloader.signals.finished.connect(self._update_cover_image, conn_type)
        downloader.signals.log.connect(self.log_msg, conn_type)

        if self._qtcore:
            self._qtcore.QThreadPool.globalInstance().start(downloader)
