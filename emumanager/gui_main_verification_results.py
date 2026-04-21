from __future__ import annotations

from pathlib import Path
from typing import Optional


class MainWindowVerificationResultsMixin:
    def _populate_verification_results(
        self, results, status_filter: Optional[str] = None
    ):
        filtered = [
            result for result in results if (not status_filter or result.status == status_filter)
        ]
        self.ui.table_results.setRowCount(len(filtered))
        for i, result in enumerate(filtered):
            self._create_result_row(i, result)

    def _create_result_row(self, row_idx, result):
        qt = self._qtwidgets

        item_status = qt.QTableWidgetItem(result.status)
        self._style_status_item(item_status, result.status)
        self.ui.table_results.setItem(row_idx, 0, item_status)

        self.ui.table_results.setItem(row_idx, 1, qt.QTableWidgetItem(result.filename))
        self.ui.table_results.setItem(
            row_idx, 2, qt.QTableWidgetItem(result.match_name or "")
        )
        self.ui.table_results.setItem(
            row_idx, 3, qt.QTableWidgetItem(result.dat_name or "")
        )
        self.ui.table_results.setItem(row_idx, 4, qt.QTableWidgetItem(result.crc or ""))
        self.ui.table_results.setItem(row_idx, 5, qt.QTableWidgetItem(result.sha1 or ""))

        try:
            self.ui.table_results.setItem(
                row_idx, 6, qt.QTableWidgetItem(getattr(result, "md5", "") or "")
            )
            self.ui.table_results.setItem(
                row_idx, 7, qt.QTableWidgetItem(getattr(result, "sha256", "") or "")
            )
            note = ""
            if getattr(result, "status", None) == "HASH_FAILED":
                note = result.match_name or "Hashing failed"
            elif getattr(result, "status", None) == "MISMATCH":
                note = result.match_name or ""
            self.ui.table_results.setItem(row_idx, 8, qt.QTableWidgetItem(note))
        except Exception:
            pass

    def _style_status_item(self, item, status):
        qt = self._qtwidgets
        if status == "VERIFIED":
            bg_color = (
                self._qtgui.QColor(200, 255, 200)
                if self._qtgui
                else qt.QColor(0, 255, 0)
            )
            fg_color = (
                self._qtgui.QColor(0, 100, 0) if self._qtgui else qt.QColor(0, 0, 0)
            )
        else:
            bg_color = (
                self._qtgui.QColor(255, 200, 200)
                if self._qtgui
                else qt.QColor(255, 0, 0)
            )
            fg_color = (
                self._qtgui.QColor(100, 0, 0) if self._qtgui else qt.QColor(0, 0, 0)
            )

        item.setBackground(bg_color)
        item.setForeground(fg_color)

    def _on_verification_item_dblclick(self, item):
        try:
            row = item.row()
            results = getattr(self, "_last_verify_results", [])
            if 0 <= row < len(results):
                full_path = results[row].full_path
                if full_path:
                    self._open_file_location(Path(full_path))
        except Exception:
            pass

    def on_verification_filter_changed(self):
        status = None
        if hasattr(self.ui, "combo_verif_filter"):
            txt = self.ui.combo_verif_filter.currentText()
            if txt in ("VERIFIED", "UNKNOWN", "HASH_FAILED"):
                status = txt
        results = getattr(self, "_last_verify_results", [])
        self._populate_verification_results(results, status)

    def on_export_verification_csv(self):
        qt = self._qtwidgets
        results = self._get_filtered_verification_results()
        if not results:
            self.log_msg("No results to export.")
            return
        path = self._ask_export_path(qt) or str(
            (self._last_base or Path(".")) / "verification_results.csv"
        )
        self._write_verification_csv(path, results)

    def _get_filtered_verification_results(self):
        all_results = getattr(self, "_last_verify_results", [])
        status = None
        if hasattr(self.ui, "combo_verif_filter"):
            txt = self.ui.combo_verif_filter.currentText()
            if txt in ("VERIFIED", "UNKNOWN", "HASH_FAILED"):
                status = txt
        return [result for result in all_results if (not status or result.status == status)]

    def _ask_export_path(self, qt):
        try:
            dlg = qt.QFileDialog(self.window, "Export Verification CSV")
            try:
                dlg.setAcceptMode(qt.QFileDialog.AcceptMode.AcceptSave)
            except AttributeError:
                dlg.setAcceptMode(qt.QFileDialog.AcceptSave)
            dlg.setNameFilter("CSV Files (*.csv)")
            if dlg.exec():
                return dlg.selectedFiles()[0]
        except Exception:
            pass
        return None

    def _write_verification_csv(self, path, results):
        try:
            import csv

            with open(path, "w", newline="") as file_obj:
                writer = csv.writer(file_obj)
                writer.writerow(
                    [
                        "Status",
                        "File Name",
                        "Game Name",
                        "CRC32",
                        "SHA1",
                        "MD5",
                        "SHA256",
                    ]
                )
                for result in results:
                    writer.writerow(
                        [
                            result.status,
                            result.filename,
                            result.match_name or "",
                            result.crc or "",
                            result.sha1 or "",
                            getattr(result, "md5", "") or "",
                            getattr(result, "sha256", "") or "",
                        ]
                    )
            self.log_msg(f"Exported CSV: {path}")
        except Exception as e:
            self.log_msg(f"Export CSV error: {e}")
