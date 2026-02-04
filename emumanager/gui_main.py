"""MainWindow component for EmuManager GUI.

Redesenhado para usar nativamente o Core Orchestrator.
"""

from __future__ import annotations

import logging
import threading
import uuid
from pathlib import Path
import shutil
from types import SimpleNamespace
from typing import Any, Callable, Optional

from emumanager.controllers.duplicates import DuplicatesController
from emumanager.controllers.gallery import GalleryController
from emumanager.controllers.tools import ToolsController
from emumanager.library import LibraryDB
from emumanager.logging_cfg import get_logger, setup_gui_logging
from emumanager.verification.dat_downloader import DatDownloader
from emumanager.verification.hasher import calculate_hashes

from .gui_covers import CoverDownloader
from .gui_ui import MainWindowUI
from .gui_workers import (
    worker_hash_verify,
    worker_scan_library,
    worker_clean_junk,
    worker_identify_single_file,
    worker_identify_all
)


# Constants
MSG_NO_ROM = "No ROM selected"
MSG_NO_SYSTEM = "No system selected"
MSG_NSZ_MISSING = "Error: 'nsz' tool not found in environment."
MSG_SELECT_BASE = "Please select a base directory first (Open Library)."
LOG_WARN = "WARN: "
LOG_ERROR = "ERROR: "
LOG_EXCEPTION = "EXCEPTION: "
LAST_SYSTEM_KEY = "ui/last_system"


class MainWindowBase:
    """A minimal abstraction over a Qt MainWindow using the new Core Orchestrator."""

    def __init__(self, qtwidgets: Any, orchestrator: Any):
        self._qtwidgets = qtwidgets
        self._orchestrator = orchestrator
        self.ui = MainWindowUI()
        self._last_base = orchestrator.session.base_path
        self._current_dat_path = None
        self._dlg_select_base_title = "Select base directory"

        self._init_qt_modules()
        self._init_executor()
        self._init_state()
        
        self.window = self._qtwidgets.QMainWindow()
        self.ui.setup_ui(self.window, self._qtwidgets)
        self.window.closeEvent = self._on_close_event
        self._original_close_event = self.window.closeEvent

        self._alias_widgets()
        self._init_theme()
        self._init_logging_signaler()
        
        self.logger = get_logger("gui")
        self._init_controllers()
        self._connect_signals()
        self._init_settings()
        self._init_ui_enhancements()

    def _init_qt_modules(self):
        try:
            import importlib
            try:
                self._qtcore = importlib.import_module("PyQt6.QtCore")
                self._qtgui = importlib.import_module("PyQt6.QtGui")
            except Exception:
                self._qtcore = importlib.import_module("PySide6.QtCore")
                self._qtgui = importlib.import_module("PySide6.QtGui")
        except Exception as e:
            logging.error(f"Failed to load Qt modules: {e}")
            self._qtcore = None
            self._qtgui = None

    def _init_executor(self):
        try:
            import concurrent.futures
            self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        except Exception as e:
            logging.error(f"Failed to init executor: {e}")
            self._executor = None

    def _init_state(self):
        self._active_timer = None
        self._active_future = None
        self._scan_in_progress = False
        self._skip_list_side_effects = False
        self._cancel_event = threading.Event()
        self._settings = None
        self._env = {}
        self.library_db = LibraryDB()
        self._Qt_enum = getattr(self._qtcore, "Qt", None) if self._qtcore else None

    def _alias_widgets(self):
        self.log = self.ui.log
        self.status = self.ui.statusbar
        self.rom_list = self.ui.rom_list
        self.sys_list = self.ui.sys_list
        self.cover_label = self.ui.cover_label
        
        # Settings widgets
        self.chk_dry_run = self.ui.chk_dry_run
        self.spin_level = self.ui.spin_level
        self.combo_profile = self.ui.combo_profile
        self.chk_rm_originals = self.ui.chk_rm_originals
        self.chk_quarantine = self.ui.chk_quarantine
        self.chk_deep_verify = self.ui.chk_deep_verify
        self.chk_recursive = self.ui.chk_recursive
        self.chk_process_selected = self.ui.chk_process_selected
        self.chk_standardize_names = self.ui.chk_standardize_names

    def _init_theme(self):
        if self._qtgui:
            try:
                self.ui.apply_dark_theme(self._qtwidgets, self._qtgui, self.window)
            except Exception as e:
                logging.debug(f"Theme application failed: {e}")

    def _init_logging_signaler(self):
        if not self._qtcore:
            self._signaler = None
            return

        class LogSignaler(self._qtcore.QObject):
            if hasattr(self._qtcore, "pyqtSignal"):
                log_signal = self._qtcore.pyqtSignal(str)
                progress_signal = self._qtcore.pyqtSignal(float, str)
            else:
                log_signal = self._qtcore.Signal(str)
                progress_signal = self._qtcore.Signal(float, str)

            def emit_log(self, msg, level):
                self.log_signal.emit(msg)

        self._signaler = LogSignaler()
        self._signaler.log_signal.connect(self._log_msg_slot)
        self._signaler.progress_signal.connect(self._progress_slot)
        setup_gui_logging(self._signaler)

    def _init_controllers(self):
        self.gallery_controller = GalleryController(self)
        self.duplicates_controller = DuplicatesController(self)
        self.tools_controller = ToolsController(self)

    def _init_settings(self):
        if self._qtcore:
            try:
                self._settings = self._qtcore.QSettings("EmuManager", "Manager")
                self._load_settings()
            except Exception as e:
                logging.error(f"Settings init failed: {e}")

    def _init_ui_enhancements(self):
        try:
            self._setup_toolbar()
            self._setup_menubar()
            self._setup_rom_context_menu()
            self._setup_verification_context_menu()
        except Exception as e:
            logging.debug(f"UI enhancements failed: {e}")

        if self._qtcore:
            self._setup_startup_hook()
        self._setup_log_context_menu()
        self._setup_quarantine_signals()

    def _setup_quarantine_signals(self):
        try:
            if hasattr(self.ui, "btn_quar_open"):
                self.ui.btn_quar_open.clicked.connect(self._quarantine_open_location)
            if hasattr(self.ui, "btn_quar_restore"):
                self.ui.btn_quar_restore.clicked.connect(self._quarantine_restore)
            if hasattr(self.ui, "btn_quar_delete"):
                self.ui.btn_quar_delete.clicked.connect(self._quarantine_delete)
            if hasattr(self.ui, "quarantine_table"):
                self.ui.quarantine_table.itemSelectionChanged.connect(
                    self._on_quarantine_selection_changed
                )
        except Exception as e:
            logging.debug(f"Quarantine signals failed: {e}")

    def _setup_startup_hook(self):
        """
        Install an event filter to trigger logic only when the window is actually shown.
        """
        QObject = self._qtcore.QObject

        # Define filter class dynamically to use the imported QObject
        class StartupFilter(QObject):
            def __init__(self, callback):
                super().__init__()
                self.callback = callback
                self.has_run = False

            def eventFilter(self, obj, event):
                # Check for Show event (17)
                # Handle both PyQt6 (enum) and PySide6 (int/enum)
                t = event.type()
                val = t.value if hasattr(t, "value") else t

                if val == 17:  # QEvent.Show
                    if not self.has_run:
                        self.has_run = True
                        self.callback()
                return False

        self._startup_filter = StartupFilter(self._on_ui_shown)
        self.window.installEventFilter(self._startup_filter)

    def _on_ui_shown(self):
        """Called when the window receives the Show event."""
        # Defer slightly to ensure the window is fully painted and event loop is running
        self._qtcore.QTimer.singleShot(100, self._startup_logic)

    def _startup_logic(self):
        """Perform startup checks: load last library or prompt user."""
        if self._last_base and self._last_base.exists():
            self.log_msg(f"Library ready: {self._last_base}")
            # Avoid starting multiple overlapping scans as the UI auto-selects systems.
            self.on_list(force_scan=True)
        else:
            self.log_msg("Welcome! Please select a library.")
            self.on_open_library()

    def _connect_signals(self):
        self._connect_dashboard_signals()
        self._connect_library_signals()
        self._connect_verification_signals()
        self._connect_misc_signals()

    def _connect_dashboard_signals(self):
        if hasattr(self.ui, "btn_quick_organize"):
            self.ui.btn_quick_organize.clicked.connect(self.on_organize_all)
        if hasattr(self.ui, "btn_quick_verify"):
            self.ui.btn_quick_verify.clicked.connect(self.on_verify_all)
        if hasattr(self.ui, "btn_quick_update"):
            self.ui.btn_quick_update.clicked.connect(self.on_list)
        if hasattr(self.ui, "btn_quick_clean"):
            self.ui.btn_quick_clean.clicked.connect(self.tools_controller.on_clean_junk)

    def _connect_library_signals(self):
        self.ui.btn_open_lib.clicked.connect(self.on_open_library)
        self.ui.btn_init.clicked.connect(self.on_init)
        self.ui.btn_list.clicked.connect(self.on_list)
        self.ui.btn_add.clicked.connect(self.on_add)
        self.ui.btn_clear.clicked.connect(self.on_clear_log)
        
        self.ui.rom_list.currentItemChanged.connect(self._on_rom_selection_changed)
        self.ui.sys_list.itemClicked.connect(self._on_system_selected)
        self.ui.rom_list.itemDoubleClicked.connect(self._on_rom_double_clicked)
        
        if hasattr(self.ui, "edit_filter"):
            self.ui.edit_filter.textChanged.connect(self._on_filter_text)
        if hasattr(self.ui, "btn_clear_filter"):
            self.ui.btn_clear_filter.clicked.connect(lambda: self.ui.edit_filter.setText(""))

    def _connect_verification_signals(self):
        self.ui.btn_select_dat.clicked.connect(self.on_select_dat)
        self.ui.btn_verify_dat.clicked.connect(self.on_verify_dat)
        
        if hasattr(self.ui, "btn_update_dats"):
            self.ui.btn_update_dats.clicked.connect(self.on_update_dats)
        
        if hasattr(self.ui, "combo_verif_filter"):
            self.ui.combo_verif_filter.currentTextChanged.connect(self.on_verification_filter_changed)
        
        if hasattr(self.ui, "btn_export_csv"):
            self.ui.btn_export_csv.clicked.connect(self.on_export_verification_csv)
            
        if hasattr(self.ui, "btn_try_rehash"):
            self.ui.btn_try_rehash.clicked.connect(self.on_try_rehash)
            
        if hasattr(self.ui, "table_results"):
            self.ui.table_results.itemDoubleClicked.connect(self._on_verification_item_dblclick)
            
        if hasattr(self.ui, "btn_identify_all"):
            self.ui.btn_identify_all.clicked.connect(self.on_identify_all)

    def _connect_misc_signals(self):
        self.ui.btn_cancel.clicked.connect(self.on_cancel_requested)
        try:
            self._install_rom_key_filter()
        except Exception as e:
            logging.debug(f"ROM key filter installation failed: {e}")

    def show(self):
        self.window.show()

    def _log_msg_slot(self, text: str):
        # Just append to the log window.
        # The text is already formatted by the logging handler if it came from there.
        self.log.append(text)

        # Auto-scroll to bottom
        try:
            sb = self.log.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())
        except Exception:
            pass

        # Show brief status in the status bar
        try:
            # Truncate if too long for status bar
            status_text = text.strip()
            if len(status_text) > 100:
                status_text = status_text[:97] + "..."
            self.status.showMessage(status_text, 5000)
        except Exception:
            pass

    def _progress_slot(self, percent: float, message: str):
        try:
            # clamp percent
            p = 0.0 if percent is None else float(percent)
            if p < 0.0:
                p = 0.0
            if p > 1.0:
                p = 1.0

            # Update progress bar and label
            try:
                # Show progress bar if hidden
                if not self.ui.progress_bar.isVisible():
                    self.ui.progress_bar.setVisible(True)

                    # If percent is None treat as indeterminate/busy; negative
                    # values are clamped to 0 for determinate reporting.
                    if percent is None:
                        try:
                            self.ui.progress_bar.setRange(0, 0)
                        except Exception:
                            pass
                    else:
                        try:
                            # clamp negative/over values into [0,1]
                            if p < 0.0:
                                p = 0.0
                            if p > 1.0:
                                p = 1.0
                            self.ui.progress_bar.setRange(0, 100)
                            self.ui.progress_bar.setValue(int(p * 100))
                        except Exception:
                            pass

                # Update small label with message (if any)
                try:
                    if message:
                        self.ui.progress_label.setText(message)
                        self.ui.progress_label.setVisible(True)
                    else:
                        self.ui.progress_label.setVisible(False)
                except Exception:
                    pass
            except Exception:
                pass

            if message:
                self.status.showMessage(message)
        except Exception:
            pass

    def log_msg(self, text: str):
        """Thread-safe logging method.

        Now redirects to standard logging.
        """
        logging.info(text)

    def on_clear_log(self):
        try:
            self.log.clear()
        except Exception:
            # ignore GUI errors
            pass

    def _ensure_common_actions(self):
        """Create common QAction objects once and store as instance attributes."""
        qt = self._qtwidgets
        if hasattr(self, "act_open_library"):
            return
        # grouped creators to reduce complexity
        self._create_file_actions(qt)
        self._create_view_actions(qt)
        self._create_tools_actions(qt)
        self._create_misc_actions(qt)

    def _create_file_actions(self, qt):
        self.act_open_library = qt.QAction("Open Library", self.window)
        self.act_open_library.setShortcut("Ctrl+O")
        self.act_open_library.triggered.connect(self.on_open_library)

        self.act_refresh_list = qt.QAction("Refresh List", self.window)
        self.act_refresh_list.setShortcut("F5")
        self.act_refresh_list.triggered.connect(self.on_list)

        self.act_init_structure = qt.QAction("Init Structure", self.window)
        self.act_init_structure.setShortcut("Ctrl+I")
        self.act_init_structure.triggered.connect(self.on_init)

        self.act_add_rom = qt.QAction("Add ROM", self.window)
        self.act_add_rom.setShortcut("Ctrl+A")
        self.act_add_rom.triggered.connect(self.on_add)

        self.act_verify_dat = qt.QAction("Verify DAT", self.window)
        self.act_verify_dat.setShortcut("Ctrl+Shift+V")
        self.act_verify_dat.triggered.connect(self.on_verify_dat)

        self.act_cancel = qt.QAction("Cancel", self.window)
        self.act_cancel.setShortcut("Esc")
        self.act_cancel.triggered.connect(self.on_cancel_requested)

        self.act_exit = qt.QAction("Exit", self.window)
        self.act_exit.setShortcut("Ctrl+Q")

        def _exit():
            try:
                self.window.close()
            except Exception:
                pass

        self.act_exit.triggered.connect(_exit)

    def _create_view_actions(self, qt):
        self.act_toggle_log = qt.QAction("Toggle Log", self.window)
        self.act_toggle_log.setShortcut("Ctrl+L")

        def _toggle_log():
            try:
                vis = self.ui.log_dock.isVisible()
                self.ui.log_dock.setVisible(not vis)
            except Exception:
                pass

        self.act_toggle_log.triggered.connect(_toggle_log)

        self.act_toggle_toolbar = qt.QAction("Show Toolbar", self.window)
        try:
            self.act_toggle_toolbar.setCheckable(True)
        except Exception:
            pass

        def _toggle_tb(checked=None):
            try:
                tb = getattr(self, "_toolbar", None)
                if tb:
                    if checked is None:
                        vis = tb.isVisible()
                        tb.setVisible(not vis)
                    else:
                        tb.setVisible(bool(checked))
            except Exception:
                pass

        self.act_toggle_toolbar.triggered.connect(_toggle_tb)

        self.act_focus_filter = qt.QAction("Focus ROM Filter", self.window)
        self.act_focus_filter.setShortcut("Ctrl+F")

        def _focus_filter():
            try:
                if hasattr(self.ui, "edit_filter"):
                    self.ui.edit_filter.setFocus()
            except Exception:
                pass

        self.act_focus_filter.triggered.connect(_focus_filter)

        # Reset layout
        self.act_reset_layout = qt.QAction("Reset Layout", self.window)
        self.act_reset_layout.triggered.connect(self._reset_layout)

    def _create_tools_actions(self, qt):
        self.act_organize = qt.QAction("Organize Library", self.window)
        self.act_organize.triggered.connect(self.tools_controller.on_organize)

        self.act_health = qt.QAction("Health Check", self.window)
        self.act_health.triggered.connect(self.tools_controller.on_health_check)

        self.act_switch_compress = qt.QAction("Switch: Compress", self.window)
        self.act_switch_compress.triggered.connect(
            self.tools_controller.on_switch_compress
        )

        self.act_switch_decompress = qt.QAction("Switch: Decompress", self.window)
        self.act_switch_decompress.triggered.connect(
            self.tools_controller.on_switch_decompress
        )

        self.act_ps2_convert = qt.QAction("PS2: Convert to CHD", self.window)
        self.act_ps2_convert.triggered.connect(self.tools_controller.on_ps2_convert)

        self.act_psx_convert = qt.QAction("PS1: Convert to CHD", self.window)
        self.act_psx_convert.triggered.connect(self.tools_controller.on_psx_convert)

        self.act_ps2_verify = qt.QAction("PS2: Verify", self.window)
        self.act_ps2_verify.triggered.connect(self.tools_controller.on_ps2_verify)

        self.act_psx_verify = qt.QAction("PS1: Verify", self.window)
        self.act_psx_verify.triggered.connect(self.tools_controller.on_psx_verify)

        self.act_ps2_organize = qt.QAction("PS2: Organize", self.window)
        self.act_ps2_organize.triggered.connect(self.tools_controller.on_ps2_organize)

        self.act_psx_organize = qt.QAction("PS1: Organize", self.window)
        self.act_psx_organize.triggered.connect(self.tools_controller.on_psx_organize)

        self.act_ps3_verify = qt.QAction("PS3: Verify", self.window)
        self.act_ps3_verify.triggered.connect(self.tools_controller.on_ps3_verify)

        self.act_ps3_organize = qt.QAction("PS3: Organize", self.window)
        self.act_ps3_organize.triggered.connect(self.tools_controller.on_ps3_organize)

        self.act_psp_verify = qt.QAction("PSP: Verify", self.window)
        self.act_psp_verify.triggered.connect(self.tools_controller.on_psp_verify)

        self.act_psp_organize = qt.QAction("PSP: Organize", self.window)
        self.act_psp_organize.triggered.connect(self.tools_controller.on_psp_organize)

        self.act_psp_compress = qt.QAction("PSP: Compress ISO->CSO", self.window)
        self.act_psp_compress.triggered.connect(self.tools_controller.on_psp_compress)

        self.act_n3ds_verify = qt.QAction("3DS: Verify", self.window)
        self.act_n3ds_verify.triggered.connect(self.tools_controller.on_n3ds_verify)

        self.act_n3ds_organize = qt.QAction("3DS: Organize", self.window)
        self.act_n3ds_organize.triggered.connect(self.tools_controller.on_n3ds_organize)

        self.act_dol_convert = qt.QAction("GC/Wii: Convert to RVZ", self.window)
        self.act_dol_convert.triggered.connect(self.tools_controller.on_dolphin_convert)

        self.act_dol_verify = qt.QAction("GC/Wii: Verify", self.window)
        self.act_dol_verify.triggered.connect(self.tools_controller.on_dolphin_verify)

        self.act_dol_organize = qt.QAction("GC/Wii: Organize", self.window)
        self.act_dol_organize.triggered.connect(
            self.tools_controller.on_dolphin_organize
        )

        self.act_clean_junk = qt.QAction("Clean Junk Files", self.window)
        self.act_clean_junk.triggered.connect(self.tools_controller.on_clean_junk)

        self.act_export_csv = qt.QAction("Export Verification CSV", self.window)
        self.act_export_csv.triggered.connect(self.on_export_verification_csv)

        # Show Library Actions (audit trail)
        self.act_show_actions = qt.QAction("Show Library Actions", self.window)
        # Show Quarantine viewer
        self.act_show_quarantine = qt.QAction("Show Quarantine", self.window)
        # Connect to ToolsController handler if available
        try:
            if hasattr(self, "tools_controller") and hasattr(
                self.tools_controller, "on_show_actions"
            ):
                self.act_show_actions.triggered.connect(
                    self.tools_controller.on_show_actions
                )
            if hasattr(self, "tools_controller") and hasattr(
                self.tools_controller, "on_show_quarantine"
            ):
                self.act_show_quarantine.triggered.connect(
                    self.tools_controller.on_show_quarantine
                )
        except Exception:
            pass

    def _create_misc_actions(self, qt):
        self.act_open_folder = qt.QAction("Open Selected ROM Folder", self.window)
        self.act_open_folder.triggered.connect(self._open_selected_rom_folder)

        self.act_copy_path = qt.QAction("Copy Selected ROM Path", self.window)
        self.act_copy_path.triggered.connect(self._copy_selected_rom_path)

    def _setup_toolbar(self):
        """Create a toolbar with common actions and shortcuts.

        Actions are created once and reused by both toolbar and menubar.
        """
        qt = self._qtwidgets
        try:
            # Ensure actions exist
            self._ensure_common_actions()
            tb = qt.QToolBar("Main")
            self.window.addToolBar(tb)
            self._toolbar = tb
            # Actions
            tb.addAction(self.act_open_library)
            tb.addAction(self.act_refresh_list)
            tb.addAction(self.act_init_structure)
            tb.addAction(self.act_add_rom)
            tb.addAction(self.act_verify_dat)
            tb.addAction(self.act_cancel)
            tb.addSeparator()
            tb.addAction(self.act_toggle_log)
            tb.addAction(self.act_focus_filter)
        except Exception:
            pass

    def _setup_menubar(self):
        """Create the top menubar with File, Tools, and View menus."""
        qt = self._qtwidgets
        try:
            self._ensure_common_actions()
            mb = qt.QMenuBar(self.window)
            self.window.setMenuBar(mb)

            # File menu
            m_file = mb.addMenu("File")
            m_file.addAction(self.act_open_library)
            m_file.addAction(self.act_refresh_list)
            m_file.addAction(self.act_add_rom)
            m_file.addSeparator()
            m_file.addAction(self.act_exit)

            # Tools menu
            m_tools = mb.addMenu("Tools")
            m_tools.addAction(self.act_init_structure)
            m_tools.addSeparator()
            m_tools.addAction(self.act_organize)
            m_tools.addAction(self.act_health)
            m_tools.addSeparator()
            m_tools.addAction(self.act_switch_compress)
            m_tools.addAction(self.act_switch_decompress)
            m_tools.addSeparator()
            m_tools.addAction(self.act_psx_convert)
            m_tools.addAction(self.act_psx_verify)
            m_tools.addAction(self.act_psx_organize)
            m_tools.addSeparator()
            m_tools.addAction(self.act_ps2_convert)
            m_tools.addAction(self.act_ps2_verify)
            m_tools.addAction(self.act_ps2_organize)
            m_tools.addSeparator()
            m_tools.addAction(self.act_ps3_verify)
            m_tools.addAction(self.act_ps3_organize)
            m_tools.addSeparator()
            m_tools.addAction(self.act_psp_verify)
            m_tools.addAction(self.act_psp_organize)
            m_tools.addAction(self.act_psp_compress)
            m_tools.addSeparator()
            m_tools.addAction(self.act_n3ds_verify)
            m_tools.addAction(self.act_n3ds_organize)
            m_tools.addSeparator()
            m_tools.addAction(self.act_dol_convert)
            m_tools.addAction(self.act_dol_verify)
            m_tools.addAction(self.act_dol_organize)
            m_tools.addSeparator()
            m_tools.addAction(self.act_clean_junk)
            m_tools.addSeparator()
            m_tools.addAction(self.act_verify_dat)
            m_tools.addAction(self.act_export_csv)

            # View menu
            m_view = mb.addMenu("View")
            m_view.addAction(self.act_toggle_log)
            m_view.addAction(self.act_toggle_toolbar)
            m_view.addSeparator()
            m_view.addAction(self.act_focus_filter)
            m_view.addSeparator()
            m_view.addAction(self.act_reset_layout)
            # Add diagnostic dialogs
            try:
                m_view.addSeparator()
                m_view.addAction(self.act_show_actions)
                m_view.addAction(self.act_show_quarantine)
            except Exception:
                pass
        except Exception:
            pass

    def _setup_rom_context_menu(self):
        """Add a context menu to the ROM list for quick actions."""
        qt = self._qtwidgets
        core = self._qtcore
        try:
            # Use QtCore.Qt for constants
            Qt = core.Qt
            policy = (
                Qt.ContextMenuPolicy.CustomContextMenu
                if hasattr(Qt, "ContextMenuPolicy")
                else Qt.CustomContextMenu
            )
            self.ui.rom_list.setContextMenuPolicy(policy)

            def _show_menu(pos):
                try:
                    menu = qt.QMenu(self.ui.rom_list)

                    # Actions requested: Delete, Compress, Verify, Decompress
                    a_del = menu.addAction("Delete")
                    menu.addSeparator()
                    a_comp = menu.addAction("Compress")
                    a_recomp = menu.addAction("Recompress")
                    a_decomp = menu.addAction("Decompress")
                    a_rename = menu.addAction("Rename to Standard")
                    menu.addSeparator()
                    a_verify = menu.addAction("Verify (Calc Hash)")
                    a_identify = menu.addAction("Identify with DAT...")
                    menu.addSeparator()
                    a_open = menu.addAction("Open Folder")
                    a_copy = menu.addAction("Copy Path")

                    # Use exec_ if available (PyQt5/PySide2), else exec (PyQt6/PySide6)
                    exec_func = menu.exec if hasattr(menu, "exec") else menu.exec_

                    act = exec_func(self.ui.rom_list.mapToGlobal(pos))

                    if act == a_del:
                        self.on_delete_selected()
                    elif act == a_comp:
                        self.tools_controller.on_compress_selected()
                    elif act == a_recomp:
                        self.tools_controller.on_recompress_selected()
                    elif act == a_decomp:
                        self.tools_controller.on_decompress_selected()
                    elif act == a_verify:
                        self.on_verify_selected()
                    elif act == a_identify:
                        self.on_identify_selected()
                    elif act == a_rename:
                        self.on_rename_to_standard_selected()
                    elif act == a_open:
                        self._open_selected_rom_folder()
                    elif act == a_copy:
                        self._copy_selected_rom_path()
                except Exception as e:
                    self.log_msg(f"Error showing context menu: {e}")

            self.ui.rom_list.customContextMenuRequested.connect(_show_menu)
            self.log_msg("Context menu setup complete")
        except Exception as e:
            self.log_msg(f"Failed to setup context menu: {e}")

    def _setup_verification_context_menu(self):
        """Context menu for verification results to copy hashes or open location."""
        qt = self._qtwidgets
        core = self._qtcore
        try:
            if not hasattr(self.ui, "table_results"):
                return

            Qt = core.Qt
            policy = (
                Qt.ContextMenuPolicy.CustomContextMenu
                if hasattr(Qt, "ContextMenuPolicy")
                else Qt.CustomContextMenu
            )
            self.ui.table_results.setContextMenuPolicy(policy)

            def _show_menu(pos):
                menu, actions = self._build_verification_menu(qt)
                exec_func = menu.exec if hasattr(menu, "exec") else menu.exec_
                act = exec_func(self.ui.table_results.mapToGlobal(pos))
                row = self.ui.table_results.currentRow()
                results = getattr(self, "_last_verify_results", [])
                if 0 <= row < len(results):
                    self._handle_verification_action(qt, act, actions, results[row])

            self.ui.table_results.customContextMenuRequested.connect(_show_menu)
        except Exception:
            pass

    def _build_verification_menu(self, qt):
        menu = qt.QMenu(self.ui.table_results)
        a_open = menu.addAction("Open Location")
        menu.addSeparator()
        a_crc = menu.addAction("Copy CRC32")
        a_sha1 = menu.addAction("Copy SHA1")
        a_md5 = menu.addAction("Copy MD5")
        a_sha256 = menu.addAction("Copy SHA256")
        actions = {
            "open": a_open,
            "crc": a_crc,
            "sha1": a_sha1,
            "md5": a_md5,
            "sha256": a_sha256,
        }
        return menu, actions

    def _handle_verification_action(self, qt, act, actions, res):
        try:
            if act == actions["open"]:
                fp = getattr(res, "full_path", None)
                if fp:
                    self._open_file_location(Path(fp))
            elif act == actions["crc"]:
                qt.QApplication.clipboard().setText(res.crc or "")
                self.status.showMessage("CRC32 copied", 2000)
            elif act == actions["sha1"]:
                qt.QApplication.clipboard().setText(res.sha1 or "")
                self.status.showMessage("SHA1 copied", 2000)
            elif act == actions["md5"]:
                qt.QApplication.clipboard().setText(getattr(res, "md5", "") or "")
                self.status.showMessage("MD5 copied", 2000)
            elif act == actions["sha256"]:
                qt.QApplication.clipboard().setText(getattr(res, "sha256", "") or "")
                self.status.showMessage("SHA256 copied", 2000)
        except Exception:
            pass

    def _open_selected_rom_folder(self):
        try:
            sel = self.ui.rom_list.currentItem()
            sys_item = self.ui.sys_list.currentItem()
            if not sel or not sys_item:
                return
            p = Path(self._last_base) / "roms" / sys_item.text() / sel.text()
            self._open_file_location(p)
        except Exception:
            pass

    def _copy_selected_rom_path(self):
        try:
            qt = self._qtwidgets
            sel = self.ui.rom_list.currentItem()
            sys_item = self.ui.sys_list.currentItem()
            if not sel or not sys_item:
                return
            p = Path(self._last_base) / "roms" / sys_item.text() / sel.text()
            cb = qt.QApplication.clipboard()
            cb.setText(str(p))
            self.status.showMessage("Path copied to clipboard", 3000)
        except Exception:
            pass

    def _open_file_location(self, path: Path):
        if not path.exists():
            self.log_msg(f"Error: Path does not exist: {path}")
            msg = (
                "The file or folder does not exist:\n"
                f"{path}\n\n"
                "Please try rescanning the library."
            )
            self._qtwidgets.QMessageBox.warning(self.window, "Path Not Found", msg)
            return

        try:
            import subprocess

            if path.is_dir():
                subprocess.run(["xdg-open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path.parent)], check=False)
        except Exception as e:
            self.log_msg(f"Failed to open location: {path} ({e})")

    # Background/task helpers
    def _run_in_background(
        self,
        func: Callable[[], object],
        done_cb: Optional[Callable[[object], None]] = None,
    ):
        """Run func() in a thread and call done_cb(result) in the GUI thread."""
        self._cancel_event.clear()
        future = self._submit_task(func)
        self._active_future = future

        if self._qtcore:
            self._start_polling_timer(future, done_cb)

        self._enable_cancel_button()
        return future

    def _make_op_log_cb(self, op_id: str):
        """Return a log callback that prefixes messages with operation id."""

        def _log(msg: str):
            try:
                self.log_msg(f"[op={op_id}] {msg}")
            except Exception:
                try:
                    # Fallback to direct logging
                    logging.info("[op=%s] %s", op_id, msg)
                except Exception:
                    pass

        return _log

    def _submit_task(self, func: Callable[[], object]):
        if self._executor:
            return self._executor.submit(func)

        # Synchronous fallback
        class _F:
            def __init__(self, res):
                self._res = res

            def done(self):
                return True

            def result(self):
                return self._res

        try:
            res = func()
        except Exception as e:
            res = e
        return _F(res)

    def _start_polling_timer(self, future, done_cb):
        timer = self._qtcore.QTimer(self.window)
        timer.setInterval(200)

        def _check():
            if not future.done():
                return
            timer.stop()
            try:
                result = future.result()
            except Exception as e:
                result = e

            if done_cb:
                try:
                    done_cb(result)
                except Exception as e:
                    self.log_msg(f"Background callback error: {e}")
                    if hasattr(self, "logger"):
                        self.logger.exception("Background callback error")

        timer.timeout.connect(_check)
        timer.start()
        self._active_timer = timer

    def _enable_cancel_button(self):
        try:
            if hasattr(self.ui, "btn_cancel") and self.ui.btn_cancel:
                self.ui.btn_cancel.setEnabled(True)
        except Exception:
            pass

    def _load_settings(self):
        if not self._settings:
            return
        try:
            self._restore_window_settings()
            self._restore_ui_settings()
        except Exception:
            pass

    def _save_settings(self):
        if not self._settings:
            return
        try:
            self._persist_window_settings()
            self._persist_ui_settings()
        except Exception:
            pass

    def _restore_window_settings(self):
        """Restore geometry/state and base dir from QSettings."""
        try:
            # Geometry/state
            try:
                geom = self._settings.value("ui/window_geometry")
                if geom:
                    self.window.restoreGeometry(geom)
            except Exception:
                # legacy width/height
                w = self._settings.value("window/width")
                h = self._settings.value("window/height")
                if w and h:
                    try:
                        self.window.resize(int(w), int(h))
                    except Exception:
                        pass
            try:
                st = self._settings.value("ui/window_state")
                if st:
                    self.window.restoreState(st)
            except Exception:
                pass
            # Last base
            last = self._settings.value("last_base")
            if last:
                path = Path(str(last))
                if path.exists():
                    self._last_base = path
                    try:
                        self.ui.lbl_library.setText(str(self._last_base))
                        self.ui.lbl_library.setStyleSheet(
                            "font-weight: bold; color: #3daee9;"
                        )
                        # Enable UI since we have a library
                        self._set_ui_enabled(True)
                        self.log_msg(f"Restored last library: {self._last_base}")

                        # Update logger to write to the new library's log folder
                        self._update_logger(self._last_base)
                    except Exception:
                        pass
                else:
                    self.log_msg(f"Last library path not found: {path}")
        except Exception:
            pass

    def _update_logger(self, base_dir: Path):
        """Configure file-based logging under the selected library directory.

        Adds a file handler so logs are persisted to <base_dir>/_INSTALL_LOG.txt
        and a rotating file logger for fileops under <base_dir>/logs/fileops.log.
        """
        try:
            from emumanager.logging_cfg import get_logger, get_fileops_logger

            # Ensure the main emumanager logger writes to the selected base
            get_logger("emumanager", base_dir=base_dir)
            # Add/ensure fileops logger writes to a rotating file under base/logs
            get_fileops_logger(base_dir=base_dir)
        except Exception as e:
            try:
                self.log_msg(f"Failed to update logger: {e}")
            except Exception:
                pass

    def _restore_ui_settings(self):
        """Restore checkboxes, toolbar visibility, filters, splitter, and widths."""
        try:
            self._restore_checkboxes()
            self._restore_extras()
            self._restore_splitter()
            self._restore_toolbar_visibility()
            self._restore_table_widths()
            self._restore_last_system()
        except Exception:
            pass

    def _restore_checkboxes(self):
        try:
            self.chk_dry_run.setChecked(
                str(self._settings.value("settings/dry_run", "false")).lower() == "true"
            )
            self.spin_level.setValue(int(self._settings.value("settings/level", 3)))
            self.combo_profile.setCurrentText(
                str(self._settings.value("settings/profile", "None"))
            )
            self.chk_rm_originals.setChecked(
                str(self._settings.value("settings/rm_originals", "false")).lower()
                == "true"
            )
            self.chk_quarantine.setChecked(
                str(self._settings.value("settings/quarantine", "false")).lower()
                == "true"
            )
            self.chk_deep_verify.setChecked(
                str(self._settings.value("settings/deep_verify", "false")).lower()
                == "true"
            )
            self.chk_recursive.setChecked(
                str(self._settings.value("settings/recursive", "true")).lower()
                == "true"
            )
            self.chk_process_selected.setChecked(
                str(self._settings.value("settings/process_selected", "false")).lower()
                == "true"
            )
            self.chk_standardize_names.setChecked(
                str(self._settings.value("settings/standardize_names", "false")).lower()
                == "true"
            )
        except Exception:
            pass

    def _restore_extras(self):
        try:
            vis = str(self._settings.value("ui/log_visible", "true")).lower() == "true"
            self.ui.log_dock.setVisible(vis)
        except Exception:
            pass
        try:
            if hasattr(self.ui, "edit_filter"):
                self.ui.edit_filter.setText(
                    str(self._settings.value("ui/rom_filter", ""))
                )
            if hasattr(self.ui, "combo_verif_filter"):
                idx = int(self._settings.value("ui/verif_filter_idx", 0))
                self.ui.combo_verif_filter.setCurrentIndex(idx)
        except Exception:
            pass

    def _restore_splitter(self):
        try:
            st = self._settings.value("ui/splitter_state")
            if st:
                self.ui.splitter.restoreState(st)
        except Exception:
            pass

    def _restore_toolbar_visibility(self):
        try:
            tb_vis = (
                str(self._settings.value("ui/toolbar_visible", "true")).lower()
                == "true"
            )
            if hasattr(self, "_toolbar") and self._toolbar:
                self._toolbar.setVisible(tb_vis)
            if hasattr(self, "act_toggle_toolbar"):
                self.act_toggle_toolbar.setChecked(tb_vis)
        except Exception:
            pass

    def _restore_table_widths(self):
        try:
            widths = self._settings.value("ui/verif_table_widths")
            if widths and hasattr(self.ui, "table_results"):
                if isinstance(widths, (list, tuple)):
                    for i, w in enumerate(widths):
                        try:
                            self.ui.table_results.setColumnWidth(i, int(w))
                        except Exception:
                            pass
        except Exception:
            pass

    def _restore_last_system(self):
        try:
            self._last_system = (
                str(self._settings.value(LAST_SYSTEM_KEY))
                if self._settings.value(LAST_SYSTEM_KEY)
                else None
            )
        except Exception:
            self._last_system = None

    def _persist_window_settings(self):
        """Persist geometry/state and base dir to QSettings."""
        try:
            # Geometry/state
            try:
                self._settings.setValue(
                    "ui/window_geometry", self.window.saveGeometry()
                )
                self._settings.setValue("ui/window_state", self.window.saveState())
            except Exception:
                # legacy
                self._settings.setValue("window/width", self.window.width())
                self._settings.setValue("window/height", self.window.height())
            if self._last_base:
                self._settings.setValue("last_base", str(self._last_base))
        except Exception:
            pass

    def _persist_ui_settings(self):
        """Persist checkboxes, filters, splitter, toolbar visibility, and widths."""
        try:
            self._persist_checkbox_settings()
            self._persist_extras()
            self._persist_splitter()
            self._persist_table_widths()
        except Exception:
            pass

    def _persist_checkbox_settings(self):
        try:
            self._settings.setValue(
                "settings/dry_run", str(self.chk_dry_run.isChecked())
            )
            self._settings.setValue("settings/level", self.spin_level.value())
            self._settings.setValue(
                "settings/profile", self.combo_profile.currentText()
            )
            self._settings.setValue(
                "settings/rm_originals", str(self.chk_rm_originals.isChecked())
            )
            self._settings.setValue(
                "settings/quarantine", str(self.chk_quarantine.isChecked())
            )
            self._settings.setValue(
                "settings/deep_verify", str(self.chk_deep_verify.isChecked())
            )
            self._settings.setValue(
                "settings/recursive", str(self.chk_recursive.isChecked())
            )
            self._settings.setValue(
                "settings/process_selected",
                str(self.chk_process_selected.isChecked()),
            )
            self._settings.setValue(
                "settings/standardize_names",
                str(self.chk_standardize_names.isChecked()),
            )
        except Exception:
            pass

    def _persist_extras(self):
        try:
            self._settings.setValue("ui/log_visible", str(self.ui.log_dock.isVisible()))
            if hasattr(self.ui, "edit_filter"):
                self._settings.setValue("ui/rom_filter", self.ui.edit_filter.text())
            if hasattr(self.ui, "combo_verif_filter"):
                self._settings.setValue(
                    "ui/verif_filter_idx",
                    self.ui.combo_verif_filter.currentIndex(),
                )
        except Exception:
            pass

    def _persist_splitter(self):
        try:
            self._settings.setValue("ui/splitter_state", self.ui.splitter.saveState())
        except Exception:
            pass

    def _persist_table_widths(self):
        try:
            if hasattr(self.ui, "table_results"):
                widths = [
                    self.ui.table_results.columnWidth(i)
                    for i in range(self.ui.table_results.columnCount())
                ]
                self._settings.setValue("ui/verif_table_widths", widths)
        except Exception:
            pass

    def _on_close_event(self, event):
        self.log_msg("Shutting down...")
        self._cancel_event.set()
        # Persist settings before closing
        try:
            self._save_settings()
        except Exception:
            pass
        if self._executor:
            self._executor.shutdown(wait=False)
        if self._original_close_event:
            self._original_close_event(event)
        else:
            event.accept()

    def _set_ui_enabled(self, enabled: bool):
        try:
            self.ui.btn_init.setEnabled(enabled)
            self.ui.btn_list.setEnabled(enabled)
            self.ui.btn_add.setEnabled(enabled)
            self.ui.btn_clear.setEnabled(enabled)
            self.ui.btn_open_lib.setEnabled(enabled)

            # Also disable/enable tool buttons
            self.ui.btn_organize.setEnabled(enabled)
            self.ui.btn_health.setEnabled(enabled)
            self.ui.btn_switch_compress.setEnabled(enabled)
            self.ui.btn_switch_decompress.setEnabled(enabled)
            self.ui.btn_ps2_convert.setEnabled(enabled)
            self.ui.btn_ps2_verify.setEnabled(enabled)
            self.ui.btn_ps2_organize.setEnabled(enabled)
            self.ui.btn_ps3_verify.setEnabled(enabled)
            self.ui.btn_ps3_organize.setEnabled(enabled)
            self.ui.btn_psp_verify.setEnabled(enabled)
            self.ui.btn_psp_organize.setEnabled(enabled)
            self.ui.btn_dolphin_convert.setEnabled(enabled)
            self.ui.btn_dolphin_verify.setEnabled(enabled)
            self.ui.btn_clean_junk.setEnabled(enabled)

            # Verification Tab
            self.ui.btn_select_dat.setEnabled(enabled)

            # Verify DAT button logic
            # It should be enabled if we have a DAT selected OR a library open
            # (for auto-discovery)
            has_dat = bool(getattr(self, "_current_dat_path", None))
            has_base = bool(getattr(self, "_last_base", None))
            can_verify = enabled and (has_dat or has_base)

            # print(f"DEBUG: enabled={enabled} has_dat={has_dat} ...")
            self.ui.btn_verify_dat.setEnabled(can_verify)

            # Identify All button logic
            if hasattr(self.ui, "btn_identify_all"):
                self.ui.btn_identify_all.setEnabled(enabled and bool(self._last_base))

            # Compression buttons
            self.ui.btn_compress.setEnabled(enabled)
            self.ui.btn_recompress.setEnabled(enabled)
            self.ui.btn_decompress.setEnabled(enabled)

            # Cancel button logic is inverse
            self.ui.btn_cancel.setEnabled(not enabled)

            # Show/Hide progress bar and associated label
            try:
                self.ui.progress_bar.setVisible(not enabled)
            except Exception:
                pass
            try:
                # Hide progress label when UI is enabled
                self.ui.progress_label.setVisible(False)
            except Exception:
                pass
            if enabled:
                try:
                    # Reset determinate bar
                    self.ui.progress_bar.setRange(0, 100)
                    self.ui.progress_bar.setValue(0)
                except Exception:
                    pass
                try:
                    self.status.clearMessage()
                except Exception:
                    pass
        except Exception:
            pass

    def progress_hook(self, percent: float, message: str):
        """Simple progress hook for compression helpers.

        percent: 0.0 to 1.0

        Updates the status bar and appends a short log message. Safe to be set
        as `args.progress_callback` in `switch_organizer`.
        """
        if self._signaler:
            self._signaler.progress_signal.emit(percent, message)
        else:
            self._progress_slot(percent, message)

    # The following methods interact with manager; keep them small and testable
    def on_init(self):
        self.log_msg(f"Running core init on: {self._last_base}")
        try:
            self._orchestrator.initialize_library(dry_run=False)
            self.log_msg("Init complete.")
        except Exception as e:
            self.log_msg(f"Init error: {e}")


    def _start_background_scan(self, base: Path, systems: list[str]):
        """Inicia a varredura da biblioteca em background."""
        self._scan_in_progress = True
        progress_cb = self._signaler.progress_signal.emit if self._signaler else None

        def _work():
            op = str(uuid.uuid4())[:8]
            log_cb = self._make_op_log_cb(op)
            try:
                self.status.showMessage(f"Operation {op} started", 3000)
            except Exception:
                pass
            return worker_scan_library(base, log_cb, progress_cb, self._cancel_event)

        def _done(result):
            self._handle_scan_finished(result, systems)

        self._run_in_background(_work, _done)

    def _handle_scan_finished(self, result: Any, systems: list[str]):
        """Processa a conclusão do scan e atualiza a UI."""
        if isinstance(result, Exception):
            self.log_msg(f"Scan error: {result}")
        elif result:
            self.log_msg(f"Scan complete. Total files: {result.get('count', 0)}")
            self._update_dashboard_stats(systems, stats=result)
            
            # Atualizar tabela de biblioteca com dados do banco
            self._refresh_library_table()

        self._scan_in_progress = False
        self._auto_select_last_system()

        if self._signaler:
            self._signaler.progress_signal.emit(0, "")
        else:
            self._progress_slot(0, "")

        try:
            self._refresh_quarantine_tab()
        except Exception as e:
            logging.debug(f"Quarantine refresh failed: {e}")

    def on_list(self, force_scan: bool = False):
        if not self._last_base:
            self.log_msg(MSG_SELECT_BASE)
            return

        if self._scan_in_progress and not force_scan:
            return

        self._set_ui_enabled(True)
        systems = self._orchestrator.dat_manager.list_systems() # Uso direto do orchestrator
        
        self._skip_list_side_effects = True
        try:
            self._refresh_system_list_ui(systems)
        finally:
            self._skip_list_side_effects = False
            
        self._log_systems(systems)
        self.log_msg("Scanning library...")
        self._start_background_scan(Path(self._last_base), systems)
        self._update_dashboard_stats(systems)

    def _update_dashboard_stats(self, systems=None, stats=None):
        try:
            if systems is None:
                if self._last_base:
                    systems = self._orchestrator.dat_manager.list_systems()
                else:
                    systems = []

            if hasattr(self.ui, "lbl_systems_count"):
                self.ui.lbl_systems_count.setText(f"Systems Configured: {len(systems)}")

            total_files = 0
            total_size = 0

            if stats:
                total_files = stats.get("count", 0)
                total_size = stats.get("size", 0)
            else:
                # Try to get from DB
                try:
                    from emumanager.library import LibraryDB

                    db = LibraryDB()
                    total_files = db.get_total_count()
                    total_size = db.get_total_size()
                except Exception:
                    pass

            if hasattr(self.ui, "lbl_total_roms"):
                self.ui.lbl_total_roms.setText(f"Total Files: {total_files}")

            # Format size human-readable
            try:
                from emumanager.common.formatting import human_readable_size

                size_str = human_readable_size(total_size)
            except Exception:
                size_str = f"{total_size / (1024**3):.2f} GB"

            if hasattr(self.ui, "lbl_library_size"):
                self.ui.lbl_library_size.setText(f"Library Size: {size_str}")

            # Update Last Scan time
            if stats and hasattr(self.ui, "lbl_last_scan"):
                from datetime import datetime

                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.ui.lbl_last_scan.setText(f"Last Scan: {now_str}")

        except Exception:
            logging.error("Failed to update dashboard stats", exc_info=True)

    def _refresh_system_list_ui(self, systems):
        try:
            if self.sys_list is not None:
                self.sys_list.clear()
                for s in systems:
                    self.sys_list.addItem(s)
                self._auto_select_last_system()

            # Update Gallery Combo
            if hasattr(self.ui, "combo_gallery_system"):
                self.ui.combo_gallery_system.clear()
                self.ui.combo_gallery_system.addItems(systems)
        except Exception:
            pass

    def _auto_select_last_system(self):
        try:
            if getattr(self, "_last_system", None):
                items = [
                    self.sys_list.item(i).text() for i in range(self.sys_list.count())
                ]
                if self._last_system in items:
                    idx = items.index(self._last_system)
                    self.sys_list.setCurrentRow(idx)
                    self._on_system_selected(self.sys_list.item(idx))
        except Exception:
            pass

    def _log_systems(self, systems):
        if not systems:
            self.log_msg("Nenhum sistema encontrado — execute 'init' primeiro.")
            return
        self.log_msg("Sistemas encontrados:")
        for s in systems:
            self.log_msg(f" - {s}")

    # --- Quarantine tab helpers ---
    def _refresh_quarantine_tab(self):
        try:
            if not hasattr(self.ui, "quarantine_table"):
                return
            table = self.ui.quarantine_table
            # Load corrupt entries from DB
            rows = [
                e
                for e in self.library_db.get_all_entries()
                if getattr(e, "status", "") == "CORRUPT"
            ]
            table.setRowCount(len(rows))
            for i, e in enumerate(rows):
                try:
                    table.setItem(i, 0, self._qtwidgets.QTableWidgetItem(str(e.path)))
                    table.setItem(i, 1, self._qtwidgets.QTableWidgetItem(str(e.size)))
                    try:
                        import time

                        m = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(e.mtime))
                    except Exception:
                        m = str(e.mtime)
                    table.setItem(i, 2, self._qtwidgets.QTableWidgetItem(m))
                    table.setItem(i, 3, self._qtwidgets.QTableWidgetItem(str(e.status)))
                except Exception:
                    continue
            table.resizeColumnsToContents()
        except Exception:
            logging.exception("Failed to refresh quarantine tab")

    def _refresh_library_table(self):
        """Atualiza a tabela de resultados com os dados da biblioteca após o scan."""
        try:
            if not hasattr(self.ui, "table_results"):
                return
                
            # Obter todas as entradas do banco
            all_entries = self.library_db.get_all_entries()
            
            if not all_entries:
                self.log_msg("No entries found in library database")
                return
            
            # Criar objetos compatíveis com _create_result_row
            from types import SimpleNamespace
            results = []
            for entry in all_entries:
                # Converter LibraryEntry para formato esperado pela tabela
                result = SimpleNamespace(
                    status=entry.status or "UNKNOWN",
                    filename=Path(entry.path).name,
                    full_path=entry.path,
                    match_name=entry.match_name or "",
                    dat_name=entry.dat_name or "",
                    crc=entry.crc32 or "",
                    sha1=entry.sha1 or "",
                    md5=entry.md5 or "",
                    sha256=entry.sha256 or ""
                )
                results.append(result)
            
            # Atualizar a tabela
            self.ui.table_results.setRowCount(len(results))
            for i, result in enumerate(results):
                self._create_result_row(i, result)
            
            self.log_msg(f"Library table updated with {len(results)} entries")
            
        except Exception as e:
            logging.exception(f"Failed to refresh library table: {e}")
            self.log_msg(f"Error updating library table: {e}")

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
            p = Path(sel[0].text())
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
        except Exception as e:
            self.log_msg(f"Failed to open location: {e}")

    def _quarantine_delete(self):
        try:
            sel = self.ui.quarantine_table.selectedItems()
            if not sel:
                return
            row = sel[0].row()
            p = Path(self.ui.quarantine_table.item(row, 0).text())
            qt = self._qtwidgets
            try:
                yes = qt.QMessageBox.question(
                    self.window,
                    "Confirm Delete",
                    f"Delete {p.name} from quarantine?",
                    qt.QMessageBox.StandardButton.Yes | qt.QMessageBox.StandardButton.No,
                )
            except Exception:
                yes = qt.QMessageBox.Yes
            if yes != qt.QMessageBox.StandardButton.Yes and yes != qt.QMessageBox.Yes:
                return
            try:
                if p.exists():
                    p.unlink()
                try:
                    self.library_db.remove_entry(str(p))
                    self.library_db.log_action(str(p), "DELETED", "User deleted quarantined file")
                except Exception:
                    pass
                self.ui.quarantine_table.removeRow(row)
                
                # Synchronize library UI after delete
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
            qpath = self.ui.quarantine_table.item(row, 0).text()
            p = Path(qpath)
            if not p.exists():
                try:
                    self._qtwidgets.QMessageBox.information(self.window, "Not found", "Quarantined file not found")
                except Exception:
                    pass
                return

            # Try to find original path from actions
            orig = None
            try:
                rows = self.library_db.get_actions(1000)
                for path, action, detail, ts in rows:
                    try:
                        if path == qpath and action == "QUARANTINED" and detail:
                            import re

                            m = re.search(r"Moved from (.+?) due to", detail)
                            if m:
                                orig = m.group(1)
                                break
                    except Exception:
                        continue
            except Exception:
                orig = None

            dest_dir = None
            if orig:
                try:
                    od = Path(orig).parent
                    if od.exists():
                        dest_dir = od
                except Exception:
                    dest_dir = None

            if not dest_dir:
                try:
                    dest = self._qtwidgets.QFileDialog.getExistingDirectory(
                        self.window, "Select destination folder to restore to"
                    )
                    if not dest:
                        return
                    dest_dir = Path(dest)
                except Exception:
                    try:
                        self._qtwidgets.QMessageBox.warning(self.window, "Error", "Could not get destination")
                    except Exception:
                        pass
                    return

            new_path = dest_dir / p.name
            try:
                shutil.move(str(p), str(new_path))
                # Update DB
                try:
                    entry = self.library_db.get_entry(qpath)
                    if entry:
                        entry.path = str(new_path)
                        entry.status = "UNKNOWN"
                        self.library_db.update_entry(entry)
                        self.library_db.log_action(str(new_path), "RESTORED", f"Restored from quarantine: {qpath}")
                        if qpath != str(new_path):
                            try:
                                self.library_db.remove_entry(qpath)
                            except Exception:
                                pass
                except Exception:
                    pass
                self.ui.quarantine_table.removeRow(row)
                
                # Synchronize library UI after restore
                try:
                    self._sync_after_verification()
                except Exception as e:
                    logging.debug(f"UI sync after restore failed: {e}")
            except Exception as e:
                try:
                    self._qtwidgets.QMessageBox.warning(self.window, "Error", f"Failed to restore: {e}")
                except Exception:
                    pass
        except Exception:
            logging.exception("Quarantine restore failed")

    def on_add(self):
        if not self._last_base:
            self.log_msg(MSG_SELECT_BASE)
            return

        src = self._select_file_dialog("Select ROM file")
        if not src:
            return

        system = self._select_system_dialog(src, Path(self._last_base))
        if not system:
            self.log_msg("Add ROM cancelled: No system selected.")
            return

        move = self._ask_yes_no("Move file?", "Move file instead of copy?")
        
        def _work_add():
            return self._orchestrator.add_rom(src, system=system, move=move)

        def _done_add(result):
            self._set_ui_enabled(True)
            if isinstance(result, Exception):
                self.log_msg(f"Add ROM error: {result}")
            else:
                self.log_msg(f"Added ROM -> {result}")
                self.on_list() 
                self._update_dashboard_stats()

        self._set_ui_enabled(False)
        self._run_in_background(_work_add, _done_add)

    def _select_file_dialog(self, title: str) -> Optional[Path]:
        qt = self._qtwidgets
        # Use static method for better compatibility
        fname, _ = qt.QFileDialog.getOpenFileName(self.window, title)
        if fname:
            return Path(fname)
        return None

    def _select_system_dialog(self, src: Path, base: Path) -> Optional[str]:
        qt = self._qtwidgets
        from emumanager.common.registry import registry
        
        provider = registry.find_provider_for_file(src)
        guessed = provider.system_id if provider else None
        systems = self._orchestrator.dat_manager.list_systems()

        if not systems:
            from emumanager.config import EXT_TO_SYSTEM
            systems = sorted(list(set(EXT_TO_SYSTEM.values())))

        items = sorted(systems)
        idx = items.index(guessed) if guessed in items else 0

        system, ok = qt.QInputDialog.getItem(
            self.window, "Select System", "Target System:", items, idx, True
        )
        return system if ok and system else None

    def _ask_yes_no(self, title: str, msg: str) -> bool:
        qt = self._qtwidgets
        try:
            yes_btn = qt.QMessageBox.StandardButton.Yes
            no_btn = qt.QMessageBox.StandardButton.No
        except AttributeError:
            yes_btn = qt.QMessageBox.Yes
            no_btn = qt.QMessageBox.No

        ans = qt.QMessageBox.question(self.window, title, msg, yes_btn | no_btn)
        return ans == yes_btn

    # UI helpers for systems/rom listing
    def _on_system_selected(self, item):
        try:
            if getattr(self, "_skip_list_side_effects", False):
                return
            system = item.text()
            self._populate_roms(system)
            
            # Mostrar estatísticas do sistema
            try:
                entries = self.library_db.get_entries_by_system(system)
                stats = {
                    "total": len(entries),
                    "verified": sum(1 for e in entries if e.status == "VERIFIED"),
                    "corrupt": sum(1 for e in entries if e.status == "CORRUPT"),
                    "unknown": sum(1 for e in entries if e.status == "UNKNOWN"),
                }
                self.log_msg(
                    f"System '{system}': {stats['total']} files - "
                    f"{stats['verified']} verified, {stats['corrupt']} corrupt, "
                    f"{stats['unknown']} unknown"
                )
            except Exception as e:
                logging.debug(f"Failed to get system stats: {e}")
            
            # Remember last selected system
            try:
                if self._settings:
                    self._settings.setValue("ui/last_system", system)
            except Exception:
                pass

            # Toggle Switch actions
            if hasattr(self.ui, "grp_switch_actions"):
                is_switch = system.lower() == "switch"
                self.ui.grp_switch_actions.setVisible(is_switch)
            # Apply current filter if present
            if hasattr(self.ui, "edit_filter"):
                self._apply_rom_filter(self.ui.edit_filter.text())
        except Exception:
            pass

    def _on_rom_double_clicked(self, item):
        try:
            # double-click compresses by default
            self.tools_controller.on_compress_selected()
        except Exception as e:
            logging.debug(f"Double-click action failed: {e}")

    def _list_files_recursive(self, root: Path) -> list[Path]:
        """List files recursively, excluding hidden files, DATs, and non-game files."""
        files = []
        if not root.exists(): return files

        # Extensions to ignore (junk, metadata, images, etc)
        IGNORED_EXTENSIONS = {
            ".dat", ".xml", ".txt", ".nfo", ".pdf", ".doc", ".docx", ".jpg", ".jpeg",
            ".png", ".bmp", ".gif", ".ico", ".ini", ".cfg", ".conf", ".db", ".ds_store",
            ".url", ".lnk", ".desktop", ".py", ".pyc", ".log", ".err", ".out",
        }

        for p in root.rglob("*"):
            if not p.is_file() or p.name.startswith("."): continue
            if p.suffix.lower() in IGNORED_EXTENSIONS: continue

            try:
                rel = p.relative_to(root)
                if any(part.startswith(".") for part in rel.parts): continue

                parts_lower = [part.lower() for part in rel.parts]
                if any(d in parts_lower for d in ("dats", "no-intro", "redump")):
                    continue

                files.append(p)
            except Exception: continue

        files.sort(key=lambda p: str(p).lower())
        return files

    def _get_list_files_fn(self):
        """Returns the appropriate list_files function based on settings."""
        if self.chk_process_selected.isChecked():
            return self._list_files_selected
        return self._list_files_recursive

    def _find_rom_files(self, system: str) -> list[Path]:
        """Tenta localizar e listar os ficheiros físicos de um sistema."""
        try:
            roms_root = self._orchestrator.session.roms_path
            roms_dir = roms_root / system
            if not roms_dir.exists():
                self.log_msg(f"Directory not found: {roms_dir}")
                return []

            self.log_msg(f"Listing ROMs for {system} in {roms_dir}")
            full_files = self._list_files_recursive(roms_dir)
            return [p.relative_to(roms_dir) for p in full_files]
        except Exception as e:
            self.log_msg(f"Error listing ROMs: {e}")
            logging.error("Failed to find ROM files", exc_info=True)
            return []

    def _populate_roms(self, system: str):
        """Popula a lista de ROMs com informações do banco de dados."""
        if not self._last_base:
            return

        try:
            # Obter entradas do banco de dados para este sistema
            entries = self.library_db.get_entries_by_system(system)
            entry_dict = {Path(e.path).name: e for e in entries}
            
            # Listar arquivos físicos
            files = self._find_rom_files(system)
            self._current_roms = [str(p) for p in files]
            self.log_msg(f"Found {len(files)} files ({len(entries)} in database).")

            if self.rom_list is not None:
                self.rom_list.clear()
                for f in files:
                    filename = str(f)
                    # Adicionar indicador de status se disponível
                    file_key = Path(f).name
                    if file_key in entry_dict:
                        entry = entry_dict[file_key]
                        status = entry.status or "UNKNOWN"
                        # Adicionar emoji/símbolo baseado no status
                        if status == "VERIFIED":
                            display_name = f"✓ {filename}"
                        elif status == "CORRUPT":
                            display_name = f"✗ {filename}"
                        elif status == "ERROR":
                            display_name = f"⚠ {filename}"
                        else:
                            display_name = f"? {filename}"
                    else:
                        display_name = f"  {filename}"
                    
                    self.rom_list.addItem(display_name)
        except Exception as e:
            logging.exception(f"Failed to populate roms: {e}")
            self.log_msg(f"Error populating ROM list: {e}")

    def _on_filter_text(self, text: str):
        try:
            self._apply_rom_filter(text)
        except Exception:
            pass

    def _apply_rom_filter(self, text: str):
        if not hasattr(self, "_current_roms"):
            return
        try:
            query = (text or "").lower().strip()
            items = self._current_roms
            if query:
                items = [s for s in items if query in s.lower()]
            self.ui.rom_list.clear()
            for s in items:
                self.ui.rom_list.addItem(s)
        except Exception:
            pass

    def on_cancel_requested(self):
        try:
            self._cancel_event.set()
            from emumanager.common.execution import cancel_current_process

            ok = cancel_current_process()
            self.log_msg(
                "Cancel requested" + (" — cancelled" if ok else " — nothing to cancel")
            )
        except Exception:
            self.log_msg("Cancel requested — failed to call cancel")

    def _ensure_env(self, base_path: Path):
        """Ensure environment tools and paths are configured for the given base path."""
        if self._env and self._env.get("ROMS_DIR") == base_path:
            return

        try:
            from emumanager.common.execution import find_tool
            from emumanager.switch.main_helpers import configure_environment

            # Create a dummy args object for configure_environment
            class Args:
                dir = str(base_path)
                keys = str(base_path / "keys.txt")  # Default assumption
                compress = False
                decompress = False

            # We need to find keys.txt or ask user, but for now let's assume it's in
            # base. If keys are not found, configure_environment might fail or warn.
            # Let's try to find keys in common locations if not at base/keys.txt
            keys_path = base_path / "keys.txt"
            if not keys_path.exists():
                keys_path = base_path / "prod.keys"

            args = Args()
            args.keys = str(keys_path)

            # Mock logger to capture output to GUI log
            class GuiLogger:
                def info(_s, msg, *a):
                    self.log_msg(msg % a if a else msg)

                def warning(_s, msg, *a):
                    self.log_msg("WARN: " + (msg % a if a else msg))

                def error(_s, msg, *a):
                    self.log_msg("ERROR: " + (msg % a if a else msg))

                def debug(_s, msg, *a):
                    pass  # ignore debug

                def exception(_s, msg, *a):
                    self.log_msg("EXCEPTION: " + (msg % a if a else msg))

            self._env = configure_environment(args, GuiLogger(), find_tool)
            self.log_msg(f"Environment configured for {base_path}")
        except Exception as e:
            self.log_msg(f"Failed to configure environment: {e}")
            self._env = {}

    def _get_common_args(self):
        class Args:
            pass

        args = Args()
        args.dry_run = self.chk_dry_run.isChecked()
        args.level = self.spin_level.value()
        profile = self.combo_profile.currentText()
        args.compression_profile = profile if profile != "None" else None
        args.rm_originals = self.chk_rm_originals.isChecked()
        args.quarantine = self.chk_quarantine.isChecked()
        args.deep_verify = self.chk_deep_verify.isChecked()
        args.clean_junk = False  # Handled separately
        args.organize = False  # Handled separately
        args.compress = False
        args.decompress = False
        args.recompress = False
        args.keep_on_failure = False
        args.cmd_timeout = None
        args.quarantine_dir = None
        args.report_csv = None
        args.dup_check = "fast"
        args.verbose = False
        args.progress_callback = self.progress_hook
        args.cancel_event = self._cancel_event
        args.standardize_names = self.chk_standardize_names.isChecked()
        args.orchestrator = self._orchestrator
        args.library_db = self.library_db
        return args

    def on_open_library(self):
        qt = self._qtwidgets
        dlg = qt.QFileDialog(self.window, "Select Library Directory")
        try:
            dlg.setFileMode(qt.QFileDialog.FileMode.Directory)
        except AttributeError:
            dlg.setFileMode(qt.QFileDialog.Directory)

        if dlg.exec():
            base = Path(dlg.selectedFiles()[0])
            self._last_base = base
            self.ui.lbl_library.setText(str(base))
            self.ui.lbl_library.setStyleSheet("font-weight: bold; color: #3daee9;")

            # Update logger to write to the new library's log folder
            self._update_logger(base)

            self.log_msg(f"Library opened: {base}")

            # Enable verification button (auto-discovery possible)
            self.ui.btn_verify_dat.setEnabled(True)
            if hasattr(self.ui, "btn_identify_all"):
                self.ui.btn_identify_all.setEnabled(True)

            # Auto-refresh list if possible
            try:
                self.on_list()
            except Exception:
                pass

    def on_select_dat(self):
        qt = self._qtwidgets
        dlg = qt.QFileDialog(self.window, "Select DAT File")
        try:
            dlg.setFileMode(qt.QFileDialog.FileMode.ExistingFile)
        except AttributeError:
            dlg.setFileMode(qt.QFileDialog.ExistingFile)
        dlg.setNameFilter("DAT Files (*.dat *.xml)")

        if dlg.exec():
            path = Path(dlg.selectedFiles()[0])
            self._current_dat_path = path
            self.ui.lbl_dat_path.setText(path.name)
            self.ui.lbl_dat_path.setStyleSheet("color: #3daee9; font-weight: bold;")
            self.ui.btn_verify_dat.setEnabled(True)
            self.log_msg(f"Selected DAT: {path}")

    def on_verify_dat(self):
        if not self._last_base:
            self.log_msg(MSG_SELECT_BASE)
            return

        # Determine target path (System specific if selected)
        target_path = self._last_base
        selected_items = self.ui.sys_list.selectedItems()
        if selected_items:
            system_name = selected_items[0].text()
            # Try to resolve system path
            p1 = self._last_base / system_name
            p2 = self._last_base / "roms" / system_name

            if p1.exists():
                target_path = p1
                self.log_msg(f"Targeting system folder: {system_name}")
            elif p2.exists():
                target_path = p2
                self.log_msg(f"Targeting system folder: {system_name}")

        # If no DAT selected, prompt user
        if not getattr(self, "_current_dat_path", None):
            self.on_select_dat()
            # If still no DAT, return (user cancelled)
            if not getattr(self, "_current_dat_path", None):
                return

        dat_path = self._current_dat_path

        args = self._get_common_args()
        args.dat_path = dat_path

        # Try to locate 'dats' folder in common locations
        candidates = [
            self._last_base / "dats",
            self._last_base.parent / "dats",
            self._last_base.parent.parent / "dats",
        ]
        args.dats_root = next((p for p in candidates if p.exists()), None)

        # Clear previous results
        self.ui.table_results.setRowCount(0)

        def _work():
            op = uuid.uuid4().hex
            log_cb = self._make_op_log_cb(op)
            try:
                self.status.showMessage(f"Operation {op} started", 3000)
            except Exception:
                pass
            return worker_hash_verify(
                target_path, args, log_cb, self._get_list_files_fn()
            )

        def _done(res):
            if hasattr(res, "results"):
                self.log_msg(res.text)
                # Store for filtering/export
                self._last_verify_results = res.results
                self.on_verification_filter_changed()
                
                # Sincronizar dados após verificação
                self._sync_after_verification()
            else:
                self.log_msg(str(res))
            self._set_ui_enabled(True)

        self._set_ui_enabled(False)
        self._run_in_background(_work, _done)

    def _sync_after_verification(self):
        """Sincroniza os dados da biblioteca após verificação."""
        try:
            # Recarregar a lista de ROMs do sistema atual para refletir novos status
            current_sys_item = self.sys_list.currentItem()
            if current_sys_item:
                system = current_sys_item.text()
                self.log_msg(f"🔄 Refreshing {system} library data...")
                self._populate_roms(system)
            
            # Atualizar o inspector se houver ROM selecionada
            current_rom = self.rom_list.currentItem()
            if current_rom and current_sys_item:
                system = current_sys_item.text()
                rom_text = current_rom.text()
                # Remover indicadores de status
                if rom_text.startswith(("✓ ", "✗ ", "⚠ ", "? ", "  ")):
                    rom_text = rom_text[2:]
                
                try:
                    from .manager import get_roms_dir
                    base_roms_dir = get_roms_dir(Path(self._last_base))
                    full_path = base_roms_dir / system / rom_text
                    self._show_rom_metadata(str(full_path.resolve()))
                except Exception as e:
                    logging.debug(f"Failed to update inspector after verification: {e}")
                    
            self.log_msg("✓ Library data synchronized")
        except Exception as e:
            logging.debug(f"Failed to sync after verification: {e}")

    def _get_rehash_targets(self):
        """Identifica os itens da tabela de verificação que devem ser re-hashados."""
        try:
            table = self.ui.table_results
            filtered = self._get_filtered_verification_results()
            indexes = table.selectedIndexes()
            sel_rows = sorted({idx.row() for idx in indexes})
            
            if sel_rows:
                return [filtered[r] for r in sel_rows if 0 <= r < len(filtered)]
            
            # Default: all HASH_FAILED
            return [r for r in filtered if getattr(r, "status", None) == "HASH_FAILED"]
        except Exception as e:
            logging.error(f"Failed to get rehash targets: {e}")
            return []

    def _rehash_single_item(self, target: Any, dat_path: Optional[Path]):
        """Executa o re-hash ou re-identificação de um único arquivo."""
        try:
            p = Path(target.full_path) if getattr(target, "full_path", None) else None
            if not p or not p.exists():
                return str(p), "missing"

            if dat_path:
                return self._reidentify_with_dat(p, dat_path)
            
            return self._recalculate_hashes_to_db(p)
        except Exception as e:
            logging.debug(f"Rehash failed for {target}: {e}")
            return str(target), f"error:{e}"

    def _reidentify_with_dat(self, path: Path, dat_path: Path):
        op = uuid.uuid4().hex
        log_cb = self._make_op_log_cb(op)
        try:
            self.status.showMessage(f"Operation {op} started", 3000)
        except Exception:
            pass
        out = worker_identify_single_file(path, dat_path, log_cb, None)
        return str(path), out

    def _recalculate_hashes_to_db(self, path: Path):
        algos = ("crc32", "sha1")
        if getattr(self, "chk_deep_verify", None) and self.chk_deep_verify.isChecked():
            algos = ("crc32", "md5", "sha1", "sha256")
        
        hashes = calculate_hashes(path, algorithms=algos)
        try:
            st = path.stat()
            from emumanager.library import LibraryEntry
            new_entry = LibraryEntry(
                path=str(path.resolve()),
                system="unknown",
                size=st.st_size,
                mtime=st.st_mtime,
                crc32=hashes.get("crc32"),
                md5=hashes.get("md5"),
                sha1=hashes.get("sha1"),
                sha256=hashes.get("sha256"),
                status="UNKNOWN"
            )
            self.library_db.update_entry(new_entry)
            return str(path), "rehash_ok"
        except Exception as e:
            return str(path), f"error:{e}"

    def _update_in_memory_results(self, rehash_results: list[tuple[str, str]]):
        """Atualiza os resultados cacheados com os novos dados do banco de dados."""
        for p, _ in rehash_results:
            for rr in getattr(self, "_last_verify_results", []):
                if getattr(rr, "full_path", None) == p:
                    try:
                        e = self.library_db.get_entry(p)
                        if e:
                            rr.crc, rr.sha1, rr.md5, rr.sha256 = e.crc32, e.sha1, e.md5, e.sha256
                            rr.status, rr.match_name = e.status, e.match_name
                    except Exception as ex:
                        logging.debug(f"Failed to sync memory result for {p}: {ex}")

    def on_try_rehash(self):
        """Try re-hash selected verification rows or all HASH_FAILED rows."""
        targets = self._get_rehash_targets()
        if not targets:
            self.log_msg("No files selected for rehash")
            return

        dat_path = getattr(self, "_current_dat_path", None)

        def _work():
            return [self._rehash_single_item(t, dat_path) for t in targets]

        def _done(res):
            self._set_ui_enabled(True)
            if isinstance(res, Exception):
                self.log_msg(f"Rehash error: {res}")
                return

            self.log_msg(f"Rehash complete. Processed: {len(res)} items")
            if dat_path:
                try:
                    self.on_verify_dat()
                except Exception as e:
                    logging.debug(f"Refresh after rehash failed: {e}")
            else:
                self._update_in_memory_results(res)
                self.on_verification_filter_changed()

        self._set_ui_enabled(False)
        self._run_in_background(_work, _done)

    def _populate_verification_results(
        self, results, status_filter: Optional[str] = None
    ):
        filtered = [
            r for r in results if (not status_filter or r.status == status_filter)
        ]
        self.ui.table_results.setRowCount(len(filtered))
        for i, r in enumerate(filtered):
            self._create_result_row(i, r)

    def _create_result_row(self, row_idx, result):
        qt = self._qtwidgets

        # Status Item with Color
        item_status = qt.QTableWidgetItem(result.status)
        self._style_status_item(item_status, result.status)
        self.ui.table_results.setItem(row_idx, 0, item_status)

        # Other columns
        self.ui.table_results.setItem(row_idx, 1, qt.QTableWidgetItem(result.filename))
        self.ui.table_results.setItem(
            row_idx, 2, qt.QTableWidgetItem(result.match_name or "")
        )
        self.ui.table_results.setItem(
            row_idx, 3, qt.QTableWidgetItem(result.dat_name or "")
        )
        self.ui.table_results.setItem(row_idx, 4, qt.QTableWidgetItem(result.crc or ""))
        self.ui.table_results.setItem(
            row_idx, 5, qt.QTableWidgetItem(result.sha1 or "")
        )
        # New columns: MD5 and SHA256 (if deep verify) + Note column
        try:
            self.ui.table_results.setItem(
                row_idx,
                6,
                qt.QTableWidgetItem(getattr(result, "md5", "") or ""),
            )
            self.ui.table_results.setItem(
                row_idx,
                7,
                qt.QTableWidgetItem(getattr(result, "sha256", "") or ""),
            )
            # Note column (diagnostic messages such as HASH_FAILED reason)
            note = ""
            if getattr(result, "status", None) == "HASH_FAILED":
                note = result.match_name or "Hashing failed"
            elif getattr(result, "status", None) == "MISMATCH":
                # mismatch reason sometimes lives in match_name
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
                fp = results[row].full_path
                if fp:
                    self._open_file_location(Path(fp))
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
        return [r for r in all_results if (not status or r.status == status)]

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

            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(
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
                for r in results:
                    w.writerow(
                        [
                            r.status,
                            r.filename,
                            r.match_name or "",
                            r.crc or "",
                            r.sha1 or "",
                            getattr(r, "md5", "") or "",
                            getattr(r, "sha256", "") or "",
                        ]
                    )
            self.log_msg(f"Exported CSV: {path}")
        except Exception as e:
            self.log_msg(f"Export CSV error: {e}")

    def _list_files_selected(self, root: Path) -> list[Path]:
        """Return only selected files from the UI, resolved to absolute paths."""
        if not self.rom_list or not self.sys_list:
            return []

        selected_items = self.rom_list.selectedItems()
        if not selected_items:
            return []

        sys_item = self.sys_list.currentItem()
        if not sys_item:
            return []

        system = sys_item.text()
        roms_dir = Path(self._last_base) / "roms" / system

        files = []
        for item in selected_items:
            rel_path = item.text()
            full_path = roms_dir / rel_path
            # Only include if it exists (sanity check)
            if full_path.exists():
                files.append(full_path)

        return files

    def on_organize_all(self):
        """Organize all supported systems sequentially using the Core Orchestrator."""
        if not self._last_base:
            self.log_msg(MSG_SELECT_BASE)
            return

        # Confirmation
        reply = self._qtwidgets.QMessageBox.question(
            self.window,
            "Confirm Organization",
            "This will scan, distribute files from root to system folders, and rename everything based on metadata.\n"
            "Are you sure you want to proceed?",
            self._qtwidgets.QMessageBox.StandardButton.Yes
            | self._qtwidgets.QMessageBox.StandardButton.No,
            self._qtwidgets.QMessageBox.StandardButton.No,
        )
        if reply != self._qtwidgets.QMessageBox.StandardButton.Yes:
            return

        self._ensure_env(self._last_base)
        args = self._get_common_args()

        self.log_msg("Starting global organization flow...")

        def _work():
            return self._orchestrator.full_organization_flow(
                dry_run=args.dry_run, 
                progress_cb=self.progress_hook
            )

        def _done(res):
            if isinstance(res, Exception):
                self.log_msg(f"Organization error: {res}")
            else:
                self.log_msg(f"Organization complete: {res}")
            self._set_ui_enabled(True)
            self.on_list() # Refresh list
            self._update_dashboard_stats()

        self._set_ui_enabled(False)
        self._run_in_background(_work, _done)

    def on_verify_all(self):
        """Verify all supported systems sequentially."""
        if not self._last_base:
            self.log_msg(MSG_SELECT_BASE)
            return
        self.log_msg(
            "Starting batch verification (Not implemented yet for all systems)"
        )
        # Placeholder
        self.tools_controller.on_health_check()

    def on_delete_selected(self):
        if not self.rom_list:
            return
        try:
            sel_items = self.rom_list.selectedItems()
            if not sel_items:
                self.log_msg(MSG_NO_ROM)
                return

            sys_item = self.sys_list.currentItem() if self.sys_list else None
            if not sys_item:
                self.log_msg(MSG_NO_SYSTEM)
                return
            
            system = sys_item.text()
            roms_root = self._orchestrator.session.roms_path
            
            files_to_delete = []
            for item in sel_items:
                filepath = roms_root / system / item.text()
                if filepath.exists():
                    files_to_delete.append(filepath)

            if not files_to_delete: return

            msg = f"Are you sure you want to delete {len(files_to_delete)} files?"
            if not self._ask_yes_no("Confirm Delete", msg): return

            count = 0
            for fp in files_to_delete:
                if self._orchestrator.delete_rom_file(fp):
                    count += 1
                    self.log_msg(f"Deleted: {fp.name}")
                else:
                    self.log_msg(f"Failed to delete {fp.name}")

            if count > 0:
                self._populate_roms(system)
                self._update_dashboard_stats()

        except Exception as e:
            self.log_msg(f"Error deleting files: {e}")
            logging.error("Failed deletion operation", exc_info=True)

    def on_verify_selected(self):
        if not self.rom_list:
            return
        try:
            sel = self.rom_list.currentItem()
            if sel is None:
                self.log_msg(MSG_NO_ROM)
                return
            
            rom_name = sel.text()
            sys_item = self.sys_list.currentItem() if self.sys_list else None
            if not sys_item:
                self.log_msg(MSG_NO_SYSTEM)
                return
            
            system = sys_item.text()
            roms_root = self._orchestrator.session.roms_path
            filepath = roms_root / system / rom_name

            if not filepath.exists():
                self.log_msg(f"File not found: {filepath}")
                return

            self.log_msg(f"Identifying {rom_name}...")

            def _work():
                return self._orchestrator.identify_single_file(filepath)

            def _done(res):
                self._set_ui_enabled(True)
                if not res:
                    self.log_msg(f"Failed to identify {rom_name}")
                else:
                    self.log_msg(f"Metadata for {rom_name}: {res}")
                    self._qtwidgets.QMessageBox.information(self.window, "Identification", str(res))

            self._set_ui_enabled(False)
            self._run_in_background(_work, _done)

        except Exception as e:
            self.log_msg(f"Error verifying file: {e}")
            logging.error("Failed verification operation", exc_info=True)

    def on_rename_to_standard_selected(self):
        """Renomeia a ROM selecionada para o padrão canónico via Orchestrator."""
        if not self.rom_list: return
        try:
            sel_items = self.rom_list.selectedItems()
            if not sel_items:
                self.log_msg(MSG_NO_ROM)
                return

            sys_item = self.sys_list.currentItem() if self.sys_list else None
            if not sys_item:
                self.log_msg(MSG_NO_SYSTEM)
                return
            
            system = sys_item.text()
            self.log_msg(f"Organizando nomes para: {system}")
            
            # Executar workflow de organização apenas para este sistema
            def _work():
                return self._orchestrator.organize_names(system_id=system, dry_run=False)

            def _done(res):
                self._set_ui_enabled(True)
                self.log_msg(f"Renomeação concluída: {res}")
                self._populate_roms(system)
                self._update_dashboard_stats()
                # Sincronizar inspector após renomeação
                self._sync_after_verification()

            self._set_ui_enabled(False)
            self._run_in_background(_work, _done)

        except Exception as e:
            self.log_msg(f"Error renaming files: {e}")
            logging.error("Failed rename operation", exc_info=True)

    def _rename_single_to_standard(
        self, system: str, roms_root: Path, filepath: Path
    ) -> bool:
        """Call the per-system single-file organizer and return True if renamed.
        """
        try:
            logger = GuiLogger(self.log_msg)
            # Build a minimal args object
            args = SimpleNamespace()
            args.dry_run = (
                getattr(self, "chk_dry_run", False)
                and getattr(self.chk_dry_run, "isChecked", lambda: False)()
            )

            if system == "psp":
                # returns bool
                return _organize_psp_item(filepath, args, logger)
            elif system == "psx":
                ok, _ = _organize_psx_file(filepath, args, logger)
                return bool(ok)
            elif system == "ps2":
                return _organize_ps2_file(filepath, args, logger)
            elif system in ("gamecube", "wii", "gamecube/wii", "gc", "wiiu"):
                # Dolphin organizes within a target_dir; pass system folder
                target_dir = roms_root / system
                # Dolphin returns 'renamed'|'skipped'|'error'
                res = _organize_dolphin_file(filepath, target_dir, args.dry_run, logger)
                return res == "renamed"
            elif system == "3ds":
                return _organize_n3ds_item(filepath, args, logger)
            elif system == "ps3":
                return _organize_ps3_item(filepath, args, logger)
            else:
                self.log_msg(f"Rename not supported for system: {system}")
                return False
        except Exception as e:
            self.log_msg(f"Rename helper error: {e}")
            return False

    def _guess_rom_region(self, path_str: str) -> Optional[str]:
        if "(USA)" in path_str or "(US)" in path_str:
            return "US"
        if "(Europe)" in path_str or "(EU)" in path_str:
            return "EN"
        if "(Japan)" in path_str or "(JP)" in path_str:
            return "JA"
        return None

    def _on_rom_selection_changed(self, current, previous):
        if not current:
            self.cover_label.clear()
            self.cover_label.setText("No ROM selected")
            return

        sys_item = self.sys_list.currentItem()
        if not sys_item or not self._last_base:
            return

        system = sys_item.text()
        rom_rel_path = current.text()
        
        # Remover indicadores de status do nome se presentes
        rom_display_name = rom_rel_path
        if rom_display_name.startswith(("✓ ", "✗ ", "⚠ ", "? ", "  ")):
            rom_display_name = rom_display_name[2:]
        
        try:
            from .manager import get_roms_dir
            base_roms_dir = get_roms_dir(Path(self._last_base))
            full_path = base_roms_dir / system / rom_display_name
            
            # Mostrar metadados da biblioteca no log
            self._show_rom_metadata(str(full_path.resolve()))
            
            cache_dir = Path(self._last_base) / ".covers"
            cache_dir.mkdir(exist_ok=True)
            
            self.log_msg(f"Fetching cover for {rom_display_name} (System: {system})...")
            region = self._guess_rom_region(rom_display_name)
            
            self._start_cover_downloader(system, region, cache_dir, full_path)
        except Exception as e:
            logging.error(f"Selection change failed: {e}")

    def _show_rom_metadata(self, full_path: str):
        """Mostra metadados da ROM no log a partir do banco de dados."""
        try:
            entry = self.library_db.get_entry(full_path)
            if not entry:
                self.log_msg(f"⚠ No metadata found in library for this file")
                return
            
            # Mostrar informações básicas
            self.log_msg("─" * 60)
            self.log_msg(f"📋 ROM METADATA:")
            self.log_msg(f"  Status: {entry.status}")
            
            if entry.match_name:
                self.log_msg(f"  Title: {entry.match_name}")
            
            if entry.dat_name:
                self.log_msg(f"  Serial/ID: {entry.dat_name}")
            
            # Mostrar hashes se disponíveis
            if entry.crc32 or entry.sha1 or entry.md5:
                self.log_msg(f"  Hashes:")
                if entry.crc32:
                    self.log_msg(f"    CRC32: {entry.crc32}")
                if entry.sha1:
                    self.log_msg(f"    SHA1: {entry.sha1}")
                if entry.md5:
                    self.log_msg(f"    MD5: {entry.md5}")
            
            # Mostrar informações de tamanho
            try:
                size_mb = entry.size / (1024 * 1024)
                self.log_msg(f"  Size: {size_mb:.2f} MB")
            except Exception:
                pass
            
            # Mostrar metadados extras se disponíveis
            if entry.extra_metadata:
                extra = entry.extra_metadata
                if extra.get("title"):
                    self.log_msg(f"  Game Title: {extra['title']}")
                if extra.get("serial"):
                    self.log_msg(f"  Game Serial: {extra['serial']}")
                if extra.get("region"):
                    self.log_msg(f"  Region: {extra['region']}")
                if extra.get("ra_compatible"):
                    self.log_msg(f"  RetroAchievements: ✓ Compatible")
            
            self.log_msg("─" * 60)
            
        except Exception as e:
            logging.debug(f"Failed to show ROM metadata: {e}")

    def _start_cover_downloader(self, system, region, cache_dir, full_path):
        downloader = CoverDownloader(system, None, region, str(cache_dir), str(full_path))
        
        conn_type = (
            self._Qt_enum.ConnectionType.QueuedConnection
            if self._Qt_enum and hasattr(self._Qt_enum, "ConnectionType")
            else self._qtcore.Qt.QueuedConnection
        )

        downloader.signals.finished.connect(self._update_cover_image, conn_type)
        downloader.signals.log.connect(self.log_msg, conn_type)

        if self._qtcore:
            self._qtcore.QThreadPool.globalInstance().start(downloader)

    def _download_dats_phase(self, downloader):
        self.progress_hook(0.0, "Fetching No-Intro file list...")
        ni_files = downloader.list_available_dats("no-intro")

        self.progress_hook(0.0, "Fetching Redump file list...")
        rd_files = downloader.list_available_dats("redump")
        
        return ni_files, rd_files

    def _execute_dat_downloads(self, downloader, ni_files, rd_files):
        import concurrent.futures
        total_files = len(ni_files) + len(rd_files)
        if total_files == 0:
            return "No DAT files found to download."

        self.log_msg(f"Found {len(ni_files)} No-Intro and {len(rd_files)} Redump DATs. Starting...")
        completed = success = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for f in ni_files: futures.append(executor.submit(downloader.download_dat, "no-intro", f))
            for f in rd_files: futures.append(executor.submit(downloader.download_dat, "redump", f))

            for future in concurrent.futures.as_completed(futures):
                completed += 1
                try:
                    if future.result(): success += 1
                except Exception as e:
                    logging.debug(f"DAT download failed: {e}")
                
                percent = completed / total_files
                self.progress_hook(percent, f"Downloading: {completed}/{total_files} ({(percent * 100):.1f}%)")

        return f"Update complete. Downloaded {success}/{total_files} DATs."

    def on_update_dats(self):
        if not self._last_base:
            self.log_msg(MSG_SELECT_BASE)
            return

        dats_dir = self._last_base / "dats"
        dats_dir.mkdir(parents=True, exist_ok=True)

        self.log_msg("Initializing DAT update process...")
        self.progress_hook(0.0, "Connecting to GitHub...")
        self._set_ui_enabled(False)

        def _work():
            downloader = DatDownloader(dats_dir)
            ni, rd = self._download_dats_phase(downloader)
            return self._execute_dat_downloads(downloader, ni, rd)

        def _done(res):
            self.log_msg(str(res))
            self._set_ui_enabled(True)
            self.progress_hook(1.0, "DAT update complete")

        self._run_in_background(_work, _done)

    def on_identify_selected(self):
        """Identify the selected ROM using a DAT file."""
        if not self.rom_list:
            return

        sel = self.rom_list.currentItem()
        if not sel:
            self.log_msg(MSG_NO_ROM)
            return

        # Get file path
        if not self._last_base:
            self.log_msg(MSG_SELECT_BASE)
            return

        system = (
            self.sys_list.currentItem().text() if self.sys_list.currentItem() else ""
        )
        if not system:
            self.log_msg(MSG_NO_SYSTEM)
            return

        base_roms_dir = get_roms_dir(Path(self._last_base))
        rom_rel_path = sel.text()
        full_path = base_roms_dir / system / rom_rel_path

        if not full_path.exists():
            self.log_msg(f"File not found: {full_path}")
            return

        # Try to auto-discover DAT first
        from emumanager.verification.dat_manager import find_dat_for_system

        dat_path = None

        # Look in dats folder
        dats_dir = self._last_base / "dats"
        if dats_dir.exists():
            found = find_dat_for_system(dats_dir, system)
            if found:
                dat_path = str(found)

        # If not found, ask user
        if not dat_path:
            dat_path, _ = self._qtwidgets.QFileDialog.getOpenFileName(
                self.window,
                "Select DAT File",
                str(self._last_base),
                "DAT Files (*.dat *.xml)",
            )

        if not dat_path:
            return

        self.log_msg(f"Identifying {full_path.name} using {Path(dat_path).name}...")

        # Use signal emitter for thread safety
        progress_cb = self._signaler.progress_signal.emit if self._signaler else None

        def _work():
            op = uuid.uuid4().hex
            log_cb = self._make_op_log_cb(op)
            try:
                self.status.showMessage(f"Operation {op} started", 3000)
            except Exception:
                pass
            return worker_identify_single_file(
                full_path, Path(dat_path), log_cb, progress_cb
            )

        def _done(res):
            self.log_msg(str(res))
            self._qtwidgets.QMessageBox.information(
                self.window, "Identification Result", str(res)
            )
            # Sincronizar dados após identificação
            self._sync_after_verification()

        self._run_in_background(_work, _done)

    def on_identify_all(self):
        if not self._last_base:
            self.log_msg(MSG_SELECT_BASE)
            return

        # Confirm with user as this is heavy
        if not self._ask_yes_no(
            "Start Full Identification?",
            "This will load ALL DAT files into memory and scan the library. "
            "It may take a significant amount of RAM and time. Continue?",
        ):
            return

        args = self._get_common_args()

        # Collect potential DAT locations
        # We include the library folder itself to find DATs installed there
        potential_roots = [
            self._last_base / "dats",
            self._last_base,
            self._last_base.parent / "dats",
            self._last_base.parent.parent / "dats",
        ]

        # Filter only existing directories
        args.dats_roots = [p for p in potential_roots if p.exists()]

        if not args.dats_roots:
            self.log_msg(
                "Error: No DATs locations found. "
                "Please run 'Update DATs' or place .dat files in the library."
            )
            return

        # Clear previous results
        self.ui.table_results.setRowCount(0)
        self.log_msg("Starting full identification...")

        def _work():
            op = uuid.uuid4().hex
            log_cb = self._make_op_log_cb(op)
            try:
                self.status.showMessage(f"Operation {op} started", 3000)
            except Exception:
                pass
            return worker_identify_all(
                self._last_base, args, log_cb, self._get_list_files_fn()
            )

        def _done(res):
            if hasattr(res, "results"):
                self.log_msg(res.text)
                self._last_verify_results = res.results
                self.on_verification_filter_changed()
                # Sincronizar dados após identificar todos
                self._sync_after_verification()
            else:
                self.log_msg(str(res))
            self._set_ui_enabled(True)

        self._set_ui_enabled(False)
        self._run_in_background(_work, _done)

    def on_update_dats(self):
        if not self._last_base:
            self.log_msg(MSG_SELECT_BASE)
            return

        dats_dir = self._last_base / "dats"
        if not dats_dir.exists():
            self.log_msg(f"Creating DATs directory at {dats_dir}")
            dats_dir.mkdir(parents=True, exist_ok=True)

        # Immediate feedback
        self.log_msg("Initializing DAT update process...")
        self.progress_hook(0.0, "Connecting to GitHub...")
        self._set_ui_enabled(False)

        def _work():
            import concurrent.futures

            downloader = DatDownloader(dats_dir)

            # Phase 1: Listing
            self.progress_hook(0.0, "Fetching No-Intro file list...")
            ni_files = downloader.list_available_dats("no-intro")

            self.progress_hook(0.0, "Fetching Redump file list...")
            rd_files = downloader.list_available_dats("redump")

            total_files = len(ni_files) + len(rd_files)
            if total_files == 0:
                return "No DAT files found to download."

            self.log_msg(
                f"Found {len(ni_files)} No-Intro and {len(rd_files)} Redump DATs. "
                "Starting download..."
            )

            # Phase 2: Downloading
            completed = 0
            success = 0

            def _download_task(source, filename):
                return downloader.download_dat(source, filename)

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                # Submit No-Intro
                for f in ni_files:
                    futures.append(executor.submit(_download_task, "no-intro", f))
                # Submit Redump
                for f in rd_files:
                    futures.append(executor.submit(_download_task, "redump", f))

                for future in concurrent.futures.as_completed(futures):
                    completed += 1
                    percent = completed / total_files

                    try:
                        res = future.result()
                        if res:
                            success += 1
                    except Exception:
                        pass

                    msg = (
                        f"Downloading: {completed}/{total_files} "
                        f"({(percent * 100):.1f}%)"
                    )
                    self.progress_hook(percent, msg)

            return f"Update complete. Downloaded {success}/{total_files} DATs."

        def _done(res):
            self.log_msg(str(res))
            self._set_ui_enabled(True)
            self.progress_hook(1.0, "DAT update complete")

        self._run_in_background(_work, _done)

    def _setup_log_context_menu(self):
        """Setup context menu for the log widget."""
        try:
            self.log.setContextMenuPolicy(
                self._Qt_enum.ContextMenuPolicy.CustomContextMenu
            )
            self.log.customContextMenuRequested.connect(self._on_log_context_menu)
        except Exception:
            pass

    def _on_log_context_menu(self, position):
        menu = self._qtwidgets.QMenu()

        act_clear = menu.addAction("Clear Log")
        act_copy = menu.addAction("Copy All")

        action = menu.exec(self.log.mapToGlobal(position))

        if action == act_clear:
            self.log.clear()
        elif action == act_copy:
            self.log.selectAll()
            self.log.copy()
            # Deselect after copy
            cursor = self.log.textCursor()
            cursor.clearSelection()
            self.log.setTextCursor(cursor)
