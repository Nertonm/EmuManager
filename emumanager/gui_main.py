"""MainWindow component for EmuManager GUI.

Redesenhado para usar nativamente o Core Orchestrator.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Callable, Optional

from emumanager.application import LibraryInsightsService
from emumanager.controllers.duplicates import DuplicatesController
from emumanager.controllers.gallery import GalleryController
from emumanager.controllers.tools import ToolsController
from emumanager.library import LibraryDB
from emumanager.logging_cfg import get_logger, setup_gui_logging
from emumanager.verification.dat_downloader import DatDownloader
from emumanager.verification.hasher import calculate_hashes

from .gui_covers import CoverDownloader
from .gui_main_library import MainWindowLibraryMixin
from .gui_main_roms import MainWindowRomsMixin
from .gui_main_settings import MainWindowSettingsMixin
from .gui_main_verification import MainWindowVerificationMixin
from .gui_ui import MainWindowUI
from .gui_workers import (
    worker_hash_verify,
    worker_scan_library,
    worker_identify_single_file,
    worker_identify_all
)

# Constants
MSG_NSZ_MISSING = "Error: 'nsz' tool not found in environment."
LOG_WARN = "WARN: "
LOG_ERROR = "ERROR: "
LOG_EXCEPTION = "EXCEPTION: "
LAST_SYSTEM_KEY = "ui/last_system"
COMMON_UI_BUTTONS = (
    "btn_init",
    "btn_list",
    "btn_add",
    "btn_clear",
    "btn_open_lib",
    "btn_organize",
    "btn_health",
    "btn_switch_compress",
    "btn_switch_decompress",
    "btn_ps2_convert",
    "btn_ps2_verify",
    "btn_ps2_organize",
    "btn_ps3_verify",
    "btn_ps3_organize",
    "btn_psp_verify",
    "btn_psp_organize",
    "btn_dolphin_convert",
    "btn_dolphin_verify",
    "btn_clean_junk",
    "btn_select_dat",
    "btn_compress",
    "btn_recompress",
    "btn_decompress",
)


class MainWindowBase(
    MainWindowSettingsMixin,
    MainWindowVerificationMixin,
    MainWindowLibraryMixin,
    MainWindowRomsMixin,
):
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
        self._current_rom_rows = []
        self.library_db = getattr(self._orchestrator, "db", None) or LibraryDB()
        self.library_insights = LibraryInsightsService(self.library_db)
        self._Qt_enum = getattr(self._qtcore, "Qt", None) if self._qtcore else None

    def _rebind_library_runtime(self, base_dir: Path) -> None:
        """Realign orchestrator, database, and read-model services to the active base."""
        self._last_base = base_dir

        try:
            from emumanager.manager import get_orchestrator

            self._orchestrator = get_orchestrator(base_dir)
            self.library_db = self._orchestrator.db
        except Exception as exc:
            logging.debug("Failed to rebuild orchestrator for %s: %s", base_dir, exc)
            try:
                if hasattr(self._orchestrator, "session"):
                    self._orchestrator.session.base_path = base_dir
            except Exception:
                pass
            self.library_db = LibraryDB(base_dir / "library.db")

        self.library_insights.set_database(self.library_db)

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

    def _run_hash_verify_worker(
        self, target_path: Path, args: Any, log_cb: Callable[[str], None]
    ):
        return worker_hash_verify(target_path, args, log_cb, self._get_list_files_fn())

    def _run_scan_worker(
        self,
        base: Path,
        log_cb: Callable[[str], None],
        progress_cb: Optional[Callable] = None,
    ):
        return worker_scan_library(base, log_cb, progress_cb, self._cancel_event)

    def _run_identify_single_worker(
        self,
        full_path: Path,
        dat_path: Path,
        log_cb: Callable[[str], None],
        progress_cb: Optional[Callable] = None,
    ):
        return worker_identify_single_file(full_path, dat_path, log_cb, progress_cb)

    def _run_identify_all_worker(self, args: Any, log_cb: Callable[[str], None]):
        return worker_identify_all(
            self._last_base, args, log_cb, self._get_list_files_fn()
        )

    def _create_dat_downloader(self, dats_dir: Path):
        return DatDownloader(dats_dir)

    def _calculate_hashes_for_path(
        self, path: Path, algorithms: tuple[str, ...]
    ) -> dict[str, str]:
        return calculate_hashes(path, algorithms=algorithms)

    def _create_cover_downloader(
        self, system: str, region: Optional[str], cache_dir: Path, full_path: Path
    ):
        return CoverDownloader(system, None, region, str(cache_dir), str(full_path))

    def _set_ui_enabled(self, enabled: bool):
        try:
            for attr_name in COMMON_UI_BUTTONS:
                widget = getattr(self.ui, attr_name, None)
                if widget is not None:
                    widget.setEnabled(enabled)

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
