from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from emumanager import gui_workers as _gui_workers

if TYPE_CHECKING:
    from emumanager.gui_main import MainWindowBase

from .tools_batch import ToolsBatchMixin
from .tools_dialogs import ToolsDialogsMixin
from .tools_single_file import ToolsSingleFileMixin

worker_clean_junk = _gui_workers.worker_clean_junk
worker_compress_single = _gui_workers.worker_compress_single
worker_decompress_single = _gui_workers.worker_decompress_single
worker_dolphin_convert = _gui_workers.worker_dolphin_convert
worker_dolphin_decompress_single = _gui_workers.worker_dolphin_decompress_single
worker_dolphin_organize = _gui_workers.worker_dolphin_organize
worker_dolphin_recompress_single = _gui_workers.worker_dolphin_recompress_single
worker_dolphin_verify = _gui_workers.worker_dolphin_verify
worker_health_check = _gui_workers.worker_health_check
worker_n3ds_compress = _gui_workers.worker_n3ds_compress
worker_n3ds_compress_single = _gui_workers.worker_n3ds_compress_single
worker_n3ds_convert_cia = _gui_workers.worker_n3ds_convert_cia
worker_n3ds_decompress = _gui_workers.worker_n3ds_decompress
worker_n3ds_decompress_single = _gui_workers.worker_n3ds_decompress_single
worker_n3ds_organize = _gui_workers.worker_n3ds_organize
worker_n3ds_verify = _gui_workers.worker_n3ds_verify
worker_organize = _gui_workers.worker_organize
worker_ps2_convert = _gui_workers.worker_ps2_convert
worker_ps2_organize = _gui_workers.worker_ps2_organize
worker_ps2_verify = _gui_workers.worker_ps2_verify
worker_ps3_organize = _gui_workers.worker_ps3_organize
worker_ps3_verify = _gui_workers.worker_ps3_verify
worker_psp_compress = _gui_workers.worker_psp_compress
worker_psp_compress_single = _gui_workers.worker_psp_compress_single
worker_psp_organize = _gui_workers.worker_psp_organize
worker_psp_verify = _gui_workers.worker_psp_verify
worker_psx_convert = _gui_workers.worker_psx_convert
worker_psx_organize = _gui_workers.worker_psx_organize
worker_psx_verify = _gui_workers.worker_psx_verify
worker_recompress_single = _gui_workers.worker_recompress_single
worker_switch_compress = _gui_workers.worker_switch_compress
worker_switch_decompress = _gui_workers.worker_switch_decompress

MSG_SELECT_BASE = "Please select a base directory first (Open Library)."
REQUIRED_SIGNAL_BINDINGS = (
    ("btn_compress", "on_compress_selected"),
    ("btn_recompress", "on_recompress_selected"),
    ("btn_decompress", "on_decompress_selected"),
    ("btn_organize", "on_organize"),
    ("btn_health", "on_health_check"),
    ("btn_switch_compress", "on_switch_compress"),
    ("btn_switch_decompress", "on_switch_decompress"),
    ("btn_psx_convert", "on_psx_convert"),
    ("btn_psx_verify", "on_psx_verify"),
    ("btn_psx_organize", "on_psx_organize"),
    ("btn_ps2_convert", "on_ps2_convert"),
    ("btn_ps2_verify", "on_ps2_verify"),
    ("btn_ps2_organize", "on_ps2_organize"),
    ("btn_ps3_verify", "on_ps3_verify"),
    ("btn_ps3_organize", "on_ps3_organize"),
    ("btn_psp_verify", "on_psp_verify"),
    ("btn_psp_organize", "on_psp_organize"),
    ("btn_psp_compress", "on_psp_compress"),
    ("btn_dolphin_organize", "on_dolphin_organize"),
    ("btn_dolphin_convert", "on_dolphin_convert"),
    ("btn_dolphin_verify", "on_dolphin_verify"),
    ("btn_n3ds_organize", "on_n3ds_organize"),
    ("btn_n3ds_verify", "on_n3ds_verify"),
    ("btn_n3ds_compress", "on_n3ds_compress"),
    ("btn_n3ds_decompress", "on_n3ds_decompress"),
    ("btn_n3ds_convert_cia", "on_n3ds_convert_cia"),
    ("btn_clean_junk", "on_clean_junk"),
)
OPTIONAL_SIGNAL_BINDINGS = (
    ("btn_sega_convert", "on_sega_convert"),
    ("btn_sega_verify", "on_generic_verify_click"),
    ("btn_sega_organize", "on_generic_organize_click"),
    ("btn_ms_verify", "on_generic_verify_click"),
    ("btn_ms_organize", "on_generic_organize_click"),
    ("btn_nint_compress", "on_nint_compress"),
    ("btn_nint_verify", "on_generic_verify_click"),
    ("btn_nint_organize", "on_generic_organize_click"),
)
TOOL_TASK_SPECS = {
    "switch_organize": ("worker_organize", "Organize Switch", True),
    "switch_health": ("worker_health_check", "Health Check", True),
    "switch_compress": ("worker_switch_compress", "Compress Switch Library", True),
    "switch_decompress": ("worker_switch_decompress", "Decompress Switch Library", True),
    "psx_convert": ("worker_psx_convert", "Convert PS1 to CHD", False),
    "psx_verify": ("worker_psx_verify", "Verify PS1", False),
    "psx_organize": ("worker_psx_organize", "Organize PS1", False),
    "ps2_convert": ("worker_ps2_convert", "Convert PS2 to CHD", False),
    "ps2_verify": ("worker_ps2_verify", "Verify PS2", False),
    "ps2_organize": ("worker_ps2_organize", "Organize PS2", False),
    "ps3_verify": ("worker_ps3_verify", "Verify PS3", False),
    "ps3_organize": ("worker_ps3_organize", "Organize PS3", False),
    "psp_verify": ("worker_psp_verify", "Verify PSP", False),
    "psp_organize": ("worker_psp_organize", "Organize PSP", False),
    "dolphin_organize": ("worker_dolphin_organize", "Organize GC/Wii", False),
    "dolphin_convert": ("worker_dolphin_convert", "Convert GC/Wii to RVZ", False),
    "dolphin_verify": ("worker_dolphin_verify", "Verify GC/Wii", False),
    "n3ds_organize": ("worker_n3ds_organize", "Organize 3DS", False),
    "n3ds_verify": ("worker_n3ds_verify", "Verify 3DS", False),
    "n3ds_compress": ("worker_n3ds_compress", "Compress 3DS", False),
    "n3ds_decompress": ("worker_n3ds_decompress", "Decompress 3DS", False),
    "n3ds_convert_cia": ("worker_n3ds_convert_cia", "Convert 3DS to CIA", False),
}
PATCHABLE_WORKER_NAMES = {
    "worker_clean_junk",
    "worker_compress_single",
    "worker_decompress_single",
    "worker_dolphin_convert",
    "worker_dolphin_decompress_single",
    "worker_dolphin_organize",
    "worker_dolphin_recompress_single",
    "worker_dolphin_verify",
    "worker_health_check",
    "worker_n3ds_compress",
    "worker_n3ds_compress_single",
    "worker_n3ds_convert_cia",
    "worker_n3ds_decompress",
    "worker_n3ds_decompress_single",
    "worker_n3ds_organize",
    "worker_n3ds_verify",
    "worker_organize",
    "worker_ps2_convert",
    "worker_ps2_organize",
    "worker_ps2_verify",
    "worker_ps3_organize",
    "worker_ps3_verify",
    "worker_psp_compress",
    "worker_psp_compress_single",
    "worker_psp_organize",
    "worker_psp_verify",
    "worker_psx_convert",
    "worker_psx_organize",
    "worker_psx_verify",
    "worker_recompress_single",
    "worker_switch_compress",
    "worker_switch_decompress",
}


class ToolsController(
    ToolsSingleFileMixin,
    ToolsBatchMixin,
    ToolsDialogsMixin,
):
    def __init__(self, main_window: MainWindowBase):
        self.mw = main_window
        self.ui = main_window.ui
        self._connect_signals()

    def _connect_signals(self):
        self._connect_binding_group(REQUIRED_SIGNAL_BINDINGS)
        self._connect_binding_group(OPTIONAL_SIGNAL_BINDINGS, optional=True)
        self._connect_window_action("act_show_actions", self.on_show_actions)

    def _connect_binding_group(self, bindings, optional: bool = False):
        for attr_name, handler_name in bindings:
            widget = getattr(self.ui, attr_name, None)
            if widget is None:
                if optional:
                    continue
                raise AttributeError(f"Missing required UI widget: {attr_name}")
            widget.clicked.connect(getattr(self, handler_name))

    def _connect_window_action(self, action_name: str, handler: Callable):
        try:
            action = getattr(self.mw, action_name, None)
            if action is not None:
                action.triggered.connect(handler)
        except Exception:
            pass

    def _get_worker(self, name: str):
        if name not in PATCHABLE_WORKER_NAMES:
            raise KeyError(f"Unknown worker alias: {name}")
        return globals()[name]

    def _get_tool_task_spec(self, key: str):
        return TOOL_TASK_SPECS[key]

    def _ensure_base_selected(self) -> bool:
        if self.mw._last_base:
            return True
        logging.warning(MSG_SELECT_BASE)
        return False

    def _set_ui_enabled(self, enabled: bool) -> None:
        if hasattr(self.mw, "_set_ui_enabled"):
            try:
                self.mw._set_ui_enabled(enabled)
            except Exception:
                pass
