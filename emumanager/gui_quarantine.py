from __future__ import annotations

"""Dialog to show quarantined files and allow restore/delete actions."""

import os
import shutil
from pathlib import Path
from typing import Optional


import logging
import os
import re
import shutil
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class QuarantineDialog:
    def __init__(self, qt, parent, library_db):
        self.qt = qt
        self.parent = parent
        self.db = library_db
        self.dlg = None
        self.table = None
        self.open_btn = None
        self.restore_btn = None
        self.delete_btn = None

    def _find_quarantine_actions(self, qpath: str) -> Optional[str]:
        # Search recent actions for a QUARANTINED entry for this path and
        # attempt to extract the original path from the detail text.
        rows = self.db.get_actions(1000)
        for path, action, detail, ts in rows:
            try:
                if path == qpath and action == "QUARANTINED" and detail:
                    # Expect detail like: 'Moved from /orig/path due to invalid data; see /tmp/..'
                    m = re.search(r"Moved from (.+?) due to", detail)
                    if m:
                        return m.group(1)
            except Exception as e:
                logger.debug(f"Failed to parse action log for {qpath}: {e}")
                continue
        return None

    def show(self):
        qt = self.qt
        self.dlg = qt.QDialog(self.parent)
        self.dlg.setWindowTitle("Quarantined Files")
        self.dlg.resize(900, 420)

        layout = qt.QVBoxLayout(self.dlg)
        
        self._setup_table(layout)
        self._setup_buttons(layout)
        self._populate_table()
        
        # Connect main buttons
        self.open_btn.clicked.connect(self._on_open_location)
        self.delete_btn.clicked.connect(self._on_delete_file)
        self.restore_btn.clicked.connect(self._on_restore_file)

        btns = qt.QDialogButtonBox(qt.QDialogButtonBox.Close)
        btns.rejected.connect(self.dlg.reject)
        layout.addWidget(btns)

        self.dlg.exec()

    def _setup_table(self, layout):
        qt = self.qt
        self.table = qt.QTableWidget(self.dlg)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Path", "Size", "MTime", "Status"])
        self.table.setEditTriggers(qt.QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(qt.QTableWidget.SelectRows)
        self.table.setSelectionMode(qt.QTableWidget.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table)

    def _setup_buttons(self, layout):
        qt = self.qt
        btn_layout = qt.QHBoxLayout()
        self.open_btn = qt.QPushButton("Open Location")
        self.restore_btn = qt.QPushButton("Restore")
        self.delete_btn = qt.QPushButton("Delete")
        
        for btn in [self.open_btn, self.restore_btn, self.delete_btn]:
            btn.setEnabled(False)
            btn_layout.addWidget(btn)
            
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _populate_table(self):
        qt = self.qt
        # Find quarantined entries
        rows = [e for e in self.db.get_all_entries() if getattr(e, "status", "") == "CORRUPT"]
        self.table.setRowCount(len(rows))
        for i, e in enumerate(rows):
            try:
                self.table.setItem(i, 0, qt.QTableWidgetItem(str(e.path)))
                self.table.setItem(i, 1, qt.QTableWidgetItem(str(e.size)))
                
                try:
                    m = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(e.mtime))
                except Exception:
                    m = str(e.mtime)
                self.table.setItem(i, 2, qt.QTableWidgetItem(m))
                self.table.setItem(i, 3, qt.QTableWidgetItem(str(e.status)))
            except Exception as ex:
                logger.error(f"Failed to populate row {i} in QuarantineDialog: {ex}")
                continue

        self.table.resizeColumnsToContents()

    def _on_selection_changed(self):
        sel = self.table.selectedItems()
        ok = bool(sel)
        self.open_btn.setEnabled(ok)
        self.restore_btn.setEnabled(ok)
        self.delete_btn.setEnabled(ok)

    def _get_selected_path(self) -> Optional[Path]:
        sel = self.table.selectedItems()
        if not sel:
            return None
        return Path(self.table.item(sel[0].row(), 0).text())

    def _on_open_location(self):
        p = self._get_selected_path()
        if not p:
            return
            
        try:
            if not p.exists():
                self.qt.QMessageBox.information(self.dlg, "Not found", "File not found")
                return

            # Try Qt-native first
            try:
                from PyQt6.QtCore import QUrl
                from PyQt6.QtGui import QDesktopServices

                QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.parent)))
                return
            except Exception as e:
                logger.debug(f"Qt QDesktopServices failed: {e}")
            
            import subprocess
            subprocess.run(["xdg-open", str(p.parent)], check=False)
        except Exception as e:
            logger.error(f"Failed to open location for {p}: {e}")
            self.qt.QMessageBox.warning(self.dlg, "Error", f"Could not open location: {e}")

    def _on_delete_file(self):
        sel = self.table.selectedItems()
        if not sel:
            return
        row = sel[0].row()
        p = Path(self.table.item(row, 0).text())
        
        if not self._confirm_delete(p):
            return
            
        try:
            if p.exists():
                p.unlink()
            # Remove from DB
            try:
                self.db.remove_entry(str(p))
                self.db.log_action(str(p), "DELETED", "User deleted quarantined file")
            except Exception as e:
                logger.error(f"DB update failed after deleting {p}: {e}")
            
            self.table.removeRow(row)
        except Exception as e:
            logger.error(f"File deletion failed for {p}: {e}")
            self.qt.QMessageBox.warning(self.dlg, "Error", f"Could not delete: {e}")

    def _confirm_delete(self, p: Path) -> bool:
        qt = self.qt
        try:
            yes = qt.QMessageBox.question(
                self.dlg,
                "Confirm Delete",
                f"Delete {p.name} from quarantine?",
                qt.QMessageBox.StandardButton.Yes | qt.QMessageBox.StandardButton.No,
            )
            return yes == qt.QMessageBox.StandardButton.Yes
        except Exception as e:
            logger.debug(f"Failed to show confirmation dialog: {e}")
            return True # Fallback safer behavior or assume yes if it fails

    def _on_restore_file(self):
        sel = self.table.selectedItems()
        if not sel:
            return
        row = sel[0].row()
        qpath = self.table.item(row, 0).text()
        p = Path(qpath)
        
        if not p.exists():
            self.qt.QMessageBox.information(self.dlg, "Not found", "Quarantined file not found")
            return

        dest_dir = self._resolve_restore_dest(qpath)
        if not dest_dir:
            return

        new_path = dest_dir / p.name
        try:
            shutil.move(str(p), str(new_path))
            self._update_db_after_restore(qpath, new_path)
            self.table.removeRow(row)
        except Exception as e:
            logger.error(f"Restore failed for {p} to {new_path}: {e}")
            self.qt.QMessageBox.warning(self.dlg, "Error", f"Failed to restore: {e}")

    def _resolve_restore_dest(self, qpath: str) -> Optional[Path]:
        # Try to find original location from action log
        orig = self._find_quarantine_actions(qpath)
        if orig:
            try:
                od = Path(orig).parent
                if od.exists():
                    return od
            except Exception as e:
                logger.debug(f"Failed to check original path existence: {e}")

        # Ask user for destination folder
        try:
            dest_dir = self.qt.QFileDialog.getExistingDirectory(
                self.dlg, "Select destination folder to restore to"
            )
            return Path(dest_dir) if dest_dir else None
        except Exception as e:
            logger.error(f"Failed to open directory dialog: {e}")
            self.qt.QMessageBox.warning(self.dlg, "Error", "Could not get destination")
            return None

    def _update_db_after_restore(self, qpath: str, new_path: Path):
        try:
            entry = self.db.get_entry(qpath)
            if entry:
                entry.path = str(new_path)
                entry.status = "UNKNOWN"
                self.db.update_entry(entry)
                self.db.log_action(str(new_path), "RESTORED", f"Restored from quarantine: {qpath}")
                if qpath != str(new_path):
                    self.db.remove_entry(qpath)
        except Exception as e:
            logger.error(f"DB update failed after restoring {qpath}: {e}")
