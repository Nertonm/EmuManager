from __future__ import annotations

"""Dialog to show quarantined files and allow restore/delete actions."""

import os
import shutil
from pathlib import Path
from typing import Optional


class QuarantineDialog:
    def __init__(self, qt, parent, library_db):
        self.qt = qt
        self.parent = parent
        self.db = library_db

    def _find_quarantine_actions(self, qpath: str) -> Optional[str]:
        # Search recent actions for a QUARANTINED entry for this path and
        # attempt to extract the original path from the detail text.
        rows = self.db.get_actions(1000)
        for path, action, detail, ts in rows:
            try:
                if path == qpath and action == "QUARANTINED" and detail:
                    # Expect detail like: 'Moved from /orig/path due to invalid data; see /tmp/..'
                    import re

                    m = re.search(r"Moved from (.+?) due to", detail)
                    if m:
                        return m.group(1)
            except Exception:
                continue
        return None

    def show(self):
        qt = self.qt
        dlg = qt.QDialog(self.parent)
        dlg.setWindowTitle("Quarantined Files")
        dlg.resize(900, 420)

        layout = qt.QVBoxLayout(dlg)

        table = qt.QTableWidget(dlg)
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Path", "Size", "MTime", "Status"])
        table.setEditTriggers(qt.QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(qt.QTableWidget.SelectRows)
        table.setSelectionMode(qt.QTableWidget.SingleSelection)

        # Find quarantined entries
        rows = [e for e in self.db.get_all_entries() if getattr(e, "status", "") == "CORRUPT"]
        table.setRowCount(len(rows))
        for i, e in enumerate(rows):
            try:
                table.setItem(i, 0, qt.QTableWidgetItem(str(e.path)))
                table.setItem(i, 1, qt.QTableWidgetItem(str(e.size)))
                try:
                    import time

                    m = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(e.mtime))
                except Exception:
                    m = str(e.mtime)
                table.setItem(i, 2, qt.QTableWidgetItem(m))
                table.setItem(i, 3, qt.QTableWidgetItem(str(e.status)))
            except Exception:
                continue

        table.resizeColumnsToContents()
        layout.addWidget(table)

        # Buttons: Open Location, Restore, Delete
        btn_layout = qt.QHBoxLayout()
        open_btn = qt.QPushButton("Open Location")
        restore_btn = qt.QPushButton("Restore")
        delete_btn = qt.QPushButton("Delete")
        restore_btn.setEnabled(False)
        delete_btn.setEnabled(False)
        open_btn.setEnabled(False)

        btn_layout.addWidget(open_btn)
        btn_layout.addWidget(restore_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        def selection_changed():
            sel = table.selectedItems()
            ok = bool(sel)
            open_btn.setEnabled(ok)
            restore_btn.setEnabled(ok)
            delete_btn.setEnabled(ok)

        table.itemSelectionChanged.connect(selection_changed)

        def open_location():
            sel = table.selectedItems()
            if not sel:
                return
            p = Path(table.item(sel[0].row(), 0).text())
            try:
                if p.exists():
                    # Try Qt-native first
                    try:
                        from PyQt6.QtGui import QDesktopServices
                        from PyQt6.QtCore import QUrl

                        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.parent)))
                        return
                    except Exception:
                        pass
                    import subprocess

                    subprocess.run(["xdg-open", str(p.parent)], check=False)
                else:
                    qt.QMessageBox.information(dlg, "Not found", "File not found")
            except Exception as e:
                qt.QMessageBox.warning(dlg, "Error", f"Could not open location: {e}")

        def delete_file():
            sel = table.selectedItems()
            if not sel:
                return
            row = sel[0].row()
            p = Path(table.item(row, 0).text())
            try:
                yes = qt.QMessageBox.question(
                    dlg,
                    "Confirm Delete",
                    f"Delete {p.name} from quarantine?",
                    qt.QMessageBox.StandardButton.Yes | qt.QMessageBox.StandardButton.No,
                )
            except Exception:
                # Fallback enums
                yes = qt.QMessageBox.Yes
            if yes != qt.QMessageBox.StandardButton.Yes and yes != qt.QMessageBox.Yes:
                return
            try:
                if p.exists():
                    p.unlink()
                # Remove from DB
                try:
                    self.db.remove_entry(str(p))
                    self.db.log_action(str(p), "DELETED", "User deleted quarantined file")
                except Exception:
                    pass
                table.removeRow(row)
            except Exception as e:
                qt.QMessageBox.warning(dlg, "Error", f"Could not delete: {e}")

        def restore_file():
            sel = table.selectedItems()
            if not sel:
                return
            row = sel[0].row()
            qpath = table.item(row, 0).text()
            p = Path(qpath)
            if not p.exists():
                qt.QMessageBox.information(dlg, "Not found", "Quarantined file not found")
                return

            # Try to find original location from action log
            orig = self._find_quarantine_actions(qpath)
            dest_dir = None
            if orig:
                try:
                    od = Path(orig).parent
                    if od.exists():
                        dest_dir = od
                except Exception:
                    dest_dir = None

            if not dest_dir:
                # Ask user for destination folder
                try:
                    dest_dir = qt.QFileDialog.getExistingDirectory(
                        dlg, "Select destination folder to restore to"
                    )
                    if not dest_dir:
                        return
                    dest_dir = Path(dest_dir)
                except Exception:
                    qt.QMessageBox.warning(dlg, "Error", "Could not get destination")
                    return

            new_path = dest_dir / p.name
            try:
                shutil.move(str(p), str(new_path))
                # Update DB
                try:
                    entry = self.db.get_entry(qpath)
                    if entry:
                        entry.path = str(new_path)
                        entry.status = "UNKNOWN"
                        self.db.update_entry(entry)
                        self.db.log_action(str(new_path), "RESTORED", f"Restored from quarantine: {qpath}")
                        # Optionally remove old entry if path changed
                        if qpath != str(new_path):
                            try:
                                self.db.remove_entry(qpath)
                            except Exception:
                                pass
                except Exception:
                    pass
                table.removeRow(row)
            except Exception as e:
                qt.QMessageBox.warning(dlg, "Error", f"Failed to restore: {e}")

        open_btn.clicked.connect(open_location)
        delete_btn.clicked.connect(delete_file)
        restore_btn.clicked.connect(restore_file)

        btns = qt.QDialogButtonBox(qt.QDialogButtonBox.Close)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        dlg.exec()
