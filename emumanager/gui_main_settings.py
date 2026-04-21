from __future__ import annotations

from pathlib import Path


LAST_SYSTEM_KEY = "ui/last_system"


class MainWindowSettingsMixin:
    def _load_settings(self):
        if not self._settings:
            return
        try:
            self._restore_window_settings()
            self._restore_ui_settings()
        except Exception:
            pass

    def _save_settings(self):
        if not self._settings:
            return
        try:
            self._persist_window_settings()
            self._persist_ui_settings()
        except Exception:
            pass

    def _restore_window_settings(self):
        """Restore geometry/state and base dir from QSettings."""
        try:
            try:
                geom = self._settings.value("ui/window_geometry")
                if geom:
                    self.window.restoreGeometry(geom)
            except Exception:
                w = self._settings.value("window/width")
                h = self._settings.value("window/height")
                if w and h:
                    try:
                        self.window.resize(int(w), int(h))
                    except Exception:
                        pass
            try:
                st = self._settings.value("ui/window_state")
                if st:
                    self.window.restoreState(st)
            except Exception:
                pass

            last = self._settings.value("last_base")
            if last:
                path = Path(str(last))
                if path.exists():
                    self._last_base = path
                    try:
                        self.ui.lbl_library.setText(str(self._last_base))
                        self.ui.lbl_library.setStyleSheet(
                            "font-weight: bold; color: #3daee9;"
                        )
                        self._set_ui_enabled(True)
                        self.log_msg(f"Restored last library: {self._last_base}")
                        self._update_logger(self._last_base)
                    except Exception:
                        pass
                else:
                    self.log_msg(f"Last library path not found: {path}")
        except Exception:
            pass

    def _update_logger(self, base_dir: Path):
        """Configure file-based logging under the selected library directory."""
        try:
            from emumanager.logging_cfg import get_logger, get_fileops_logger

            get_logger("emumanager", base_dir=base_dir)
            get_fileops_logger(base_dir=base_dir)
        except Exception as e:
            try:
                self.log_msg(f"Failed to update logger: {e}")
            except Exception:
                pass

    def _restore_ui_settings(self):
        """Restore checkboxes, toolbar visibility, filters, splitter, and widths."""
        try:
            self._restore_checkboxes()
            self._restore_extras()
            self._restore_splitter()
            self._restore_toolbar_visibility()
            self._restore_table_widths()
            self._restore_last_system()
        except Exception:
            pass

    def _restore_checkboxes(self):
        try:
            self.chk_dry_run.setChecked(
                str(self._settings.value("settings/dry_run", "false")).lower() == "true"
            )
            self.spin_level.setValue(int(self._settings.value("settings/level", 3)))
            self.combo_profile.setCurrentText(
                str(self._settings.value("settings/profile", "None"))
            )
            self.chk_rm_originals.setChecked(
                str(self._settings.value("settings/rm_originals", "false")).lower()
                == "true"
            )
            self.chk_quarantine.setChecked(
                str(self._settings.value("settings/quarantine", "false")).lower()
                == "true"
            )
            self.chk_deep_verify.setChecked(
                str(self._settings.value("settings/deep_verify", "false")).lower()
                == "true"
            )
            self.chk_recursive.setChecked(
                str(self._settings.value("settings/recursive", "true")).lower()
                == "true"
            )
            self.chk_process_selected.setChecked(
                str(self._settings.value("settings/process_selected", "false")).lower()
                == "true"
            )
            self.chk_standardize_names.setChecked(
                str(self._settings.value("settings/standardize_names", "false")).lower()
                == "true"
            )
        except Exception:
            pass

    def _restore_extras(self):
        try:
            vis = str(self._settings.value("ui/log_visible", "true")).lower() == "true"
            self.ui.log_dock.setVisible(vis)
        except Exception:
            pass
        try:
            if hasattr(self.ui, "edit_filter"):
                self.ui.edit_filter.setText(
                    str(self._settings.value("ui/rom_filter", ""))
                )
            if hasattr(self.ui, "combo_verif_filter"):
                idx = int(self._settings.value("ui/verif_filter_idx", 0))
                self.ui.combo_verif_filter.setCurrentIndex(idx)
        except Exception:
            pass

    def _restore_splitter(self):
        try:
            st = self._settings.value("ui/splitter_state")
            if st:
                self.ui.splitter.restoreState(st)
        except Exception:
            pass

    def _restore_toolbar_visibility(self):
        try:
            tb_vis = (
                str(self._settings.value("ui/toolbar_visible", "true")).lower()
                == "true"
            )
            if hasattr(self, "_toolbar") and self._toolbar:
                self._toolbar.setVisible(tb_vis)
            if hasattr(self, "act_toggle_toolbar"):
                self.act_toggle_toolbar.setChecked(tb_vis)
        except Exception:
            pass

    def _restore_table_widths(self):
        try:
            widths = self._settings.value("ui/verif_table_widths")
            if widths and hasattr(self.ui, "table_results"):
                if isinstance(widths, (list, tuple)):
                    for i, w in enumerate(widths):
                        try:
                            self.ui.table_results.setColumnWidth(i, int(w))
                        except Exception:
                            pass
        except Exception:
            pass

    def _restore_last_system(self):
        try:
            self._last_system = (
                str(self._settings.value(LAST_SYSTEM_KEY))
                if self._settings.value(LAST_SYSTEM_KEY)
                else None
            )
        except Exception:
            self._last_system = None

    def _persist_window_settings(self):
        """Persist geometry/state and base dir to QSettings."""
        try:
            try:
                self._settings.setValue("ui/window_geometry", self.window.saveGeometry())
                self._settings.setValue("ui/window_state", self.window.saveState())
            except Exception:
                self._settings.setValue("window/width", self.window.width())
                self._settings.setValue("window/height", self.window.height())
            if self._last_base:
                self._settings.setValue("last_base", str(self._last_base))
        except Exception:
            pass

    def _persist_ui_settings(self):
        """Persist checkboxes, filters, splitter, toolbar visibility, and widths."""
        try:
            self._persist_checkbox_settings()
            self._persist_extras()
            self._persist_splitter()
            self._persist_table_widths()
        except Exception:
            pass

    def _persist_checkbox_settings(self):
        try:
            self._settings.setValue("settings/dry_run", str(self.chk_dry_run.isChecked()))
            self._settings.setValue("settings/level", self.spin_level.value())
            self._settings.setValue("settings/profile", self.combo_profile.currentText())
            self._settings.setValue(
                "settings/rm_originals", str(self.chk_rm_originals.isChecked())
            )
            self._settings.setValue(
                "settings/quarantine", str(self.chk_quarantine.isChecked())
            )
            self._settings.setValue(
                "settings/deep_verify", str(self.chk_deep_verify.isChecked())
            )
            self._settings.setValue(
                "settings/recursive", str(self.chk_recursive.isChecked())
            )
            self._settings.setValue(
                "settings/process_selected",
                str(self.chk_process_selected.isChecked()),
            )
            self._settings.setValue(
                "settings/standardize_names",
                str(self.chk_standardize_names.isChecked()),
            )
        except Exception:
            pass

    def _persist_extras(self):
        try:
            self._settings.setValue("ui/log_visible", str(self.ui.log_dock.isVisible()))
            if hasattr(self.ui, "edit_filter"):
                self._settings.setValue("ui/rom_filter", self.ui.edit_filter.text())
            if hasattr(self.ui, "combo_verif_filter"):
                self._settings.setValue(
                    "ui/verif_filter_idx",
                    self.ui.combo_verif_filter.currentIndex(),
                )
        except Exception:
            pass

    def _persist_splitter(self):
        try:
            self._settings.setValue("ui/splitter_state", self.ui.splitter.saveState())
        except Exception:
            pass

    def _persist_table_widths(self):
        try:
            if hasattr(self.ui, "table_results"):
                widths = [
                    self.ui.table_results.columnWidth(i)
                    for i in range(self.ui.table_results.columnCount())
                ]
                self._settings.setValue("ui/verif_table_widths", widths)
        except Exception:
            pass

    def _on_close_event(self, event):
        self.log_msg("Shutting down...")
        self._cancel_event.set()
        try:
            self._save_settings()
        except Exception:
            pass
        if self._executor:
            self._executor.shutdown(wait=False)
        if self._original_close_event:
            self._original_close_event(event)
        else:
            event.accept()
