from __future__ import annotations
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from emumanager.gui_workers import (
    worker_clean_junk,
    worker_compress_single,
    worker_decompress_single,
    worker_dolphin_convert,
    worker_dolphin_decompress_single,
    worker_dolphin_organize,
    worker_dolphin_recompress_single,
    worker_dolphin_verify,
    worker_health_check,
    worker_n3ds_organize,
    worker_n3ds_verify,
    worker_n3ds_compress,
    worker_n3ds_decompress,
    worker_n3ds_convert_cia,
    worker_n3ds_decrypt,
    worker_organize,
    worker_ps2_convert,
    worker_ps2_organize,
    worker_ps2_verify,
    worker_ps3_organize,
    worker_ps3_verify,
    worker_psp_compress,
    worker_psp_organize,
    worker_psp_verify,
    worker_psx_convert,
    worker_psx_organize,
    worker_psx_verify,
    worker_recompress_single,
    worker_switch_compress,
    worker_switch_decompress,
)

if TYPE_CHECKING:
    from emumanager.gui_main import MainWindowBase

MSG_SELECT_BASE = "Please select a base directory first (Open Library)."

class ToolsController:
    def __init__(self, main_window: MainWindowBase):
        self.mw = main_window
        self.ui = main_window.ui
        self._connect_signals()

    def _connect_signals(self):
        # Switch Actions (Contextual)
        self.ui.btn_compress.clicked.connect(self.on_compress_selected)
        self.ui.btn_recompress.clicked.connect(self.on_recompress_selected)
        self.ui.btn_decompress.clicked.connect(self.on_decompress_selected)
        
        # Tools Tab - Switch
        self.ui.btn_organize.clicked.connect(self.on_organize)
        self.ui.btn_health.clicked.connect(self.on_health_check)
        self.ui.btn_switch_compress.clicked.connect(self.on_switch_compress)
        self.ui.btn_switch_decompress.clicked.connect(self.on_switch_decompress)

        # Tools Tab - PS1
        self.ui.btn_psx_convert.clicked.connect(self.on_psx_convert)
        self.ui.btn_psx_verify.clicked.connect(self.on_psx_verify)
        self.ui.btn_psx_organize.clicked.connect(self.on_psx_organize)

        # Tools Tab - PS2
        self.ui.btn_ps2_convert.clicked.connect(self.on_ps2_convert)
        self.ui.btn_ps2_verify.clicked.connect(self.on_ps2_verify)
        self.ui.btn_ps2_organize.clicked.connect(self.on_ps2_organize)

        # Tools Tab - PS3
        self.ui.btn_ps3_verify.clicked.connect(self.on_ps3_verify)
        self.ui.btn_ps3_organize.clicked.connect(self.on_ps3_organize)

        # Tools Tab - PSP
        self.ui.btn_psp_verify.clicked.connect(self.on_psp_verify)
        self.ui.btn_psp_organize.clicked.connect(self.on_psp_organize)
        self.ui.btn_psp_compress.clicked.connect(self.on_psp_compress)

        # Tools Tab - Dolphin
        self.ui.btn_dolphin_organize.clicked.connect(self.on_dolphin_organize)
        self.ui.btn_dolphin_convert.clicked.connect(self.on_dolphin_convert)
        self.ui.btn_dolphin_verify.clicked.connect(self.on_dolphin_verify)

        # Tools Tab - 3DS
        self.ui.btn_n3ds_organize.clicked.connect(self.on_n3ds_organize)
        self.ui.btn_n3ds_verify.clicked.connect(self.on_n3ds_verify)
        self.ui.btn_n3ds_compress.clicked.connect(self.on_n3ds_compress)
        self.ui.btn_n3ds_decompress.clicked.connect(self.on_n3ds_decompress)
        self.ui.btn_n3ds_convert_cia.clicked.connect(self.on_n3ds_convert_cia)

        # Tools Tab - General
        self.ui.btn_clean_junk.clicked.connect(self.on_clean_junk)

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

    def on_compress_selected(self):
        self._run_single_file_task(worker_compress_single, "Compress")

    def on_recompress_selected(self):
        self._run_single_file_task(worker_recompress_single, "Recompress")

    def on_decompress_selected(self):
        self._run_single_file_task(worker_decompress_single, "Decompress")

    def _run_single_file_task(self, worker_func, label):
        if not self.mw.rom_list:
            return
        item = self.mw.rom_list.currentItem()
        if not item:
            return
        
        # We need to resolve the full path. 
        # MW has logic for this in _on_rom_selection_changed but we can reconstruct it.
        if not self.mw._last_base:
            return
            
        sys_item = self.mw.sys_list.currentItem()
        if not sys_item:
            return
        system = sys_item.text()
        
        rom_rel_path = item.text()
        # Assuming standard structure
        full_path = Path(self.mw._last_base) / "roms" / system / rom_rel_path
        
        if not full_path.exists():
            logging.error(f"File not found: {full_path}")
            return

        logging.info(f"{label}ing {full_path.name}...")
        
        def _work():
            return worker_func(full_path, self.mw.log_msg) # Workers expect a log callback
            
        def _done(res):
            logging.info(str(res))
            self.mw.on_list() # Refresh list
            
        self.mw._run_in_background(_work, _done)

    def on_organize(self):
        self._run_tool_task(worker_organize, "Organize Switch")

    def on_health_check(self):
        self._run_tool_task(worker_health_check, "Health Check")

    def on_switch_compress(self):
        self._run_tool_task(worker_switch_compress, "Compress Switch Library")

    def on_switch_decompress(self):
        self._run_tool_task(worker_switch_decompress, "Decompress Switch Library")

    def on_psx_convert(self):
        self._run_tool_task(worker_psx_convert, "Convert PS1 to CHD")

    def on_psx_verify(self):
        self._run_tool_task(worker_psx_verify, "Verify PS1")

    def on_psx_organize(self):
        self._run_tool_task(worker_psx_organize, "Organize PS1")

    def on_ps2_convert(self):
        self._run_tool_task(worker_ps2_convert, "Convert PS2 to CHD")

    def on_ps2_verify(self):
        self._run_tool_task(worker_ps2_verify, "Verify PS2")

    def on_ps2_organize(self):
        self._run_tool_task(worker_ps2_organize, "Organize PS2")

    def on_ps3_verify(self):
        self._run_tool_task(worker_ps3_verify, "Verify PS3")

    def on_ps3_organize(self):
        self._run_tool_task(worker_ps3_organize, "Organize PS3")

    def on_psp_verify(self):
        self._run_tool_task(worker_psp_verify, "Verify PSP")

    def on_psp_organize(self):
        self._run_tool_task(worker_psp_organize, "Organize PSP")

    def on_psp_compress(self):
        # PSP compress needs extra args (level)
        if not self.mw._last_base:
            logging.warning(MSG_SELECT_BASE)
            return

        args = self.mw._get_common_args()
        args.level = 9
        args.rm_originals = self.ui.chk_rm_originals.isChecked()

        def _work():
            return worker_psp_compress(
                self.mw._last_base, args, self.mw.log_msg, self.mw._get_list_files_fn()
            )

        def _done(res):
            logging.info(str(res))
            self.mw._set_ui_enabled(True)

        self.mw._set_ui_enabled(False)
        self.mw._run_in_background(_work, _done)

    def on_dolphin_organize(self):
        self._run_tool_task(worker_dolphin_organize, "Organize GC/Wii")

    def on_dolphin_convert(self):
        self._run_tool_task(worker_dolphin_convert, "Convert GC/Wii to RVZ")

    def on_dolphin_verify(self):
        self._run_tool_task(worker_dolphin_verify, "Verify GC/Wii")

    def on_n3ds_organize(self):
        self._run_tool_task(worker_n3ds_organize, "Organize 3DS")

    def on_n3ds_verify(self):
        self._run_tool_task(worker_n3ds_verify, "Verify 3DS")

    def on_n3ds_compress(self):
        self._run_tool_task(worker_n3ds_compress, "Compress 3DS")

    def on_n3ds_decompress(self):
        self._run_tool_task(worker_n3ds_decompress, "Decompress 3DS")

    def on_n3ds_convert_cia(self):
        self._run_tool_task(worker_n3ds_convert_cia, "Convert 3DS to CIA")

    def on_clean_junk(self):
        self._run_tool_task(worker_clean_junk, "Clean Junk")

    def _run_tool_task(self, worker_func, label):
        if not self.mw._last_base:
            logging.warning(MSG_SELECT_BASE)
            return

        args = self.mw._get_common_args()

        def _work():
            return worker_func(
                self.mw._last_base, args, self.mw.log_msg, self.mw._get_list_files_fn()
            )

        def _done(res):
            logging.info(str(res))
            self.mw._set_ui_enabled(True)
            self.mw._update_dashboard_stats()

        self.mw._set_ui_enabled(False)
        self.mw._run_in_background(_work, _done)

    def on_generic_verify_click(self):
        """Redirects to the Verification tab."""
        self.ui.tabs.setCurrentWidget(self.ui.tab_verification)
        logging.info("Please select a DAT file to verify your games.")
        self.ui.btn_select_dat.setFocus()
        
    def on_generic_organize_click(self):
        self.mw._qtwidgets.QMessageBox.information(
            self.mw.window, 
            "Feature Not Available", 
            "Automatic organization for this system is not yet implemented.\n"
            "Please use the 'Organize (Rename)' button in the Dashboard for generic renaming."
        )

    def on_sega_convert(self):
        self.mw._qtwidgets.QMessageBox.information(
            self.mw.window,
            "Sega Conversion",
            "CHD conversion for Sega systems (Dreamcast/Saturn) uses the same 'chdman' tool as PS1.\n"
            "This feature will be fully enabled in the next update."
        )

    def on_nint_compress(self):
        self.mw._qtwidgets.QMessageBox.information(
            self.mw.window,
            "Compression",
            "Generic 7z/Zip compression for legacy systems is coming soon."
        )
