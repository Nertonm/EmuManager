from __future__ import annotations

import logging
import shutil
from pathlib import Path


class MainWindowQuarantineMixin:
    def _refresh_quarantine_tab(self):
        try:
            if not hasattr(self.ui, "quarantine_table"):
                return
            table = self.ui.quarantine_table
            rows = [
                entry
                for entry in self.library_db.get_all_entries()
                if getattr(entry, "status", "") == "CORRUPT"
            ]
            table.setRowCount(len(rows))
            for i, entry in enumerate(rows):
                try:
                    table.setItem(i, 0, self._qtwidgets.QTableWidgetItem(str(entry.path)))
                    table.setItem(i, 1, self._qtwidgets.QTableWidgetItem(str(entry.size)))
                    try:
                        import time

                        mtime = time.strftime(
                            "%Y-%m-%d %H:%M:%S",
                            time.localtime(entry.mtime),
                        )
                    except Exception:
                        mtime = str(entry.mtime)
                    table.setItem(i, 2, self._qtwidgets.QTableWidgetItem(mtime))
                    table.setItem(i, 3, self._qtwidgets.QTableWidgetItem(str(entry.status)))
                except Exception:
                    continue
            table.resizeColumnsToContents()
        except Exception:
            logging.exception("Failed to refresh quarantine tab")

    def _on_quarantine_selection_changed(self):
        try:
            if not hasattr(self.ui, "quarantine_table"):
                return
            sel = self.ui.quarantine_table.selectedItems()
            ok = bool(sel)
            try:
                self.ui.btn_quar_open.setEnabled(ok)
                self.ui.btn_quar_restore.setEnabled(ok)
                self.ui.btn_quar_delete.setEnabled(ok)
            except Exception:
                pass
        except Exception:
            pass

    def _quarantine_open_location(self):
        try:
            sel = self.ui.quarantine_table.selectedItems()
            if not sel:
                return
            path = Path(sel[0].text())
            try:
                from PyQt6.QtCore import QUrl
                from PyQt6.QtGui import QDesktopServices

                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
                return
            except Exception:
                pass
            import subprocess

            subprocess.run(["xdg-open", str(path.parent)], check=False)
        except Exception as e:
            self.log_msg(f"Failed to open location: {e}")

    def _quarantine_delete(self):
        try:
            sel = self.ui.quarantine_table.selectedItems()
            if not sel:
                return
            row = sel[0].row()
            path = Path(self.ui.quarantine_table.item(row, 0).text())
            qt = self._qtwidgets
            try:
                yes = qt.QMessageBox.question(
                    self.window,
                    "Confirm Delete",
                    f"Delete {path.name} from quarantine?",
                    qt.QMessageBox.StandardButton.Yes | qt.QMessageBox.StandardButton.No,
                )
            except Exception:
                yes = qt.QMessageBox.Yes
            if yes != qt.QMessageBox.StandardButton.Yes and yes != qt.QMessageBox.Yes:
                return
            try:
                if path.exists():
                    path.unlink()
                try:
                    self.library_db.remove_entry(str(path))
                    self.library_db.log_action(
                        str(path),
                        "DELETED",
                        "User deleted quarantined file",
                    )
                except Exception:
                    pass
                self.ui.quarantine_table.removeRow(row)

                try:
                    self._sync_after_verification()
                except Exception as e:
                    logging.debug(f"UI sync after delete failed: {e}")
            except Exception as e:
                qt.QMessageBox.warning(self.window, "Error", f"Could not delete: {e}")
        except Exception:
            logging.exception("Quarantine delete failed")

    def _quarantine_restore(self):
        try:
            sel = self.ui.quarantine_table.selectedItems()
            if not sel:
                return
            row = sel[0].row()
            quarantined_path = self.ui.quarantine_table.item(row, 0).text()
            path = Path(quarantined_path)
            if not path.exists():
                try:
                    self._qtwidgets.QMessageBox.information(
                        self.window,
                        "Not found",
                        "Quarantined file not found",
                    )
                except Exception:
                    pass
                return

            original_path = None
            try:
                rows = self.library_db.get_actions(1000)
                for action_path, action, detail, _timestamp in rows:
                    try:
                        if (
                            action_path == quarantined_path
                            and action == "QUARANTINED"
                            and detail
                        ):
                            import re

                            match = re.search(r"Moved from (.+?) due to", detail)
                            if match:
                                original_path = match.group(1)
                                break
                    except Exception:
                        continue
            except Exception:
                original_path = None

            destination_dir = None
            if original_path:
                try:
                    original_dir = Path(original_path).parent
                    if original_dir.exists():
                        destination_dir = original_dir
                except Exception:
                    destination_dir = None

            if not destination_dir:
                try:
                    destination = self._qtwidgets.QFileDialog.getExistingDirectory(
                        self.window,
                        "Select destination folder to restore to",
                    )
                    if not destination:
                        return
                    destination_dir = Path(destination)
                except Exception:
                    try:
                        self._qtwidgets.QMessageBox.warning(
                            self.window,
                            "Error",
                            "Could not get destination",
                        )
                    except Exception:
                        pass
                    return

            restored_path = destination_dir / path.name
            try:
                shutil.move(str(path), str(restored_path))
                try:
                    entry = self.library_db.get_entry(quarantined_path)
                    if entry:
                        entry.path = str(restored_path)
                        entry.status = "UNKNOWN"
                        self.library_db.update_entry(entry)
                        self.library_db.log_action(
                            str(restored_path),
                            "RESTORED",
                            f"Restored from quarantine: {quarantined_path}",
                        )
                        if quarantined_path != str(restored_path):
                            try:
                                self.library_db.remove_entry(quarantined_path)
                            except Exception:
                                pass
                except Exception:
                    pass
                self.ui.quarantine_table.removeRow(row)

                try:
                    self._sync_after_verification()
                except Exception as e:
                    logging.debug(f"UI sync after restore failed: {e}")
            except Exception as e:
                try:
                    self._qtwidgets.QMessageBox.warning(
                        self.window,
                        "Error",
                        f"Failed to restore: {e}",
                    )
                except Exception:
                    pass
        except Exception:
            logging.exception("Quarantine restore failed")
