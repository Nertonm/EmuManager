from __future__ import annotations


class MainWindowUIExtraTabsMixin:
    def setup_verification_tab(self, qt, parent):
        layout = qt.QVBoxLayout(parent)

        grp_dat = qt.QGroupBox("No-Intro / Redump Verification")
        dat_layout = qt.QVBoxLayout()

        dat_file_layout = qt.QHBoxLayout()
        self.lbl_dat_path = qt.QLabel("No DAT file selected")
        self.lbl_dat_path.setStyleSheet("color: #aaa; font-style: italic;")
        self.btn_select_dat = self._make_button(
            qt,
            "Select DAT File (.xml/.dat)",
            attr_name="btn_select_dat",
            icon_name="SP_DialogOpenButton",
        )

        dat_file_layout.addWidget(self.btn_select_dat)
        dat_file_layout.addWidget(self.lbl_dat_path)
        dat_file_layout.addStretch()
        dat_layout.addLayout(dat_file_layout)

        self.btn_update_dats = self._make_button(
            qt,
            "Download/Update DATs (No-Intro/Redump)",
            attr_name="btn_update_dats",
            tooltip="Download latest DAT files from Libretro database",
            icon_name="SP_BrowserReload",
        )

        self.btn_verify_dat = self._make_button(
            qt,
            "Verify Library against DAT",
            attr_name="btn_verify_dat",
            tooltip=(
                "Hashes all files in the current library and checks against the "
                "selected DAT file (or auto-detects if none selected)."
            ),
            icon_name="SP_DialogApplyButton",
            enabled=False,
        )

        self.btn_identify_all = self._make_button(
            qt,
            "Identify Files (Scan All DATs)",
            attr_name="btn_identify_all",
            tooltip=(
                "Loads ALL available DAT files into memory and scans the library "
                "to identify unknown files. (Heavy operation!)"
            ),
            icon_name="SP_FileDialogDetailedView",
            enabled=False,
        )

        dat_layout.addWidget(self.btn_update_dats)
        dat_layout.addWidget(self.btn_verify_dat)
        dat_layout.addWidget(self.btn_identify_all)

        grp_dat.setLayout(dat_layout)
        layout.addWidget(grp_dat)

        self.grp_results = qt.QGroupBox("Verification Results")
        results_layout = qt.QVBoxLayout()
        controls_layout = qt.QHBoxLayout()
        self.combo_verif_filter = qt.QComboBox()
        self.combo_verif_filter.addItems(["All", "VERIFIED", "UNKNOWN", "HASH_FAILED"])
        self.btn_export_csv = self._make_button(
            qt,
            "Export CSV",
            attr_name="btn_export_csv",
        )
        self.btn_try_rehash = self._make_button(
            qt,
            "Try Rehash Selected",
            attr_name="btn_try_rehash",
        )
        controls_layout.addWidget(self.combo_verif_filter)
        controls_layout.addWidget(self.btn_export_csv)
        controls_layout.addWidget(self.btn_try_rehash)
        controls_layout.addStretch()
        results_layout.addLayout(controls_layout)

        self.table_results = qt.QTableWidget()
        self.table_results.setColumnCount(9)
        self.table_results.setHorizontalHeaderLabels(
            [
                "Status",
                "File Name",
                "Game Name (DAT)",
                "Source DAT",
                "CRC32",
                "SHA1",
                "MD5",
                "SHA256",
                "Note",
            ]
        )
        try:
            self.table_results.setSortingEnabled(True)
        except Exception:
            pass
        header = self.table_results.horizontalHeader()
        try:
            header.setSectionResizeMode(0, qt.QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, qt.QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, qt.QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(3, qt.QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(4, qt.QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(5, qt.QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(6, qt.QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(8, qt.QHeaderView.ResizeMode.ResizeToContents)
        except AttributeError:
            pass

        results_layout.addWidget(self.table_results)
        self.grp_results.setLayout(results_layout)
        layout.addWidget(self.grp_results)

        grp_dolphin = qt.QGroupBox("GameCube / Wii Verification")
        dolphin_layout = qt.QVBoxLayout()
        lbl_dolphin = qt.QLabel(
            "For GameCube and Wii, use the 'Tools' tab -> 'GameCube / Wii' -> "
            "'Identify & Verify Games'.\nThis uses Dolphin's internal verification "
            "tool which is recommended for ISO/RVZ/WBFS."
        )
        lbl_dolphin.setWordWrap(True)
        dolphin_layout.addWidget(lbl_dolphin)
        grp_dolphin.setLayout(dolphin_layout)

        layout.addWidget(grp_dolphin)
        layout.addStretch()

    def setup_settings_tab(self, qt, parent):
        layout = qt.QFormLayout(parent)

        self.chk_dry_run = qt.QCheckBox("Dry Run (Simulation only)")
        self.chk_dry_run.setChecked(False)
        layout.addRow("Global:", self.chk_dry_run)

        self.spin_level = qt.QSpinBox()
        self.spin_level.setRange(1, 22)
        self.spin_level.setValue(3)
        layout.addRow("Compression Level:", self.spin_level)

        self.combo_profile = qt.QComboBox()
        self.combo_profile.addItems(["None", "fast", "balanced", "best"])
        self.combo_profile.setCurrentText("None")
        layout.addRow("Compression Profile:", self.combo_profile)

        self.chk_rm_originals = qt.QCheckBox("Remove Originals after Compression")
        layout.addRow("Cleanup:", self.chk_rm_originals)

        self.chk_quarantine = qt.QCheckBox("Quarantine Bad Files")
        layout.addRow("Health Check:", self.chk_quarantine)

        self.chk_deep_verify = qt.QCheckBox("Deep Verify (Calculate Hashes)")
        layout.addRow("Verification:", self.chk_deep_verify)

        self.chk_recursive = qt.QCheckBox("Recursive Scan")
        self.chk_recursive.setChecked(True)
        layout.addRow("Scanning:", self.chk_recursive)

        self.chk_process_selected = qt.QCheckBox("Process Selected Files Only")
        self.chk_process_selected.setToolTip(
            "If checked, operations will only apply to files selected in the "
            "Library tab."
        )
        layout.addRow("Selection:", self.chk_process_selected)

        self.chk_standardize_names = qt.QCheckBox("Enforce Standard Naming")
        self.chk_standardize_names.setToolTip(
            "Rename files to a strict standard (e.g. NoIntro/Redump style) "
            "where possible."
        )
        layout.addRow("Renaming:", self.chk_standardize_names)

    def setup_gallery_tab(self, qt, parent):
        layout = qt.QVBoxLayout(parent)

        top_layout = qt.QHBoxLayout()
        top_layout.addWidget(qt.QLabel("System:"))
        self.combo_gallery_system = qt.QComboBox()
        self.combo_gallery_system.setMinimumWidth(200)
        top_layout.addWidget(self.combo_gallery_system)

        self.btn_gallery_refresh = self._make_button(
            qt,
            "Refresh Gallery",
            attr_name="btn_gallery_refresh",
            icon_name="SP_BrowserReload",
        )
        top_layout.addWidget(self.btn_gallery_refresh)

        top_layout.addStretch()
        layout.addLayout(top_layout)

        self.list_gallery = qt.QListWidget()
        try:
            self.list_gallery.setViewMode(qt.QListWidget.ViewMode.IconMode)
        except AttributeError:
            self.list_gallery.setViewMode(qt.QListWidget.IconMode)

        try:
            self.list_gallery.setResizeMode(qt.QListWidget.ResizeMode.Adjust)
        except AttributeError:
            self.list_gallery.setResizeMode(qt.QListWidget.Adjust)

        try:
            self.list_gallery.setMovement(qt.QListWidget.Movement.Static)
        except AttributeError:
            self.list_gallery.setMovement(qt.QListWidget.Static)

        if self._q_size:
            self.list_gallery.setIconSize(self._q_size(140, 200))
        self.list_gallery.setSpacing(15)
        layout.addWidget(self.list_gallery)

    def setup_duplicates_tab(self, qt, parent):
        layout = qt.QVBoxLayout(parent)

        controls = qt.QHBoxLayout()
        self.btn_dups_scan = self._make_button(
            qt,
            "Scan Duplicates",
            attr_name="btn_dups_scan",
            icon_name="SP_BrowserReload",
        )

        self.chk_dups_include_name = qt.QCheckBox("Include name-based duplicates")
        self.chk_dups_include_name.setChecked(True)
        self.chk_dups_filter_non_games = qt.QCheckBox("Filter non-game files")
        self.chk_dups_filter_non_games.setChecked(True)

        self.lbl_dups_summary = qt.QLabel("No scan yet")
        self.lbl_dups_summary.setStyleSheet("color: #aaa; font-style: italic;")

        controls.addWidget(self.btn_dups_scan)
        controls.addWidget(self.chk_dups_include_name)
        controls.addWidget(self.chk_dups_filter_non_games)
        controls.addStretch()
        controls.addWidget(self.lbl_dups_summary)
        layout.addLayout(controls)

        splitter = qt.QSplitter()
        self.list_dups_groups = qt.QListWidget()
        self.list_dups_groups.setMinimumWidth(320)

        right = qt.QWidget()
        right_layout = qt.QVBoxLayout(right)

        self.table_dups_entries = qt.QTableWidget()
        self.table_dups_entries.setColumnCount(5)
        self.table_dups_entries.setHorizontalHeaderLabels(
            ["Keep?", "System", "File", "Size", "Path"]
        )
        try:
            self.table_dups_entries.setSortingEnabled(True)
        except Exception:
            pass

        try:
            header = self.table_dups_entries.horizontalHeader()
            try:
                header.setSectionResizeMode(2, qt.QHeaderView.ResizeMode.Stretch)
                header.setSectionResizeMode(4, qt.QHeaderView.ResizeMode.Stretch)
                header.setSectionResizeMode(
                    3,
                    qt.QHeaderView.ResizeMode.ResizeToContents,
                )
            except Exception:
                try:
                    header.setSectionResizeMode(2, qt.QHeaderView.Stretch)
                    header.setSectionResizeMode(4, qt.QHeaderView.Stretch)
                    header.setSectionResizeMode(3, qt.QHeaderView.ResizeToContents)
                except Exception:
                    pass
            try:
                self.table_dups_entries.setColumnWidth(3, 120)
            except Exception:
                pass
            try:
                header.setStretchLastSection(True)
            except Exception:
                pass
        except Exception:
            pass

        actions = qt.QHBoxLayout()
        self.btn_dups_move_others = qt.QPushButton("Move others to duplicates/")
        self.btn_dups_keep_largest = qt.QPushButton("Keep largest")
        self.btn_dups_keep_smallest = qt.QPushButton("Keep smallest")
        self.btn_dups_open_location = qt.QPushButton("Open location")

        actions.addWidget(self.btn_dups_move_others)
        actions.addWidget(self.btn_dups_keep_largest)
        actions.addWidget(self.btn_dups_keep_smallest)
        actions.addWidget(self.btn_dups_open_location)
        actions.addStretch()

        right_layout.addWidget(self.table_dups_entries)
        right_layout.addLayout(actions)

        splitter.addWidget(self.list_dups_groups)
        splitter.addWidget(right)
        splitter.setSizes([350, 650])
        layout.addWidget(splitter)
