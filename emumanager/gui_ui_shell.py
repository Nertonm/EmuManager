from __future__ import annotations

import logging
from typing import Any


class MainWindowUIShellMixin:
    def setup_ui(self, main_window, qtwidgets: Any):
        qt = qtwidgets
        self._resolve_qt_namespaces()

        main_window.setObjectName("MainWindow")
        main_window.resize(900, 700)

        self.centralwidget = qt.QWidget(main_window)
        self.centralwidget.setObjectName("centralwidget")
        self.vertical_layout = qt.QVBoxLayout(self.centralwidget)
        self.vertical_layout.setObjectName("verticalLayout")

        self._setup_top_bar(qt)
        self._setup_tabs_container(qt)
        main_window.setCentralWidget(self.centralwidget)
        self._setup_dock_and_status(main_window, qt)

        self.retranslate_ui(main_window)
        self.tabs.setCurrentIndex(0)

    def retranslate_ui(self, main_window):
        main_window.setWindowTitle("EmuManager")

    def _setup_top_bar(self, qt):
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
        self.vertical_layout.addLayout(self.top_bar_layout)

    def _setup_tabs_container(self, qt):
        self.tabs = qt.QTabWidget(self.centralwidget)
        self.tabs.setObjectName("tabs")

        tabs_config = [
            (self.setup_dashboard_tab, "Dashboard", "SP_ComputerIcon"),
            (self.setup_library_tab, "Library", "SP_DirHomeIcon"),
            (self.setup_tools_tab, "Tools", "SP_FileDialogDetailedView"),
            (self.setup_verification_tab, "Verification", "SP_DialogApplyButton"),
            (self.setup_settings_tab, "Settings", "SP_FileDialogListView"),
            (self.setup_gallery_tab, "Gallery", "SP_FileIcon"),
            (self.setup_duplicates_tab, "Duplicates", "SP_FileDialogDetailedView"),
        ]

        for setup_fn, title, icon_key in tabs_config:
            tab_widget = qt.QWidget()
            tab_widget.setObjectName(f"tab_{title.lower()}")
            setup_fn(qt, tab_widget)

            icon = self._get_icon(qt, icon_key)
            if icon:
                self.tabs.addTab(tab_widget, icon, title)
            else:
                self.tabs.addTab(tab_widget, title)

            setattr(self, f"tab_{title.lower()}", tab_widget)

        self.vertical_layout.addWidget(self.tabs)

    def _setup_dock_and_status(self, main_window, qt):
        self.log = qt.QTextEdit()
        self.log.setReadOnly(True)
        self.log.setObjectName("log")
        self.log_dock = qt.QDockWidget("Log")
        self.log_dock.setObjectName("log_dock")
        self.log_dock.setWidget(self.log)

        self._attach_log_dock(main_window, qt)
        self._setup_dock_features(qt)

        self.statusbar = qt.QStatusBar(main_window)
        main_window.setStatusBar(self.statusbar)

        self.progress_bar = qt.QProgressBar(self.statusbar)
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.statusbar.addPermanentWidget(self.progress_bar)

        self.progress_label = qt.QLabel(self.statusbar)
        self.progress_label.setObjectName("progress_label")
        try:
            self.progress_label.setStyleSheet("color: #bbb; font-size: 11px;")
        except Exception as exc:
            logging.debug(f"Failed to style progress label: {exc}")
        self.progress_label.setVisible(False)
        self.statusbar.addPermanentWidget(self.progress_label)

    def _attach_log_dock(self, main_window, qt):
        try:
            if self._qt_enum is not None:
                try:
                    main_window.addDockWidget(
                        self._qt_enum.DockWidgetArea.BottomDockWidgetArea,
                        self.log_dock,
                    )
                except Exception:
                    main_window.addDockWidget(
                        self._qt_enum.BottomDockWidgetArea,
                        self.log_dock,
                    )
            else:
                main_window.addDockWidget(8, self.log_dock)
        except Exception as exc:
            logging.warning(f"Failed to attach log dock to area: {exc}")
            try:
                main_window.addDockWidget(self.log_dock)
            except Exception:
                pass

    def _setup_dock_features(self, qt):
        self.log_dock.setVisible(True)
        try:
            self.log_dock.setFeatures(
                qt.QDockWidget.DockWidgetFeature.DockWidgetMovable
                | qt.QDockWidget.DockWidgetFeature.DockWidgetFloatable
                | qt.QDockWidget.DockWidgetFeature.DockWidgetClosable
            )
        except AttributeError:
            try:
                self.log_dock.setFeatures(
                    qt.QDockWidget.Movable
                    | qt.QDockWidget.Floatable
                    | qt.QDockWidget.Closable
                )
            except AttributeError as exc:
                logging.debug(f"Dock features not supported: {exc}")
