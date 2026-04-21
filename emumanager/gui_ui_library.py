from __future__ import annotations


class MainWindowUILibraryMixin:
    def setup_dashboard_tab(self, qt, parent):
        layout = qt.QVBoxLayout(parent)

        self.grp_status = qt.QGroupBox("Collection Status")
        status_layout = qt.QGridLayout()

        self.lbl_total_roms = qt.QLabel("Total Files: 0")
        self.lbl_total_roms.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.lbl_systems_count = qt.QLabel("Systems Configured: 0")
        self.lbl_systems_count.setStyleSheet("font-size: 14px;")
        self.lbl_library_size = qt.QLabel("Library Size: 0 GB")
        self.lbl_library_size.setStyleSheet("font-size: 14px;")
        self.lbl_last_scan = qt.QLabel("Last Scan: Never")
        self.lbl_last_scan.setStyleSheet("font-size: 14px; color: #888;")

        status_layout.addWidget(self.lbl_total_roms, 0, 0)
        status_layout.addWidget(self.lbl_systems_count, 0, 1)
        status_layout.addWidget(self.lbl_library_size, 0, 2)
        status_layout.addWidget(self.lbl_last_scan, 1, 0, 1, 3)

        self.grp_status.setLayout(status_layout)
        layout.addWidget(self.grp_status)

        self.grp_quick = qt.QGroupBox("Quick Actions")
        quick_layout = qt.QGridLayout()

        self.btn_quick_organize = self._make_button(
            qt,
            "Organize All Systems",
            attr_name="btn_quick_organize",
            tooltip="Run organization for all detected systems",
            icon_name="SP_FileDialogListView",
            minimum_height=40,
        )
        self.btn_quick_verify = self._make_button(
            qt,
            "Verify All Systems",
            attr_name="btn_quick_verify",
            tooltip="Run verification for all detected systems",
            icon_name="SP_DialogApplyButton",
            minimum_height=40,
        )
        self.btn_quick_clean = self._make_button(
            qt,
            "Clean Junk Files",
            attr_name="btn_quick_clean",
            tooltip="Remove .txt, .url, .nfo and empty folders",
            icon_name="SP_TrashIcon",
            minimum_height=40,
        )
        self.btn_quick_update = self._make_button(
            qt,
            "Update Library Stats",
            attr_name="btn_quick_update",
            tooltip="Rescan library to update statistics",
            icon_name="SP_BrowserReload",
            minimum_height=40,
        )

        quick_layout.addWidget(self.btn_quick_organize, 0, 0)
        quick_layout.addWidget(self.btn_quick_verify, 0, 1)
        quick_layout.addWidget(self.btn_quick_clean, 1, 0)
        quick_layout.addWidget(self.btn_quick_update, 1, 1)

        self.grp_quick.setLayout(quick_layout)
        layout.addWidget(self.grp_quick)
        layout.addStretch()

    def setup_library_tab(self, qt, parent):
        layout = qt.QVBoxLayout(parent)
        layout.addLayout(self._setup_library_top_buttons(qt))

        self.splitter = self._setup_library_lists(qt)
        layout.addWidget(self.splitter)

        self.grp_switch_actions = self._setup_library_switch_actions(qt)
        layout.addWidget(self.grp_switch_actions)

        self.btn_cancel = self._setup_library_cancel_button(qt)
        layout.addWidget(self.btn_cancel)

    def _setup_library_top_buttons(self, qt):
        top_layout = qt.QHBoxLayout()
        self.btn_init = self._make_button(
            qt,
            "Init Structure",
            attr_name="btn_init",
            icon_name="SP_DirHomeIcon",
        )
        self.btn_list = self._make_button(
            qt,
            "Refresh List",
            attr_name="btn_list",
            icon_name="SP_BrowserReload",
        )
        self.btn_add = self._make_button(
            qt,
            "Add ROM",
            attr_name="btn_add",
            icon_name="SP_FileDialogNewFolder",
        )
        self.btn_clear = self._make_button(
            qt,
            "Clear Log",
            attr_name="btn_clear",
            icon_name="SP_DialogDiscardButton",
        )
        self.edit_filter = qt.QLineEdit()
        self.edit_filter.setPlaceholderText("Filter ROMs...")
        self.btn_clear_filter = self._make_button(
            qt,
            "Clear Filter",
            attr_name="btn_clear_filter",
        )

        icon = self._get_icon(qt, "SP_DirOpenIcon")
        if icon:
            self.btn_open_lib.setIcon(icon)

        top_layout.addWidget(self.btn_init)
        top_layout.addWidget(self.btn_list)
        top_layout.addWidget(self.btn_add)
        top_layout.addWidget(self.btn_clear)
        top_layout.addStretch()
        top_layout.addWidget(self.edit_filter)
        top_layout.addWidget(self.btn_clear_filter)
        return top_layout

    def _setup_library_lists(self, qt):
        splitter = qt.QSplitter()
        self.sys_list = qt.QListWidget()
        self.rom_list = qt.QListWidget()
        self.sys_list.setMinimumWidth(180)
        try:
            self.rom_list.setSelectionMode(
                qt.QAbstractItemView.SelectionMode.ExtendedSelection
            )
        except AttributeError:
            self.rom_list.setSelectionMode(qt.QAbstractItemView.ExtendedSelection)
        splitter.addWidget(self.sys_list)
        splitter.addWidget(self.rom_list)

        self.cover_label = qt.QLabel("No Cover")
        if self._qt_enum:
            try:
                self.cover_label.setAlignment(self._qt_enum.AlignmentFlag.AlignCenter)
            except AttributeError:
                self.cover_label.setAlignment(self._qt_enum.AlignCenter)
        self.cover_label.setMinimumWidth(200)
        self.cover_label.setStyleSheet(
            "background-color: #222; color: #888; border: 1px solid #444;"
        )
        self.cover_label.setScaledContents(True)

        try:
            self.cover_label.setSizePolicy(
                qt.QSizePolicy.Policy.Ignored,
                qt.QSizePolicy.Policy.Ignored,
            )
        except AttributeError:
            self.cover_label.setSizePolicy(
                qt.QSizePolicy.Ignored,
                qt.QSizePolicy.Ignored,
            )
        splitter.addWidget(self.cover_label)
        splitter.setSizes([200, 500, 300])
        return splitter

    def _setup_library_switch_actions(self, qt):
        grp = qt.QGroupBox("Selected Item Actions")
        action_layout = qt.QHBoxLayout()
        self.btn_compress = self._make_button(
            qt,
            "Compress",
            attr_name="btn_compress",
            icon_name="SP_ArrowDown",
        )
        self.btn_recompress = self._make_button(
            qt,
            "Recompress",
            attr_name="btn_recompress",
            icon_name="SP_ArrowRight",
        )
        self.btn_decompress = self._make_button(
            qt,
            "Decompress",
            attr_name="btn_decompress",
            icon_name="SP_ArrowUp",
        )

        action_layout.addWidget(self.btn_compress)
        action_layout.addWidget(self.btn_recompress)
        action_layout.addWidget(self.btn_decompress)
        grp.setLayout(action_layout)
        grp.setVisible(False)
        return grp

    def _setup_library_cancel_button(self, qt):
        btn = self._make_button(
            qt,
            "Cancel Current Task",
            icon_name="SP_DialogCancelButton",
        )
        btn.setStyleSheet("background-color: #5a2a2a;")
        return btn
