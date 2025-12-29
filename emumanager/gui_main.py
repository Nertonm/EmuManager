"""MainWindow component for EmuManager GUI.

This module contains the MainWindow class and related UI helpers. It is
GUI-library-agnostic in the sense that callers should import the Qt classes
from the binding they prefer and pass them when constructing the window.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, Callable, Optional

from emumanager.controllers.gallery import GalleryController
from emumanager.controllers.tools import ToolsController
from emumanager.logging_cfg import get_logger, setup_gui_logging
from emumanager.verification.hasher import calculate_hashes
from emumanager.workers.distributor import worker_distribute_root
from .architect import get_roms_dir

from .gui_ui import Ui_MainWindow
from .gui_covers import CoverDownloader
from .gui_workers import (
    worker_distribute_root,
    worker_hash_verify,
    worker_identify_single_file,
    worker_organize,
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
    """A minimal abstraction over a Qt MainWindow used by the package.

    This class expects the QtWidgets module to be available in the global
    namespace of the caller (i.e., the module that instantiates it).
    """

    def __init__(self, qtwidgets: Any, manager_module: Any):
        self._qtwidgets = qtwidgets
        self._manager = manager_module
        self.ui = Ui_MainWindow()

        # Create widgets (use local alias to the qt binding)
        qt = self._qtwidgets
        # Common literals
        self._dlg_select_base_title = "Select base directory"

        # Attempt to locate the QtCore module corresponding to the passed
        # QtWidgets binding (works for PyQt6 or PySide6). Also prepare a small
        # thread pool used for background tasks.
        try:
            import importlib

            try:
                self._qtcore = importlib.import_module("PyQt6.QtCore")
                self._qtgui = importlib.import_module("PyQt6.QtGui")
            except Exception:
                self._qtcore = importlib.import_module("PySide6.QtCore")
                self._qtgui = importlib.import_module("PySide6.QtGui")
        except Exception:
            self._qtcore = None
            self._qtgui = None

        # Executor for background tasks (small pool)
        try:
            import concurrent.futures

            self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        except Exception:
            self._executor = None

        # UI state helpers
        self._active_timer = None
        self._active_future = None
        self._cancel_event = threading.Event()
        self._settings = None
        self._last_base = None
        self._env = {}  # Cache for environment tools/paths
        self.window = qt.QMainWindow()

        # Setup UI
        self.ui.setupUi(self.window, qt)

        # Setup close handler
        self._original_close_event = self.window.closeEvent
        self.window.closeEvent = self._on_close_event

        # Alias common widgets for convenience and compatibility
        self.log = self.ui.log
        self.status = self.ui.statusbar
        self.rom_list = self.ui.rom_list
        self.sys_list = self.ui.sys_list
        self.cover_label = self.ui.cover_label

        # Alias settings widgets
        self.chk_dry_run = self.ui.chk_dry_run
        self.spin_level = self.ui.spin_level
        self.combo_profile = self.ui.combo_profile
        self.chk_rm_originals = self.ui.chk_rm_originals
        self.chk_quarantine = self.ui.chk_quarantine
        self.chk_deep_verify = self.ui.chk_deep_verify
        self.chk_recursive = self.ui.chk_recursive
        self.chk_process_selected = self.ui.chk_process_selected
        self.chk_standardize_names = self.ui.chk_standardize_names

        if self._qtgui:
            self.ui.apply_dark_theme(qt, self._qtgui, self.window)

        # Setup thread-safe logging signal
        if self._qtcore:
            # Define a QObject to hold the signal
            class LogSignaler(self._qtcore.QObject):
                # Try both PyQt6 and PySide6 signal names
                if hasattr(self._qtcore, "pyqtSignal"):
                    log_signal = self._qtcore.pyqtSignal(str)
                    progress_signal = self._qtcore.pyqtSignal(float, str)
                else:
                    log_signal = self._qtcore.Signal(str)
                    progress_signal = self._qtcore.Signal(float, str)
                
                def emit_log(self, msg, level):
                    # We can optionally use level to colorize, but for now just emit msg
                    self.log_signal.emit(msg)

            self._signaler = LogSignaler()
            self._signaler.log_signal.connect(self._log_msg_slot)
            self._signaler.progress_signal.connect(self._progress_slot)
            
            # Configure standard logging to use this signaler
            setup_gui_logging(self._signaler)

        else:
            self._signaler = None

        # Initialize logger
        self.logger = get_logger("gui")

        # Initialize Controllers
        self.gallery_controller = GalleryController(self)
        self.tools_controller = ToolsController(self)

        # Connect Signals
        self._connect_signals()

        # Initialize settings if possible
        if self._qtcore:
            self._settings = self._qtcore.QSettings("EmuManager", "Manager")
            self._load_settings()

        # Resolve Qt namespace for enums
        self._Qt_enum = None
        if self._qtcore:
            try:
                self._Qt_enum = self._qtcore.Qt
            except AttributeError:
                pass

        # Enhance UI: toolbar and context menus
        try:
            self._setup_toolbar()
            self._setup_menubar()
            self._setup_rom_context_menu()
            self._setup_verification_context_menu()
        except Exception:
            pass

    def _connect_signals(self):
        # Dashboard Tab
        if hasattr(self.ui, "btn_quick_organize"):
            self.ui.btn_quick_organize.clicked.connect(self.on_organize_all)
        if hasattr(self.ui, "btn_quick_verify"):
            self.ui.btn_quick_verify.clicked.connect(self.on_verify_all)
        if hasattr(self.ui, "btn_quick_update"):
            self.ui.btn_quick_update.clicked.connect(self.on_list)

        # Library Tab
        self.ui.btn_open_lib.clicked.connect(self.on_open_library)
        self.ui.btn_init.clicked.connect(self.on_init)
        self.ui.btn_list.clicked.connect(self.on_list)
        self.ui.btn_add.clicked.connect(self.on_add)
        self.ui.btn_clear.clicked.connect(self.on_clear_log)
        # Connect selection change for covers
        self.ui.rom_list.currentItemChanged.connect(self._on_rom_selection_changed)
        # Filter box
        if hasattr(self.ui, "edit_filter"):
            self.ui.edit_filter.textChanged.connect(self._on_filter_text)
        if hasattr(self.ui, "btn_clear_filter"):
            self.ui.btn_clear_filter.clicked.connect(
                lambda: self.ui.edit_filter.setText("")
            )
        self.ui.sys_list.itemClicked.connect(self._on_system_selected)
        self.ui.rom_list.itemDoubleClicked.connect(self._on_rom_double_clicked)

        # Cancel button
        self.ui.btn_cancel.clicked.connect(self.on_cancel_requested)

        self.ui.btn_dolphin_convert.clicked.connect(self.on_dolphin_convert)
        self.ui.btn_dolphin_verify.clicked.connect(self.on_dolphin_verify)

        # Tools Tab - 3DS
        self.ui.btn_n3ds_organize.clicked.connect(self.on_n3ds_organize)
        self.ui.btn_n3ds_verify.clicked.connect(self.on_n3ds_verify)
        self.ui.btn_n3ds_compress.clicked.connect(self.on_n3ds_compress)
        self.ui.btn_n3ds_decompress.clicked.connect(self.on_n3ds_decompress)
        self.ui.btn_n3ds_convert_cia.clicked.connect(self.on_n3ds_convert_cia)

        # Tools Tab - Sega
        if hasattr(self.ui, "btn_sega_convert"):
            self.ui.btn_sega_convert.clicked.connect(self.on_sega_convert)
        if hasattr(self.ui, "btn_sega_verify"):
            self.ui.btn_sega_verify.clicked.connect(self.on_generic_verify_click)
        if hasattr(self.ui, "btn_sega_organize"):
            self.ui.btn_sega_organize.clicked.connect(self.on_generic_organize_click)

        # Tools Tab - Microsoft
        if hasattr(self.ui, "btn_ms_verify"):
            self.ui.btn_ms_verify.clicked.connect(self.on_generic_verify_click)
        if hasattr(self.ui, "btn_ms_organize"):
            self.ui.btn_ms_organize.clicked.connect(self.on_generic_organize_click)

        # Tools Tab - Nintendo Legacy
        if hasattr(self.ui, "btn_nint_compress"):
            self.ui.btn_nint_compress.clicked.connect(self.on_nint_compress)
        if hasattr(self.ui, "btn_nint_verify"):
            self.ui.btn_nint_verify.clicked.connect(self.on_generic_verify_click)
        if hasattr(self.ui, "btn_nint_organize"):
            self.ui.btn_nint_organize.clicked.connect(self.on_generic_organize_click)

        # Tools Tab - General
        self.ui.btn_clean_junk.clicked.connect(self.on_clean_junk)

        # Verification Tab
        self.ui.btn_select_dat.clicked.connect(self.on_select_dat)
        self.ui.btn_verify_dat.clicked.connect(self.on_verify_dat)
        if hasattr(self.ui, "combo_verif_filter"):
            self.ui.combo_verif_filter.currentTextChanged.connect(
                self.on_verification_filter_changed
            )
        if hasattr(self.ui, "btn_export_csv"):
            self.ui.btn_export_csv.clicked.connect(self.on_export_verification_csv)
        # Key handling on ROM list (Enter/Return to Compress)
        try:
            self._install_rom_key_filter()
        except Exception:
            pass
        if hasattr(self.ui, "table_results"):
            self.ui.table_results.itemDoubleClicked.connect(
                self._on_verification_item_dblclick
            )
        if hasattr(self.ui, "combo_verif_filter"):
            self.ui.combo_verif_filter.currentTextChanged.connect(
                self.on_verification_filter_changed
            )
        if hasattr(self.ui, "btn_export_csv"):
            self.ui.btn_export_csv.clicked.connect(self.on_export_verification_csv)

    def show(self):
        self.window.show()

    def _log_msg_slot(self, text: str):
        # Just append to the log window. 
        # The text is already formatted by the logging handler if it came from there.
        self.log.append(text)
        # Show brief status in the status bar
        try:
            self.status.showMessage(text, 5000)
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

            # Update progress bar
            try:
                if not self.ui.progress_bar.isVisible():
                    self.ui.progress_bar.setVisible(True)
                self.ui.progress_bar.setValue(int(p * 100))
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
        self.act_organize.triggered.connect(self.on_organize)

        self.act_health = qt.QAction("Health Check", self.window)
        self.act_health.triggered.connect(self.on_health_check)

        self.act_switch_compress = qt.QAction("Switch: Compress", self.window)
        self.act_switch_compress.triggered.connect(self.on_switch_compress)

        self.act_switch_decompress = qt.QAction("Switch: Decompress", self.window)
        self.act_switch_decompress.triggered.connect(self.on_switch_decompress)

        self.act_ps2_convert = qt.QAction("PS2: Convert to CHD", self.window)
        self.act_ps2_convert.triggered.connect(self.on_ps2_convert)

        self.act_psx_convert = qt.QAction("PS1: Convert to CHD", self.window)
        self.act_psx_convert.triggered.connect(self.on_psx_convert)

        self.act_ps2_verify = qt.QAction("PS2: Verify", self.window)
        self.act_ps2_verify.triggered.connect(self.on_ps2_verify)

        self.act_psx_verify = qt.QAction("PS1: Verify", self.window)
        self.act_psx_verify.triggered.connect(self.on_psx_verify)

        self.act_ps2_organize = qt.QAction("PS2: Organize", self.window)
        self.act_ps2_organize.triggered.connect(self.on_ps2_organize)

        self.act_psx_organize = qt.QAction("PS1: Organize", self.window)
        self.act_psx_organize.triggered.connect(self.on_psx_organize)

        self.act_ps3_verify = qt.QAction("PS3: Verify", self.window)
        self.act_ps3_verify.triggered.connect(self.on_ps3_verify)

        self.act_ps3_organize = qt.QAction("PS3: Organize", self.window)
        self.act_ps3_organize.triggered.connect(self.on_ps3_organize)

        self.act_psp_verify = qt.QAction("PSP: Verify", self.window)
        self.act_psp_verify.triggered.connect(self.on_psp_verify)

        self.act_psp_organize = qt.QAction("PSP: Organize", self.window)
        self.act_psp_organize.triggered.connect(self.on_psp_organize)

        self.act_psp_compress = qt.QAction("PSP: Compress ISO->CSO", self.window)
        self.act_psp_compress.triggered.connect(self.on_psp_compress)

        self.act_n3ds_verify = qt.QAction("3DS: Verify", self.window)
        self.act_n3ds_verify.triggered.connect(self.on_n3ds_verify)

        self.act_n3ds_organize = qt.QAction("3DS: Organize", self.window)
        self.act_n3ds_organize.triggered.connect(self.on_n3ds_organize)

        self.act_dol_convert = qt.QAction("GC/Wii: Convert to RVZ", self.window)
        self.act_dol_convert.triggered.connect(self.on_dolphin_convert)

        self.act_dol_verify = qt.QAction("GC/Wii: Verify", self.window)
        self.act_dol_verify.triggered.connect(self.on_dolphin_verify)

        self.act_dol_organize = qt.QAction("GC/Wii: Organize", self.window)
        self.act_dol_organize.triggered.connect(self.on_dolphin_organize)

        self.act_clean_junk = qt.QAction("Clean Junk Files", self.window)
        self.act_clean_junk.triggered.connect(self.on_clean_junk)

        self.act_export_csv = qt.QAction("Export Verification CSV", self.window)
        self.act_export_csv.triggered.connect(self.on_export_verification_csv)

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
        try:
            import subprocess

            if path.is_dir():
                subprocess.run(["xdg-open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path.parent)], check=False)
        except Exception:
            self.log_msg(f"Failed to open location: {path}")

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
                self._last_base = Path(str(last))
                try:
                    self.ui.lbl_library.setText(str(self._last_base))
                    self.ui.lbl_library.setStyleSheet(
                        "font-weight: bold; color: #3daee9;"
                    )
                except Exception:
                    pass
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
            self.ui.btn_open_library.setEnabled(enabled)

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
            if (
                enabled
                and hasattr(self, "_current_dat_path")
                and self._current_dat_path
            ):
                self.ui.btn_verify_dat.setEnabled(True)
            else:
                self.ui.btn_verify_dat.setEnabled(False)

            # Compression buttons
            self.ui.btn_compress.setEnabled(enabled)
            self.ui.btn_recompress.setEnabled(enabled)
            self.ui.btn_decompress.setEnabled(enabled)

            # Cancel button logic is inverse
            self.ui.btn_cancel.setEnabled(not enabled)

            # Show/Hide progress bar
            self.ui.progress_bar.setVisible(not enabled)
            if enabled:
                self.ui.progress_bar.setValue(0)
                self.status.clearMessage()
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
        qt = self._qtwidgets
        base = self._last_base
        if not base:
            self.log_msg(MSG_SELECT_BASE)
            return

        try:
            yes_btn = qt.QMessageBox.StandardButton.Yes
            no_btn = qt.QMessageBox.StandardButton.No
        except AttributeError:
            yes_btn = qt.QMessageBox.Yes
            no_btn = qt.QMessageBox.No

        dry = qt.QMessageBox.question(
            self.window,
            "Dry-run?",
            "Run in dry-run (no changes)?",
            yes_btn | no_btn,
        )
        dry_run = dry == yes_btn
        self.log_msg(f"Running init on: {base} (dry={dry_run})")

        def _work():
            return self._manager.cmd_init(base, dry_run=dry_run)

        def _done(result):
            if isinstance(result, Exception):
                self.log_msg(f"Init error: {result}")
            else:
                try:
                    self.log_msg(f"Finished init, rc={result}")
                except Exception:
                    pass
            self._set_ui_enabled(True)

        self._set_ui_enabled(False)
        self._run_in_background(_work, _done)

    def on_list(self):
        base = self._last_base
        if not base:
            self.log_msg(MSG_SELECT_BASE)
            return
        systems = self._manager.cmd_list_systems(base)
        self._refresh_system_list_ui(systems)
        self._log_systems(systems)
        self._update_dashboard_stats(systems)

    def _update_dashboard_stats(self, systems=None):
        try:
            if systems is None:
                if self._last_base:
                    systems = self._manager.cmd_list_systems(self._last_base)
                else:
                    systems = []

            if hasattr(self.ui, "lbl_systems_count"):
                self.ui.lbl_systems_count.setText(f"Systems Configured: {len(systems)}")

            # Calculate total files (approximate)
            total_files = 0
            roms_root = self._manager.get_roms_dir(self._last_base)
            for sys_name in systems:
                try:
                    p = roms_root / sys_name
                    # Count files recursively
                    total_files += sum(1 for _ in p.rglob("*") if _.is_file())
                except Exception:
                    logging.warning(f"Failed to count files for {sys_name}", exc_info=True)

            if hasattr(self.ui, "lbl_total_roms"):
                self.ui.lbl_total_roms.setText(f"Total Files: {total_files}")
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

    def on_add(self):
        base = self._last_base
        if not base:
            self.log_msg(MSG_SELECT_BASE)
            return

        src = self._select_file_dialog("Select ROM file")
        if not src:
            return

        system = self._select_system_dialog(src, base)
        if not system:
            self.log_msg("Add ROM cancelled: No system selected.")
            return

        move = self._ask_yes_no("Move file?", "Move file instead of copy?")
        dry_run = self._ask_yes_no("Dry-run?", "Run in dry-run (no changes)?")

        def _work_add():
            return self._manager.cmd_add_rom(
                src, base, system=system, move=move, dry_run=dry_run
            )

        def _done_add(result):
            if isinstance(result, Exception):
                self.log_msg(f"Add ROM error: {result}")
            else:
                try:
                    self.log_msg(f"Added ROM -> {result}")
                    # Refresh list to show new file
                    self.on_list()
                    # Update dashboard stats
                    self._update_dashboard_stats()
                except Exception:
                    pass
            self._set_ui_enabled(True)

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
        guessed = self._manager.guess_system_for_file(src)
        systems = self._manager.cmd_list_systems(base)

        # If no systems found (empty library), populate with known systems
        if not systems:
            from emumanager.config import EXT_TO_SYSTEM
            systems = sorted(list(set(EXT_TO_SYSTEM.values())))

        items = sorted(systems)
        idx = 0
        if guessed:
            if guessed not in items:
                items.insert(0, guessed)
            idx = items.index(guessed)

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
            system = item.text()
            self._populate_roms(system)
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
            self.on_compress_selected()
        except Exception:
            pass

    def _list_files_recursive(self, root: Path) -> list[Path]:
        """List files recursively, excluding hidden files and directories."""
        files = []
        if not root.exists():
            return files

        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.name.startswith("."):
                continue

            try:
                rel = p.relative_to(root)
                if any(part.startswith(".") for part in rel.parts):
                    continue
                files.append(p)
            except ValueError:
                continue

        files.sort(key=lambda p: str(p).lower())
        return files

    def _list_dirs_recursive(self, root: Path) -> list[Path]:
        """List directories recursively, excluding hidden ones."""
        dirs = []
        if not root.exists():
            return dirs

        for p in root.rglob("*"):
            if not p.is_dir():
                continue
            if p.name.startswith("."):
                continue

            try:
                rel = p.relative_to(root)
                if any(part.startswith(".") for part in rel.parts):
                    continue
                dirs.append(p)
            except ValueError:
                continue

        # Sort reverse to ensure we process children before parents
        dirs.sort(key=lambda p: str(p), reverse=True)
        return dirs

    def _list_files_flat(self, root: Path) -> list[Path]:
        """List files in the directory (non-recursive), excluding hidden files."""
        files = []
        if not root.exists():
            return files

        for p in root.iterdir():
            if not p.is_file():
                continue
            if p.name.startswith("."):
                continue
            files.append(p)
        return files

    def _get_list_files_fn(self):
        """Returns the appropriate list_files function based on settings."""
        if self.chk_process_selected.isChecked():
            return self._list_files_selected
        elif self.chk_recursive.isChecked():
            return self._list_files_recursive
        else:
            return self._list_files_flat

    def _populate_roms(self, system: str):
        if not self._last_base:
            return
        try:
            # Use manager's logic to find roms dir
            roms_root = self._manager.get_roms_dir(self._last_base)
            roms_dir = roms_root / system

            self.log_msg(f"Listing ROMs for {system} in {roms_dir}")

            files = []
            if roms_dir.exists():
                # Always list recursively for the UI so users can see organized games
                # regardless of the "Recursive" checkbox state
                # (which controls processing).
                full_files = self._list_files_recursive(roms_dir)
                files = [p.relative_to(roms_dir) for p in full_files]
                # Store for filtering
                self._current_roms = [str(p) for p in files]
                self.log_msg(f"Found {len(files)} files.")
            else:
                self.log_msg(f"Directory not found: {roms_dir}")

            if self.rom_list is not None:
                self.rom_list.clear()
                for f in files:
                    self.rom_list.addItem(str(f))
        except Exception as e:
            self.log_msg(f"Error listing ROMs: {e}")
            if hasattr(self, "logger"):
                self.logger.exception("Error listing ROMs")

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

        if not hasattr(self, "_current_dat_path") or not self._current_dat_path:
            self.log_msg("Please select a DAT file first.")
            return

        args = self._get_common_args()
        args.dat_path = self._current_dat_path

        # Clear previous results
        self.ui.table_results.setRowCount(0)

        def _work():
            return worker_hash_verify(
                self._last_base, args, self.log_msg, self._get_list_files_fn()
            )

        def _done(res):
            if hasattr(res, "results"):
                self.log_msg(res.text)
                # Store for filtering/export
                self._last_verify_results = res.results
                self.on_verification_filter_changed()
            else:
                self.log_msg(str(res))
            self._set_ui_enabled(True)

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
        self.ui.table_results.setItem(row_idx, 3, qt.QTableWidgetItem(result.crc or ""))
        self.ui.table_results.setItem(
            row_idx, 4, qt.QTableWidgetItem(result.sha1 or "")
        )
        # New columns: MD5 and SHA256 (if deep verify)
        try:
            self.ui.table_results.setItem(
                row_idx,
                5,
                qt.QTableWidgetItem(getattr(result, "md5", "") or ""),
            )
            self.ui.table_results.setItem(
                row_idx,
                6,
                qt.QTableWidgetItem(getattr(result, "sha256", "") or ""),
            )
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
            if txt in ("VERIFIED", "UNKNOWN"):
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
            if txt in ("VERIFIED", "UNKNOWN"):
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
        """Organize all supported systems sequentially."""
        if not self._last_base:
            self.log_msg(MSG_SELECT_BASE)
            return

        self._ensure_env(self._last_base)
        args = self._get_common_args()
        args.organize = True

        self.log_msg("Starting batch organization...")

        def _work():
            results = []

            # 1. Distribute root files
            # If _last_base is the 'roms' folder, we scan it directly.
            # If _last_base is the project root, we might need to append 'roms'.
            # Based on user log, _last_base seems to be the roms folder.
            # But let's be safe: check if 'roms' subdir exists.

            target_root = self._last_base
            if (self._last_base / "roms").exists():
                target_root = self._last_base / "roms"

            self.log_msg(f"Distributing files in {target_root}...")
            dist_stats = worker_distribute_root(
                target_root,
                self.log_msg,
                progress_cb=getattr(self, "progress_hook", None),
                cancel_event=self._cancel_event
            )
            results.append(f"Distribution: {dist_stats}")

            # 2. Run Switch Organizer
            # We want to organize the 'switch' folder inside target_root
            switch_dir = target_root / "switch"
            if switch_dir.exists():
                self.log_msg(f"Organizing Switch folder: {switch_dir}...")

                # Create a copy of env with updated ROMS_DIR
                switch_env = self._env.copy()
                switch_env["ROMS_DIR"] = switch_dir
                switch_env["CSV_FILE"] = switch_dir / "biblioteca_switch.csv"
                switch_env["DUPE_DIR"] = switch_dir / "_DUPLICATES"

                switch_res = worker_organize(
                    switch_dir,
                    switch_env,
                    args,
                    self.log_msg,
                    self._list_files_flat,
                    progress_cb=getattr(self, "progress_hook", None),
                )
                results.append(f"Switch: {switch_res}")
            else:
                results.append("Switch: Skipped (folder not found)")

            return "\n".join(results)

        def _done(res):
            if isinstance(res, Exception):
                self.log_msg(f"Batch Organization error: {res}")
            else:
                self.log_msg(str(res))
            self._set_ui_enabled(True)
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
            roms_root = self._manager.get_roms_dir(self._last_base)

            files_to_delete = []
            for item in sel_items:
                filepath = roms_root / system / item.text()
                if filepath.exists():
                    files_to_delete.append(filepath)

            if not files_to_delete:
                return

            msg = f"Are you sure you want to delete {len(files_to_delete)} files?"
            if not self._ask_yes_no("Confirm Delete", msg):
                return

            count = 0
            for fp in files_to_delete:
                try:
                    fp.unlink()
                    count += 1
                    self.log_msg(f"Deleted: {fp.name}")
                except Exception as e:
                    self.log_msg(f"Failed to delete {fp.name}: {e}")

            if count > 0:
                self._populate_roms(system)
                self._update_dashboard_stats()

        except Exception as e:
            self.log_msg(f"Error deleting files: {e}")

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
            roms_root = self._manager.get_roms_dir(self._last_base)
            filepath = roms_root / system / rom_name

            if not filepath.exists():
                self.log_msg(f"File not found: {filepath}")
                return

            self.log_msg(f"Calculating hashes for {rom_name}...")

            def _work():
                return calculate_hashes(filepath)

            def _done(res):
                if not res:
                    self.log_msg(f"Failed to calculate hashes for {rom_name}")
                else:
                    self.log_msg(f"Hashes for {rom_name}:")
                    for algo, val in res.items():
                        self.log_msg(f"  {algo.upper()}: {val}")
                self._set_ui_enabled(True)

            self._set_ui_enabled(False)
            self._run_in_background(_work, _done)

        except Exception as e:
            self.log_msg(f"Error verifying file: {e}")


    def _on_rom_selection_changed(self, current, previous):
        if not current:
            self.cover_label.clear()
            self.cover_label.setText("No ROM selected")
            return

        # Get system
        if not self.sys_list.currentItem():
            return
        system = self.sys_list.currentItem().text()

        # Get file path
        if not self._last_base:
            return
            
        base_roms_dir = get_roms_dir(Path(self._last_base))
        system_dir = base_roms_dir / system
        
        rom_rel_path = current.text()
        full_path = system_dir / rom_rel_path
        
        # Start cover download/extraction
        # Use a cache dir for covers
        cache_dir = Path(self._last_base) / ".covers"
        cache_dir.mkdir(exist_ok=True)
        
        self.log_msg(f"Fetching cover for {rom_rel_path} (System: {system})...")
        
        # Guess region from filename
        region = None
        if "(USA)" in rom_rel_path or "(US)" in rom_rel_path:
            region = "US"
        elif "(Europe)" in rom_rel_path or "(EU)" in rom_rel_path:
            region = "EN"
        elif "(Japan)" in rom_rel_path or "(JP)" in rom_rel_path:
            region = "JA"
            
        downloader = CoverDownloader(system, None, region, str(cache_dir), str(full_path))
        
        # Force QueuedConnection to ensure UI updates happen in the main thread
        conn_type = self._Qt_enum.ConnectionType.QueuedConnection if self._Qt_enum and hasattr(self._Qt_enum, "ConnectionType") else self._qtcore.Qt.QueuedConnection
        
        downloader.signals.finished.connect(self._update_cover_image, conn_type)
        downloader.signals.log.connect(self.log_msg, conn_type)
        
        # Run in thread pool
        if self._qtcore:
            self._qtcore.QThreadPool.globalInstance().start(downloader)

    def _update_cover_image(self, image_path):
        import threading
        self.log_msg(f"Update cover called in thread: {threading.current_thread().name}")
        
        if not image_path or not Path(image_path).exists():
            self.cover_label.setText("No Cover Found")
            return
            
        # Check file size
        try:
            size = Path(image_path).stat().st_size
            if size == 0:
                self.log_msg(f"Error: Image file is empty: {image_path}")
                self.cover_label.setText("Empty Image")
                return
        except Exception:
            pass

        self.log_msg(f"Displaying cover: {image_path}")
        pixmap = self._qtgui.QPixmap(image_path)
        
        if not pixmap.isNull():
            self.log_msg(f"Loaded pixmap: {pixmap.width()}x{pixmap.height()}")
            self.cover_label.setPixmap(pixmap)
            self.cover_label.setVisible(True)
        else:
            self.log_msg(f"Failed to load pixmap from {image_path}")
            self.cover_label.setText("Invalid Image")

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
            
        system = self.sys_list.currentItem().text() if self.sys_list.currentItem() else ""
        if not system:
            self.log_msg(MSG_NO_SYSTEM)
            return

        base_roms_dir = get_roms_dir(Path(self._last_base))
        rom_rel_path = sel.text()
        full_path = base_roms_dir / system / rom_rel_path
        
        if not full_path.exists():
            self.log_msg(f"File not found: {full_path}")
            return

        # Ask user for DAT file
        dat_path, _ = self._qtwidgets.QFileDialog.getOpenFileName(
            self.window, "Select DAT File", str(self._last_base), "DAT Files (*.dat *.xml)"
        )
        
        if not dat_path:
            return
            
        self.log_msg(f"Identifying {full_path.name} using {Path(dat_path).name}...")
        
        def _work():
            return worker_identify_single_file(
                full_path, Path(dat_path), self.log_msg, self._progress_slot
            )
            
        def _done(res):
            self.log_msg(str(res))
            self._qtwidgets.QMessageBox.information(self.window, "Identification Result", str(res))
            
        self._run_in_background(_work, _done)


