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
        self.dlg = None
        self.table = None
        self.filter_edit = None
        self.action_combo = None
        self.unmark_btn = None

    def show(self):
        qt = self.qt
        self.dlg = qt.QDialog(self.parent)
        self.dlg.setWindowTitle("Library Actions")
        self.dlg.resize(800, 400)

        layout = qt.QVBoxLayout(self.dlg)
        
        self._setup_filter_bar(layout)
        self._setup_table(layout)
        self._populate_data()
        self._setup_connections()

        button_box = qt.QDialogButtonBox(qt.QDialogButtonBox.Close)
        button_box.rejected.connect(self.dlg.reject)
        layout.addWidget(button_box)

        self.dlg.exec()

    def _setup_filter_bar(self, layout):
        qt = self.qt
        filter_layout = qt.QHBoxLayout()
        
        filter_layout.addWidget(qt.QLabel("Filter:"))
        self.filter_edit = qt.QLineEdit()
        self.filter_edit.setPlaceholderText("Filter by path or action...")
        filter_layout.addWidget(self.filter_edit)

        filter_layout.addWidget(qt.QLabel("Action:"))
        self.action_combo = qt.QComboBox()
        self.action_combo.addItem("All")
        filter_layout.addWidget(self.action_combo)

        self.unmark_btn = qt.QPushButton("Unmark as compressed")
        self.unmark_btn.setEnabled(False)
        filter_layout.addWidget(self.unmark_btn)

        layout.addLayout(filter_layout)

    def _setup_table(self, layout):
        qt = self.qt
        self.table = qt.QTableWidget(self.dlg)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Path", "Action", "Detail", "Timestamp"])
        self.table.setEditTriggers(qt.QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(qt.QTableWidget.SelectRows)
        self.table.setSelectionMode(qt.QTableWidget.SingleSelection)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

    def _populate_data(self):
        qt = self.qt
        rows = self.db.get_actions(500)
        self.table.setRowCount(len(rows))
        
        distinct_actions = set()
        for i, (path, action, detail, ts) in enumerate(rows):
            self._add_table_row(i, path, action, detail, ts)
            if action:
                distinct_actions.add(action)

        for action in sorted(distinct_actions):
            self.action_combo.addItem(action)
        
        self.table.resizeColumnsToContents()

    def _add_table_row(self, row_idx, path, action, detail, ts):
        qt = self.qt
        try:
            self.table.setItem(row_idx, 0, qt.QTableWidgetItem(str(path)))
            self.table.setItem(row_idx, 1, qt.QTableWidgetItem(str(action)))
            self.table.setItem(row_idx, 2, qt.QTableWidgetItem(str(detail or "")))
            
            timestamp_str = self._format_timestamp(ts)
            self.table.setItem(row_idx, 3, qt.QTableWidgetItem(timestamp_str))
        except Exception as e:
            import logging
            logging.error(f"Failed to add row {row_idx} to ActionsDialog: {e}")

    def _format_timestamp(self, ts):
        try:
            import time
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
        except Exception:
            return str(ts)

    def _setup_connections(self):
        self.filter_edit.textChanged.connect(self._apply_filter)
        self.action_combo.currentIndexChanged.connect(self._apply_filter)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.unmark_btn.clicked.connect(self._unmark_selected)

    def _apply_filter(self):
        query = self.filter_edit.text().lower()
        selected_action = self.action_combo.currentText()
        
        for r in range(self.table.rowCount()):
            is_visible = self._is_row_matching_filter(r, query, selected_action)
            self.table.setRowHidden(r, not is_visible)

    def _is_row_matching_filter(self, row_idx, query, selected_action):
        # Text filter check
        match_text = False
        for c in range(self.table.columnCount()):
            item = self.table.item(row_idx, c)
            if item and query in item.text().lower():
                match_text = True
                break
        
        if not match_text:
            return False
            
        # Action filter check
        if selected_action != "All":
            action_item = self.table.item(row_idx, 1)
            if not action_item or action_item.text() != selected_action:
                return False
                
        return True

    def _on_selection_changed(self):
        has_selection = bool(self.table.selectedItems())
        self.unmark_btn.setEnabled(has_selection)

    def _unmark_selected(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            return
            
        row_idx = selected_items[0].row()
        path_item = self.table.item(row_idx, 0)
        if not path_item:
            return
            
        path = path_item.text()
        try:
            self._process_unmark(path)
        except Exception as e:
            import logging
            logging.error(f"Failed to unmark file {path}: {e}")

    def _process_unmark(self, path):
        entry = self.db.get_entry(path)
        if entry and entry.status == "COMPRESSED":
            entry.status = "UNKNOWN"
            self.db.update_entry(entry)
            self.db.log_action(path, "UNMARK_COMPRESSED", "User unmarked via UI")
            self._apply_filter()
