# -*- coding: utf-8 -*-
from typing import Any

# Common button labels to reduce duplication
IDENTIFY_VERIFY_LABEL = "Identify & Verify Games"
ORGANIZE_LABEL = "Organize (Rename)"


class Ui_MainWindow:
    def setupUi(self, MainWindow, qtwidgets: Any):
        qt = qtwidgets
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(900, 700)

        self.centralwidget = qt.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = qt.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")

        # Top Bar: Library Selection
        self.top_bar_layout = qt.QHBoxLayout()
        self.label_lib_title = qt.QLabel(self.centralwidget)
        self.label_lib_title.setText("Current Library:")
        self.top_bar_layout.addWidget(self.label_lib_title)

        self.lbl_library = qt.QLabel(self.centralwidget)
        self.lbl_library.setText("No library open")
        self.lbl_library.setStyleSheet("font-weight: bold; color: #aaa;")
        self.top_bar_layout.addWidget(self.lbl_library)

        self.btn_open_lib = qt.QPushButton(self.centralwidget)
        self.btn_open_lib.setText("Open Library")
        self.top_bar_layout.addWidget(self.btn_open_lib)

        self.top_bar_layout.addStretch()
        self.verticalLayout.addLayout(self.top_bar_layout)

        # Tabs
        self.tabs = qt.QTabWidget(self.centralwidget)
        self.tabs.setObjectName("tabs")

        # --- Tab 0: Dashboard ---
        self.tab_dashboard = qt.QWidget()
        self.tab_dashboard.setObjectName("tab_dashboard")
        self.setupDashboardTab(qt, self.tab_dashboard)
        self.tabs.addTab(self.tab_dashboard, "Dashboard")

        # --- Tab 1: Library ---
        self.tab_library = qt.QWidget()
        self.tab_library.setObjectName("tab_library")
        self.setupLibraryTab(qt, self.tab_library)
        self.tabs.addTab(self.tab_library, "Library")

        # --- Tab 2: Tools ---
        self.tab_tools = qt.QWidget()
        self.tab_tools.setObjectName("tab_tools")
        self.setupToolsTab(qt, self.tab_tools)
        self.tabs.addTab(self.tab_tools, "Tools")

        # --- Tab 3: Verification ---
        self.tab_verification = qt.QWidget()
        self.tab_verification.setObjectName("tab_verification")
        self.setup_verification_tab(qt, self.tab_verification)
        self.tabs.addTab(self.tab_verification, "Verification")

        # --- Tab 4: Settings ---
        self.tab_settings = qt.QWidget()
        self.tab_settings.setObjectName("tab_settings")
        self.setup_settings_tab(qt, self.tab_settings)
        self.tabs.addTab(self.tab_settings, "Settings")

        self.verticalLayout.addWidget(self.tabs)

        # Log as Dockable panel
        self.log = qt.QTextEdit()
        self.log.setReadOnly(True)
        self.log.setObjectName("log")
        self.log_dock = qt.QDockWidget("Log")
        self.log_dock.setObjectName("log_dock")
        self.log_dock.setWidget(self.log)
        # Add dock to bottom with robust enum resolution
        _Qt = None
        try:
            from PyQt6.QtCore import Qt as _Qt
        except Exception:
            try:
                from PySide6.QtCore import Qt as _Qt
            except Exception:
                _Qt = None
        try:
            if _Qt is not None:
                try:
                    MainWindow.addDockWidget(
                        _Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock
                    )
                except Exception:
                    MainWindow.addDockWidget(_Qt.BottomDockWidgetArea, self.log_dock)
            else:
                # Fallback to bottom via numeric value (8)
                MainWindow.addDockWidget(8, self.log_dock)
        except Exception:
            # As last resort, just add without area (some bindings may allow it)
            try:
                MainWindow.addDockWidget(self.log_dock)
            except Exception:
                pass

        MainWindow.setCentralWidget(self.centralwidget)

        # Status bar
        self.statusbar = qt.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        # Progress Bar
        self.progress_bar = qt.QProgressBar(self.statusbar)
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.statusbar.addPermanentWidget(self.progress_bar)

        self.retranslate_ui(MainWindow)
        self.tabs.setCurrentIndex(0)

    def _get_icon(self, qt, name: str):
        """Return a QIcon for a given QStyle StandardPixmap name, with fallbacks."""
        try:
            style = qt.QApplication.style()
            try:
                # Qt6 style
                attr = getattr(qt.QStyle.StandardPixmap, name)
                return style.standardIcon(attr)
            except Exception:
                try:
                    # Fallback for older enum location
                    attr = getattr(qt.QStyle, name)
                    return style.standardIcon(attr)
                except Exception:
                    return None
        except Exception:
            return None

    def setupDashboardTab(self, qt, parent):
        layout = qt.QVBoxLayout(parent)

        # Welcome / Status Section
        self.grp_status = qt.QGroupBox("Collection Status")
        status_layout = qt.QGridLayout()

        self.lbl_total_roms = qt.QLabel("Total Files: 0")
        self.lbl_total_roms.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.lbl_systems_count = qt.QLabel("Systems Configured: 0")
        self.lbl_systems_count.setStyleSheet("font-size: 14px;")

        status_layout.addWidget(self.lbl_total_roms, 0, 0)
        status_layout.addWidget(self.lbl_systems_count, 0, 1)

        self.grp_status.setLayout(status_layout)
        layout.addWidget(self.grp_status)

        # Quick Actions Section
        self.grp_quick = qt.QGroupBox("Quick Actions")
        quick_layout = qt.QGridLayout()

        self.btn_quick_organize = qt.QPushButton("Organize All Systems")
        self.btn_quick_organize.setToolTip("Run organization for all detected systems")
        self.btn_quick_organize.setMinimumHeight(40)

        self.btn_quick_verify = qt.QPushButton("Verify All Systems")
        self.btn_quick_verify.setToolTip("Run verification for all detected systems")
        self.btn_quick_verify.setMinimumHeight(40)

        self.btn_quick_clean = qt.QPushButton("Clean Junk Files")
        self.btn_quick_clean.setToolTip("Remove .txt, .url, .nfo and empty folders")
        self.btn_quick_clean.setMinimumHeight(40)

        self.btn_quick_update = qt.QPushButton("Update Library Stats")
        self.btn_quick_update.setToolTip("Rescan library to update statistics")
        self.btn_quick_update.setMinimumHeight(40)

        # Icons
        ic = self._get_icon(qt, "SP_FileDialogListView")
        if ic:
            self.btn_quick_organize.setIcon(ic)
        ic = self._get_icon(qt, "SP_DialogApplyButton")
        if ic:
            self.btn_quick_verify.setIcon(ic)
        ic = self._get_icon(qt, "SP_TrashIcon")
        if ic:
            self.btn_quick_clean.setIcon(ic)
        ic = self._get_icon(qt, "SP_BrowserReload")
        if ic:
            self.btn_quick_update.setIcon(ic)

        quick_layout.addWidget(self.btn_quick_organize, 0, 0)
        quick_layout.addWidget(self.btn_quick_verify, 0, 1)
        quick_layout.addWidget(self.btn_quick_clean, 1, 0)
        quick_layout.addWidget(self.btn_quick_update, 1, 1)

        self.grp_quick.setLayout(quick_layout)
        layout.addWidget(self.grp_quick)

        layout.addStretch()

    def setupLibraryTab(self, qt, parent):
        layout = qt.QVBoxLayout(parent)

        # Top buttons
        top_layout = qt.QHBoxLayout()
        self.btn_init = qt.QPushButton("Init Structure")
        self.btn_list = qt.QPushButton("Refresh List")
        self.btn_add = qt.QPushButton("Add ROM")
        self.btn_clear = qt.QPushButton("Clear Log")
        # Filter box
        self.edit_filter = qt.QLineEdit()
        self.edit_filter.setPlaceholderText("Filter ROMs...")
        self.btn_clear_filter = qt.QPushButton("Clear Filter")

        # Add Icons via helper
        ic = self._get_icon(qt, "SP_DirHomeIcon")
        if ic:
            self.btn_init.setIcon(ic)
        ic = self._get_icon(qt, "SP_BrowserReload")
        if ic:
            self.btn_list.setIcon(ic)
        ic = self._get_icon(qt, "SP_FileDialogNewFolder")
        if ic:
            self.btn_add.setIcon(ic)
        ic = self._get_icon(qt, "SP_DialogDiscardButton")
        if ic:
            self.btn_clear.setIcon(ic)
        ic = self._get_icon(qt, "SP_DirOpenIcon")
        if ic:
            self.btn_open_lib.setIcon(ic)

        top_layout.addWidget(self.btn_init)
        top_layout.addWidget(self.btn_list)
        top_layout.addWidget(self.btn_add)
        top_layout.addWidget(self.btn_clear)
        top_layout.addStretch()
        top_layout.addWidget(self.edit_filter)
        top_layout.addWidget(self.btn_clear_filter)
        layout.addLayout(top_layout)

        # Splitter for lists
        self.splitter = qt.QSplitter()
        self.sys_list = qt.QListWidget()
        self.rom_list = qt.QListWidget()
        self.sys_list.setMinimumWidth(180)
        try:
            self.rom_list.setSelectionMode(
                qt.QAbstractItemView.SelectionMode.ExtendedSelection
            )
        except AttributeError:
            self.rom_list.setSelectionMode(qt.QAbstractItemView.ExtendedSelection)
        self.splitter.addWidget(self.sys_list)
        self.splitter.addWidget(self.rom_list)
        layout.addWidget(self.splitter)

        # Switch Actions Group
        self.grp_switch_actions = qt.QGroupBox(
            "Switch Compression Tools (Selected File)"
        )
        action_layout = qt.QHBoxLayout()
        self.btn_compress = qt.QPushButton("Compress")
        self.btn_recompress = qt.QPushButton("Recompress")
        self.btn_decompress = qt.QPushButton("Decompress")

        # Set action icons via helper
        ic = self._get_icon(qt, "SP_ArrowDown")
        if ic:
            self.btn_compress.setIcon(ic)
        ic = self._get_icon(qt, "SP_ArrowRight")
        if ic:
            self.btn_recompress.setIcon(ic)
        ic = self._get_icon(qt, "SP_ArrowUp")
        if ic:
            self.btn_decompress.setIcon(ic)

        action_layout.addWidget(self.btn_compress)
        action_layout.addWidget(self.btn_recompress)
        action_layout.addWidget(self.btn_decompress)
        self.grp_switch_actions.setLayout(action_layout)
        self.grp_switch_actions.setVisible(False)
        layout.addWidget(self.grp_switch_actions)

        # Global Cancel
        self.btn_cancel = qt.QPushButton("Cancel Current Task")
        # Set icon for cancel after creation to avoid attribute errors
        ic = self._get_icon(qt, "SP_DialogCancelButton")
        if ic:
            try:
                self.btn_cancel.setIcon(ic)
            except Exception:
                pass
        self.btn_cancel.setStyleSheet("background-color: #5a2a2a;")
        layout.addWidget(self.btn_cancel)

    def setupToolsTab(self, qt, parent):
        layout = qt.QVBoxLayout(parent)
        # Create nested tabs for tools
        self.tools_tabs = qt.QTabWidget()
        layout.addWidget(self.tools_tabs)

        self._setup_switch_tab(qt)
        self._setup_psx_tab(qt)
        self._setup_ps2_tab(qt)
        self._setup_ps3_tab(qt)
        self._setup_psp_tab(qt)
        self._setup_dolphin_tab(qt)
        self._setup_n3ds_tab(qt)
        self._setup_general_tab(qt)

    def _setup_switch_tab(self, qt):
        self.tab_switch = qt.QWidget()
        switch_layout = qt.QVBoxLayout(self.tab_switch)
        grp_switch = qt.QGroupBox("Nintendo Switch Actions")
        grp_switch_layout = qt.QVBoxLayout()
        self.btn_organize = qt.QPushButton("Organize Library (Rename/Move)")
        self.btn_organize.setToolTip(
            "Organizes Switch ROMs based on metadata (TitleID, Version, etc)"
        )
        self.btn_health = qt.QPushButton("Health Check (Integrity + Virus)")
        self.btn_health.setToolTip("Verifies NCA integrity and scans for viruses")
        self.btn_switch_compress = qt.QPushButton("Compress Library (NSP -> NSZ)")
        self.btn_switch_compress.setToolTip(
            "Compresses all NSP files in the library to NSZ format"
        )
        self.btn_switch_decompress = qt.QPushButton("Decompress Library (NSZ -> NSP)")
        self.btn_switch_decompress.setToolTip(
            "Decompresses all NSZ files in the library back to NSP format"
        )
        try:
            style = qt.QApplication.style()
            self.btn_organize.setIcon(
                style.standardIcon(qt.QStyle.StandardPixmap.SP_FileDialogListView)
            )
            self.btn_health.setIcon(
                style.standardIcon(qt.QStyle.StandardPixmap.SP_DialogApplyButton)
            )
            self.btn_switch_compress.setIcon(
                style.standardIcon(qt.QStyle.StandardPixmap.SP_ArrowDown)
            )
            self.btn_switch_decompress.setIcon(
                style.standardIcon(qt.QStyle.StandardPixmap.SP_ArrowUp)
            )
        except Exception:
            try:
                style = qt.QApplication.style()
                self.btn_organize.setIcon(
                    style.standardIcon(qt.QStyle.SP_FileDialogListView)
                )
                self.btn_health.setIcon(
                    style.standardIcon(qt.QStyle.SP_DialogApplyButton)
                )
                self.btn_switch_compress.setIcon(
                    style.standardIcon(qt.QStyle.SP_ArrowDown)
                )
                self.btn_switch_decompress.setIcon(
                    style.standardIcon(qt.QStyle.SP_ArrowUp)
                )
            except Exception:
                pass
        grp_switch_layout.addWidget(self.btn_organize)
        grp_switch_layout.addWidget(self.btn_health)
        grp_switch_layout.addWidget(self.btn_switch_compress)
        grp_switch_layout.addWidget(self.btn_switch_decompress)
        grp_switch.setLayout(grp_switch_layout)
        switch_layout.addWidget(grp_switch)
        switch_layout.addStretch()
        self.tools_tabs.addTab(self.tab_switch, "Switch")

    def _setup_psx_tab(self, qt):
        self.tab_psx = qt.QWidget()
        psx_layout = qt.QVBoxLayout(self.tab_psx)
        grp_psx = qt.QGroupBox("PlayStation 1 Actions")
        grp_psx_layout = qt.QVBoxLayout()
        self.btn_psx_convert = qt.QPushButton("Convert BIN/CUE/ISO to CHD")
        self.btn_psx_convert.setToolTip(
            "Converts PS1 games to CHD format to save space"
        )
        self.btn_psx_verify = qt.QPushButton(IDENTIFY_VERIFY_LABEL)
        self.btn_psx_verify.setToolTip(
            "Scans PS1 games, extracts Serials, and identifies titles"
        )
        self.btn_psx_organize = qt.QPushButton(ORGANIZE_LABEL)
        self.btn_psx_organize.setToolTip(
            "Renames PS1 games based on Serial (e.g. 'Title [Serial].chd')"
        )
        try:
            style = qt.QApplication.style()
            self.btn_psx_convert.setIcon(
                style.standardIcon(qt.QStyle.StandardPixmap.SP_DriveCDIcon)
            )
            self.btn_psx_verify.setIcon(
                style.standardIcon(qt.QStyle.StandardPixmap.SP_DialogApplyButton)
            )
            self.btn_psx_organize.setIcon(
                style.standardIcon(qt.QStyle.StandardPixmap.SP_FileDialogListView)
            )
        except Exception:
            try:
                style = qt.QApplication.style()
                self.btn_psx_convert.setIcon(
                    style.standardIcon(qt.QStyle.SP_DriveCDIcon)
                )
                self.btn_psx_verify.setIcon(
                    style.standardIcon(qt.QStyle.SP_DialogApplyButton)
                )
                self.btn_psx_organize.setIcon(
                    style.standardIcon(qt.QStyle.SP_FileDialogListView)
                )
            except Exception:
                pass
        grp_psx_layout.addWidget(self.btn_psx_convert)
        grp_psx_layout.addWidget(self.btn_psx_verify)
        grp_psx_layout.addWidget(self.btn_psx_organize)
        grp_psx.setLayout(grp_psx_layout)
        psx_layout.addWidget(grp_psx)
        psx_layout.addStretch()
        self.tools_tabs.addTab(self.tab_psx, "PS1")

    def _setup_ps2_tab(self, qt):
        self.tab_ps2 = qt.QWidget()
        ps2_layout = qt.QVBoxLayout(self.tab_ps2)
        grp_ps2 = qt.QGroupBox("PlayStation 2 Actions")
        grp_ps2_layout = qt.QVBoxLayout()
        self.btn_ps2_convert = qt.QPushButton("Convert ISO/CSO to CHD")
        self.btn_ps2_convert.setToolTip(
            "Converts PS2 games to CHD format to save space"
        )
        self.btn_ps2_verify = qt.QPushButton(IDENTIFY_VERIFY_LABEL)
        self.btn_ps2_verify.setToolTip(
            "Scans PS2 games, extracts Serials, and identifies titles"
        )
        self.btn_ps2_organize = qt.QPushButton(ORGANIZE_LABEL)
        self.btn_ps2_organize.setToolTip(
            "Renames PS2 games based on Serial (e.g. 'Title [Serial].iso')"
        )
        try:
            style = qt.QApplication.style()
            self.btn_ps2_convert.setIcon(
                style.standardIcon(qt.QStyle.StandardPixmap.SP_DriveCDIcon)
            )
            self.btn_ps2_verify.setIcon(
                style.standardIcon(qt.QStyle.StandardPixmap.SP_DialogApplyButton)
            )
            self.btn_ps2_organize.setIcon(
                style.standardIcon(qt.QStyle.StandardPixmap.SP_FileDialogListView)
            )
        except Exception:
            try:
                style = qt.QApplication.style()
                self.btn_ps2_convert.setIcon(
                    style.standardIcon(qt.QStyle.SP_DriveCDIcon)
                )
                self.btn_ps2_verify.setIcon(
                    style.standardIcon(qt.QStyle.SP_DialogApplyButton)
                )
                self.btn_ps2_organize.setIcon(
                    style.standardIcon(qt.QStyle.SP_FileDialogListView)
                )
            except Exception:
                pass
        grp_ps2_layout.addWidget(self.btn_ps2_convert)
        grp_ps2_layout.addWidget(self.btn_ps2_verify)
        grp_ps2_layout.addWidget(self.btn_ps2_organize)
        grp_ps2.setLayout(grp_ps2_layout)
        ps2_layout.addWidget(grp_ps2)
        ps2_layout.addStretch()
        self.tools_tabs.addTab(self.tab_ps2, "PS2")

    def _setup_ps3_tab(self, qt):
        self.tab_ps3 = qt.QWidget()
        ps3_layout = qt.QVBoxLayout(self.tab_ps3)
        grp_ps3 = qt.QGroupBox("PlayStation 3 Actions")
        grp_ps3_layout = qt.QVBoxLayout()
        self.btn_ps3_verify = qt.QPushButton(IDENTIFY_VERIFY_LABEL)
        self.btn_ps3_verify.setToolTip(
            "Scans PS3 games (ISO/Folder), extracts Serials, and identifies titles"
        )
        self.btn_ps3_organize = qt.QPushButton(ORGANIZE_LABEL)
        self.btn_ps3_organize.setToolTip(
            "Renames PS3 games based on Serial (e.g. 'Title [Serial]')"
        )
        try:
            style = qt.QApplication.style()
            self.btn_ps3_verify.setIcon(
                style.standardIcon(qt.QStyle.StandardPixmap.SP_DialogApplyButton)
            )
            self.btn_ps3_organize.setIcon(
                style.standardIcon(qt.QStyle.StandardPixmap.SP_FileDialogListView)
            )
        except Exception:
            try:
                style = qt.QApplication.style()
                self.btn_ps3_verify.setIcon(
                    style.standardIcon(qt.QStyle.SP_DialogApplyButton)
                )
                self.btn_ps3_organize.setIcon(
                    style.standardIcon(qt.QStyle.SP_FileDialogListView)
                )
            except Exception:
                pass
        grp_ps3_layout.addWidget(self.btn_ps3_verify)
        grp_ps3_layout.addWidget(self.btn_ps3_organize)
        grp_ps3.setLayout(grp_ps3_layout)
        ps3_layout.addWidget(grp_ps3)
        ps3_layout.addStretch()
        self.tools_tabs.addTab(self.tab_ps3, "PS3")

    def _setup_psp_tab(self, qt):
        self.tab_psp = qt.QWidget()
        psp_layout = qt.QVBoxLayout(self.tab_psp)
        grp_psp = qt.QGroupBox("PlayStation Portable (PSP) Actions")
        grp_psp_layout = qt.QVBoxLayout()
        self.btn_psp_verify = qt.QPushButton(IDENTIFY_VERIFY_LABEL)
        self.btn_psp_verify.setToolTip(
            "Scans PSP games (ISO/CSO/PBP), extracts Serials, and identifies titles"
        )
        self.btn_psp_organize = qt.QPushButton(ORGANIZE_LABEL)
        self.btn_psp_organize.setToolTip(
            "Renames PSP games based on Serial (e.g. 'Title [Serial]')"
        )
        self.btn_psp_compress = qt.QPushButton("Compress ISO to CSO")
        self.btn_psp_compress.setToolTip("Compresses PSP ISO files to CSO format")
        try:
            style = qt.QApplication.style()
            self.btn_psp_verify.setIcon(
                style.standardIcon(qt.QStyle.StandardPixmap.SP_DialogApplyButton)
            )
            self.btn_psp_organize.setIcon(
                style.standardIcon(qt.QStyle.StandardPixmap.SP_FileDialogListView)
            )
            self.btn_psp_compress.setIcon(
                style.standardIcon(qt.QStyle.StandardPixmap.SP_ArrowDown)
            )
        except Exception:
            try:
                style = qt.QApplication.style()
                self.btn_psp_verify.setIcon(
                    style.standardIcon(qt.QStyle.SP_DialogApplyButton)
                )
                self.btn_psp_organize.setIcon(
                    style.standardIcon(qt.QStyle.SP_FileDialogListView)
                )
                self.btn_psp_compress.setIcon(
                    style.standardIcon(qt.QStyle.SP_ArrowDown)
                )
            except Exception:
                pass
        grp_psp_layout.addWidget(self.btn_psp_verify)
        grp_psp_layout.addWidget(self.btn_psp_organize)
        grp_psp_layout.addWidget(self.btn_psp_compress)
        grp_psp.setLayout(grp_psp_layout)
        psp_layout.addWidget(grp_psp)
        psp_layout.addStretch()
        self.tools_tabs.addTab(self.tab_psp, "PSP")

    def _setup_dolphin_tab(self, qt):
        self.tab_dolphin = qt.QWidget()
        dolphin_layout = qt.QVBoxLayout(self.tab_dolphin)
        grp_dolphin = qt.QGroupBox("Dolphin (GC/Wii) Actions")
        grp_dolphin_layout = qt.QVBoxLayout()
        self.btn_dolphin_organize = qt.QPushButton("Organize Library (Rename)")
        self.btn_dolphin_organize.setToolTip(
            "Renames GC/Wii games based on metadata (Internal Name [GameID])"
        )
        self.btn_dolphin_convert = qt.QPushButton("Convert ISO/WBFS to RVZ")
        self.btn_dolphin_convert.setToolTip(
            "Converts GameCube/Wii games to RVZ format (Lossless compression)"
        )
        self.btn_dolphin_verify = qt.QPushButton(IDENTIFY_VERIFY_LABEL)
        self.btn_dolphin_verify.setToolTip(
            "Scans GC/Wii games, extracts IDs, and verifies integrity"
        )
        try:
            style = qt.QApplication.style()
            self.btn_dolphin_organize.setIcon(
                style.standardIcon(qt.QStyle.StandardPixmap.SP_FileDialogListView)
            )
            self.btn_dolphin_convert.setIcon(
                style.standardIcon(qt.QStyle.StandardPixmap.SP_DriveCDIcon)
            )
            self.btn_dolphin_verify.setIcon(
                style.standardIcon(qt.QStyle.StandardPixmap.SP_DialogApplyButton)
            )
        except Exception:
            try:
                style = qt.QApplication.style()
                self.btn_dolphin_organize.setIcon(
                    style.standardIcon(qt.QStyle.SP_FileDialogListView)
                )
                self.btn_dolphin_convert.setIcon(
                    style.standardIcon(qt.QStyle.SP_DriveCDIcon)
                )
                self.btn_dolphin_verify.setIcon(
                    style.standardIcon(qt.QStyle.SP_DialogApplyButton)
                )
            except Exception:
                pass
        grp_dolphin_layout.addWidget(self.btn_dolphin_organize)
        grp_dolphin_layout.addWidget(self.btn_dolphin_convert)
        grp_dolphin_layout.addWidget(self.btn_dolphin_verify)
        grp_dolphin.setLayout(grp_dolphin_layout)
        dolphin_layout.addWidget(grp_dolphin)
        dolphin_layout.addStretch()
        self.tools_tabs.addTab(self.tab_dolphin, "GameCube / Wii")

    def _setup_n3ds_tab(self, qt):
        self.tab_n3ds = qt.QWidget()
        n3ds_layout = qt.QVBoxLayout(self.tab_n3ds)
        grp_n3ds = qt.QGroupBox("Nintendo 3DS Actions")
        grp_n3ds_layout = qt.QVBoxLayout()

        self.btn_n3ds_organize = qt.QPushButton("Organize Library")
        self.btn_n3ds_organize.setToolTip("Organizes 3DS ROMs based on metadata")

        self.btn_n3ds_verify = qt.QPushButton("Verify Library")
        self.btn_n3ds_verify.setToolTip("Verifies 3DS ROMs integrity")

        self.btn_n3ds_compress = qt.QPushButton("Compress to 7z")
        self.btn_n3ds_compress.setToolTip("Compress .3ds/.cia to .7z")

        self.btn_n3ds_decompress = qt.QPushButton("Decompress from 7z")
        self.btn_n3ds_decompress.setToolTip("Decompress .7z to original format")

        grp_n3ds_layout.addWidget(self.btn_n3ds_organize)
        grp_n3ds_layout.addWidget(self.btn_n3ds_verify)
        grp_n3ds_layout.addWidget(self.btn_n3ds_compress)
        grp_n3ds_layout.addWidget(self.btn_n3ds_decompress)

        grp_n3ds.setLayout(grp_n3ds_layout)
        n3ds_layout.addWidget(grp_n3ds)
        n3ds_layout.addStretch()
        self.tools_tabs.addTab(self.tab_n3ds, "Nintendo 3DS")

    def _setup_general_tab(self, qt):
        self.tab_general = qt.QWidget()
        gen_layout = qt.QVBoxLayout(self.tab_general)
        grp_gen = qt.QGroupBox("General Maintenance")
        grp_gen_layout = qt.QVBoxLayout()
        self.btn_clean_junk = qt.QPushButton(
            "Clean Junk Files (.txt, .nfo, empty dirs)"
        )
        try:
            style = qt.QApplication.style()
            self.btn_clean_junk.setIcon(
                style.standardIcon(qt.QStyle.StandardPixmap.SP_TrashIcon)
            )
        except Exception:
            try:
                style = qt.QApplication.style()
                self.btn_clean_junk.setIcon(style.standardIcon(qt.QStyle.SP_TrashIcon))
            except Exception:
                pass
        grp_gen_layout.addWidget(self.btn_clean_junk)
        grp_gen.setLayout(grp_gen_layout)
        gen_layout.addWidget(grp_gen)
        gen_layout.addStretch()
        self.tools_tabs.addTab(self.tab_general, "General")

    def setup_verification_tab(self, qt, parent):
        layout = qt.QVBoxLayout(parent)

        grp_dat = qt.QGroupBox("No-Intro / Redump Verification")
        dat_layout = qt.QVBoxLayout()

        # DAT File Selection
        dat_file_layout = qt.QHBoxLayout()
        self.lbl_dat_path = qt.QLabel("No DAT file selected")
        self.lbl_dat_path.setStyleSheet("color: #aaa; font-style: italic;")
        self.btn_select_dat = qt.QPushButton("Select DAT File (.xml/.dat)")

        dat_file_layout.addWidget(self.btn_select_dat)
        dat_file_layout.addWidget(self.lbl_dat_path)
        dat_file_layout.addStretch()

        dat_layout.addLayout(dat_file_layout)

        self.btn_verify_dat = qt.QPushButton("Verify Library against DAT")
        self.btn_verify_dat.setToolTip(
            "Hashes all files in the current library and checks against the "
            "selected DAT file."
        )
        self.btn_verify_dat.setEnabled(False)  # Disabled until DAT selected

        try:
            style = qt.QApplication.style()
            self.btn_select_dat.setIcon(
                style.standardIcon(qt.QStyle.StandardPixmap.SP_DialogOpenButton)
            )
            self.btn_verify_dat.setIcon(
                style.standardIcon(qt.QStyle.StandardPixmap.SP_DialogApplyButton)
            )
        except Exception:
            try:
                style = qt.QApplication.style()
                self.btn_select_dat.setIcon(
                    style.standardIcon(qt.QStyle.SP_DialogOpenButton)
                )
                self.btn_verify_dat.setIcon(
                    style.standardIcon(qt.QStyle.SP_DialogApplyButton)
                )
            except Exception:
                pass

        dat_layout.addWidget(self.btn_verify_dat)
        grp_dat.setLayout(dat_layout)

        layout.addWidget(grp_dat)

        # Verification Results Table
        self.grp_results = qt.QGroupBox("Verification Results")
        results_layout = qt.QVBoxLayout()
        # Controls row: filter + export
        controls_layout = qt.QHBoxLayout()
        self.combo_verif_filter = qt.QComboBox()
        self.combo_verif_filter.addItems(["All", "VERIFIED", "UNKNOWN"])
        self.btn_export_csv = qt.QPushButton("Export CSV")
        controls_layout.addWidget(self.combo_verif_filter)
        controls_layout.addWidget(self.btn_export_csv)
        controls_layout.addStretch()
        results_layout.addLayout(controls_layout)
        self.table_results = qt.QTableWidget()
        self.table_results.setColumnCount(7)
        self.table_results.setHorizontalHeaderLabels(
            [
                "Status",
                "File Name",
                "Game Name (DAT)",
                "CRC32",
                "SHA1",
                "MD5",
                "SHA256",
            ]
        )
        try:
            # Enable sorting for easier inspection
            self.table_results.setSortingEnabled(True)
        except Exception:
            pass
        # Adjust column widths
        header = self.table_results.horizontalHeader()
        try:
            header.setSectionResizeMode(0, qt.QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, qt.QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, qt.QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(3, qt.QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(4, qt.QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(5, qt.QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(6, qt.QHeaderView.ResizeMode.ResizeToContents)
        except AttributeError:
            # PySide6 / PyQt6 might use different enums or just default behavior
            pass

        results_layout.addWidget(self.table_results)
        self.grp_results.setLayout(results_layout)
        layout.addWidget(self.grp_results)

        # Dolphin Info
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

    def retranslate_ui(self, main_window):
        main_window.setWindowTitle("EmuManager")

    def apply_dark_theme(self, qt, qtgui, window):
        try:
            qt.QApplication.setStyle(qt.QStyleFactory.create("Fusion"))
            palette = qtgui.QPalette()
            palette.setColor(qtgui.QPalette.ColorRole.Window, qtgui.QColor(45, 45, 45))
            palette.setColor(
                qtgui.QPalette.ColorRole.WindowText,
                qtgui.QColor(220, 220, 220),
            )
            palette.setColor(qtgui.QPalette.ColorRole.Base, qtgui.QColor(30, 30, 30))
            palette.setColor(
                qtgui.QPalette.ColorRole.AlternateBase,
                qtgui.QColor(45, 45, 45),
            )
            palette.setColor(
                qtgui.QPalette.ColorRole.ToolTipBase,
                qtgui.QColor(220, 220, 220),
            )
            palette.setColor(
                qtgui.QPalette.ColorRole.ToolTipText,
                qtgui.QColor(220, 220, 220),
            )
            palette.setColor(qtgui.QPalette.ColorRole.Text, qtgui.QColor(220, 220, 220))
            palette.setColor(qtgui.QPalette.ColorRole.Button, qtgui.QColor(60, 60, 60))
            palette.setColor(
                qtgui.QPalette.ColorRole.ButtonText,
                qtgui.QColor(220, 220, 220),
            )
            palette.setColor(
                qtgui.QPalette.ColorRole.BrightText, qtgui.QColor(255, 50, 50)
            )
            palette.setColor(qtgui.QPalette.ColorRole.Link, qtgui.QColor(50, 150, 250))
            palette.setColor(
                qtgui.QPalette.ColorRole.Highlight, qtgui.QColor(50, 150, 250)
            )
            palette.setColor(
                qtgui.QPalette.ColorRole.HighlightedText, qtgui.QColor(0, 0, 0)
            )
            qt.QApplication.setPalette(palette)

            window.setStyleSheet(
                """
                QMainWindow { background-color: #2d2d2d; }
                QTabWidget::pane {
                    border: 1px solid #3d3d3d;
                    background-color: #2d2d2d;
                    border-radius: 4px;
                }
                QTabBar::tab {
                    background: #3c3c3c;
                    color: #aaa;
                    padding: 8px 16px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    margin-right: 2px;
                    font-weight: bold;
                }
                QTabBar::tab:selected {
                    background: #505050;
                    color: #fff;
                    border-bottom: 2px solid #3daee9;
                }
                QTabBar::tab:hover { background: #444; color: #ddd; }

                QGroupBox {
                    border: 1px solid #444;
                    margin-top: 1.2em;
                    font-weight: bold;
                    border-radius: 6px;
                    padding-top: 12px;
                    padding-bottom: 8px;
                    background-color: #333;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 5px;
                    color: #3daee9;
                    background-color: #2d2d2d;
                    border-radius: 2px;
                }

                QPushButton {
                    padding: 8px 16px;
                    border-radius: 4px;
                    background-color: #3c3c3c;
                    border: 1px solid #555;
                    min-width: 80px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #4a4a4a; border-color: #3daee9; }
                QPushButton:pressed {
                    background-color: #2a2a2a; border-color: #2a2a2a;
                }
                QPushButton:disabled {
                    background-color: #333;
                    color: #666;
                    border-color: #444;
                }

                QListWidget {
                    border: 1px solid #444;
                    border-radius: 4px;
                    background-color: #1e1e1e;
                    alternate-background-color: #252525;
                    padding: 4px;
                }
                QListWidget::item { padding: 4px; border-radius: 2px; }
                QListWidget::item:selected { background-color: #3daee9; color: #fff; }
                QListWidget::item:hover { background-color: #333; }

                QTextEdit {
                    border: 1px solid #444;
                    font-family: "Consolas", "Monaco", monospace;
                    background-color: #1e1e1e;
                    border-radius: 4px;
                    padding: 6px;
                    color: #ccc;
                }

                QProgressBar {
                    border: 1px solid #444;
                    border-radius: 4px;
                    text-align: center;
                    background-color: #1e1e1e;
                    color: #fff;
                    font-weight: bold;
                }
                QProgressBar::chunk {
                    background-color: #3daee9;
                    width: 10px;
                    border-radius: 2px;
                }

                QStatusBar {
                    background-color: #252525;
                    border-top: 1px solid #333;
                    color: #aaa;
                }
                QLabel { color: #ddd; }
                QSplitter::handle { background-color: #444; width: 2px; }

                QComboBox {
                    padding: 4px;
                    border-radius: 4px;
                    background-color: #3c3c3c;
                    border: 1px solid #555;
                    color: #eee;
                }
                QComboBox::drop-down { border: 0px; }
                QSpinBox {
                    padding: 4px;
                    border-radius: 4px;
                    background-color: #3c3c3c;
                    border: 1px solid #555;
                    color: #eee;
                }
                QCheckBox { spacing: 8px; color: #eee; }
                QCheckBox::indicator { width: 16px; height: 16px; }
            """
            )
        except Exception:
            # Fallback for older Qt versions where ColorRole might not be an enum
            try:
                qt.QApplication.setStyle(qt.QStyleFactory.create("Fusion"))
                palette = qtgui.QPalette()
                palette.setColor(qtgui.QPalette.Window, qtgui.QColor(45, 45, 45))
                palette.setColor(qtgui.QPalette.WindowText, qtgui.QColor(220, 220, 220))
                palette.setColor(qtgui.QPalette.Base, qtgui.QColor(30, 30, 30))
                palette.setColor(qtgui.QPalette.AlternateBase, qtgui.QColor(45, 45, 45))
                palette.setColor(
                    qtgui.QPalette.ToolTipBase, qtgui.QColor(220, 220, 220)
                )
                palette.setColor(
                    qtgui.QPalette.ToolTipText, qtgui.QColor(220, 220, 220)
                )
                palette.setColor(qtgui.QPalette.Text, qtgui.QColor(220, 220, 220))
                palette.setColor(qtgui.QPalette.Button, qtgui.QColor(60, 60, 60))
                palette.setColor(qtgui.QPalette.ButtonText, qtgui.QColor(220, 220, 220))
                palette.setColor(qtgui.QPalette.BrightText, qtgui.QColor(255, 50, 50))
                palette.setColor(qtgui.QPalette.Link, qtgui.QColor(50, 150, 250))
                palette.setColor(qtgui.QPalette.Highlight, qtgui.QColor(50, 150, 250))
                palette.setColor(qtgui.QPalette.HighlightedText, qtgui.QColor(0, 0, 0))
                qt.QApplication.setPalette(palette)
            except Exception:
                pass
