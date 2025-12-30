from __future__ import annotations

"""Dialog to display library action history."""


class ActionsDialog:
    """Simple Qt dialog to show recent library actions from LibraryDB.

    This module is kept minimal to avoid heavy Qt imports here; the caller
    must pass the QtWidgets module as `qt` and a `parent` widget.
    """

    def __init__(self, qt, parent, library_db):
        self.qt = qt
        self.parent = parent
        self.db = library_db

    def show(self):
        qt = self.qt
        dlg = qt.QDialog(self.parent)
        dlg.setWindowTitle("Library Actions")
        dlg.resize(800, 400)

        layout = qt.QVBoxLayout(dlg)

        # Search / filter row
        filter_layout = qt.QHBoxLayout()
        filter_layout.addWidget(qt.QLabel("Filter:"))
        filter_edit = qt.QLineEdit()
        filter_edit.setPlaceholderText("Filter by path or action...")
        filter_layout.addWidget(filter_edit)

        filter_layout.addWidget(qt.QLabel("Action:"))
        action_combo = qt.QComboBox()
        action_combo.addItem("All")
        filter_layout.addWidget(action_combo)

        # Unmark button to clear COMPRESSED status for selected entry
        unmark_btn = qt.QPushButton("Unmark as compressed")
        unmark_btn.setEnabled(False)
        filter_layout.addWidget(unmark_btn)

        layout.addLayout(filter_layout)

        table = qt.QTableWidget(dlg)
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Path", "Action", "Detail", "Timestamp"])
        table.setEditTriggers(qt.QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(qt.QTableWidget.SelectRows)
        table.setSelectionMode(qt.QTableWidget.SingleSelection)
        table.setSortingEnabled(True)

        rows = self.db.get_actions(500)
        table.setRowCount(len(rows))
        for i, (path, action, detail, ts) in enumerate(rows):
            try:
                table.setItem(i, 0, qt.QTableWidgetItem(str(path)))
                table.setItem(i, 1, qt.QTableWidgetItem(str(action)))
                table.setItem(i, 2, qt.QTableWidgetItem(str(detail or "")))
                # Convert ts to readable string if possible
                try:
                    import time

                    ts_s = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
                except Exception:
                    ts_s = str(ts)
                table.setItem(i, 3, qt.QTableWidgetItem(ts_s))
            except Exception:
                # Skip malformed rows
                continue

        # Populate action combo with distinct actions
        actions = sorted({a for (_, a, _, _) in rows if a})
        for a in actions:
            action_combo.addItem(a)

        table.resizeColumnsToContents()
        layout.addWidget(table)

        def apply_filter():
            q = filter_edit.text().lower()
            selected_action = action_combo.currentText()
            for r in range(table.rowCount()):
                visible = False
                for c in range(table.columnCount()):
                    item = table.item(r, c)
                    if item and q in item.text().lower():
                        visible = True
                        break
                # Apply action filter
                if selected_action and selected_action != "All":
                    act_item = table.item(r, 1)
                    if not act_item or act_item.text() != selected_action:
                        visible = False
                table.setRowHidden(r, not visible)

        filter_edit.textChanged.connect(apply_filter)
        action_combo.currentIndexChanged.connect(lambda _: apply_filter())

        def on_selection_changed():
            sel = table.selectedItems()
            unmark_btn.setEnabled(bool(sel))

        table.itemSelectionChanged.connect(on_selection_changed)

        def unmark_selected():
            sel = table.selectedItems()
            if not sel:
                return
            row = sel[0].row()
            path_item = table.item(row, 0)
            if not path_item:
                return
            path = path_item.text()
            try:
                db = self.db
                entry = db.get_entry(path)
                if entry and entry.status == "COMPRESSED":
                    entry.status = "UNKNOWN"
                    db.update_entry(entry)
                    db.log_action(path, "UNMARK_COMPRESSED", "User unmarked via UI")
                    apply_filter()
            except Exception:
                pass

        unmark_btn.clicked.connect(unmark_selected)

        btns = qt.QDialogButtonBox(qt.QDialogButtonBox.Close)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        dlg.exec()
