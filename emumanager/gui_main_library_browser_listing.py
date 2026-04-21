from __future__ import annotations

import logging
from pathlib import Path

from emumanager.application import strip_status_prefixed_name


IGNORED_LIBRARY_EXTENSIONS = frozenset(
    {
        ".dat",
        ".xml",
        ".txt",
        ".nfo",
        ".pdf",
        ".doc",
        ".docx",
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".gif",
        ".ico",
        ".ini",
        ".cfg",
        ".conf",
        ".db",
        ".ds_store",
        ".url",
        ".lnk",
        ".desktop",
        ".py",
        ".pyc",
        ".log",
        ".err",
        ".out",
    }
)
IGNORED_LIBRARY_FOLDERS = frozenset({"dats", "no-intro", "redump"})


class MainWindowLibraryBrowserListingMixin:
    def _on_system_selected(self, item):
        try:
            if getattr(self, "_skip_list_side_effects", False):
                return

            system = item.text()
            self._populate_roms(system)
            try:
                self.log_msg(
                    self.library_insights.build_system_snapshot(system).to_log_message()
                )
            except Exception as exc:
                logging.debug(f"Failed to get system stats: {exc}")

            try:
                if self._settings:
                    self._settings.setValue("ui/last_system", system)
            except Exception:
                pass

            if hasattr(self.ui, "grp_switch_actions"):
                self.ui.grp_switch_actions.setVisible(system.lower() == "switch")
            if hasattr(self.ui, "edit_filter"):
                self._apply_rom_filter(self.ui.edit_filter.text())
        except Exception:
            pass

    def _on_rom_double_clicked(self, item):
        del item
        try:
            self.tools_controller.on_compress_selected()
        except Exception as exc:
            logging.debug(f"Double-click action failed: {exc}")

    def _list_files_recursive(self, root: Path) -> list[Path]:
        files: list[Path] = []
        if not root.exists():
            return files

        for path in root.rglob("*"):
            if not path.is_file() or path.name.startswith("."):
                continue
            if path.suffix.lower() in IGNORED_LIBRARY_EXTENSIONS:
                continue

            try:
                rel = path.relative_to(root)
                if any(part.startswith(".") for part in rel.parts):
                    continue

                parts_lower = [part.lower() for part in rel.parts]
                if any(folder in parts_lower for folder in IGNORED_LIBRARY_FOLDERS):
                    continue
                files.append(path)
            except Exception:
                continue

        files.sort(key=lambda candidate: str(candidate).lower())
        return files

    def _get_list_files_fn(self):
        if self.chk_process_selected.isChecked():
            return self._list_files_selected
        return self._list_files_recursive

    def _find_rom_files(self, system: str) -> list[Path]:
        try:
            roms_root = self._orchestrator.session.roms_path
            roms_dir = roms_root / system
            if not roms_dir.exists():
                self.log_msg(f"Directory not found: {roms_dir}")
                return []

            self.log_msg(f"Listing ROMs for {system} in {roms_dir}")
            full_files = self._list_files_recursive(roms_dir)
            return [path.relative_to(roms_dir) for path in full_files]
        except Exception as exc:
            self.log_msg(f"Error listing ROMs: {exc}")
            logging.error("Failed to find ROM files", exc_info=True)
            return []

    def _populate_roms(self, system: str):
        if not self._last_base:
            return

        try:
            files = self._find_rom_files(system)
            rows = self.library_insights.build_rom_browser_rows(system, files)
            self._current_rom_rows = rows
            self._current_roms = [row.filename for row in rows]
            tracked_count = sum(1 for row in rows if row.entry)
            self.log_msg(f"Found {len(files)} files ({tracked_count} in database).")

            if self.rom_list is not None:
                self.rom_list.clear()
                for row in rows:
                    self.rom_list.addItem(row.display_name)
        except Exception as exc:
            logging.exception(f"Failed to populate roms: {exc}")
            self.log_msg(f"Error populating ROM list: {exc}")

    def _on_filter_text(self, text: str):
        try:
            self._apply_rom_filter(text)
        except Exception:
            pass

    def _apply_rom_filter(self, text: str):
        if not hasattr(self, "_current_rom_rows"):
            return

        try:
            query = (text or "").lower().strip()
            rows = self._current_rom_rows
            if query:
                rows = [row for row in rows if query in row.filename.lower()]
            self.ui.rom_list.clear()
            for row in rows:
                self.ui.rom_list.addItem(row.display_name)
        except Exception:
            pass

    def _list_files_selected(self, root: Path) -> list[Path]:
        del root
        if not self.rom_list or not self.sys_list:
            return []

        selected_items = self.rom_list.selectedItems()
        if not selected_items:
            return []

        sys_item = self.sys_list.currentItem()
        if not sys_item:
            return []

        system = sys_item.text()
        roms_dir = Path(self._last_base) / "roms" / system
        files: list[Path] = []
        for item in selected_items:
            rel_path = strip_status_prefixed_name(item.text())
            full_path = roms_dir / rel_path
            if full_path.exists():
                files.append(full_path)
        return files
