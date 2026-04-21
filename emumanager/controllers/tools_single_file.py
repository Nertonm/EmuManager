from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Optional

from emumanager.application import strip_status_prefixed_name


class ToolsSingleFileMixin:
    def _compression_dispatcher(self, path: Path, env: Any, args: Any, log_cb: Callable):
        ext = path.suffix.lower()
        if ext in (".nsp", ".xci"):
            return self._get_worker("worker_compress_single")(path, env, args, log_cb)
        if ext in (".3ds", ".cia", ".cci"):
            return self._get_worker("worker_n3ds_compress_single")(path, args, log_cb)

        if ext == ".iso":
            system = self._get_current_system_name()
            if system in ("gamecube", "wii"):
                from emumanager.workers.dolphin import worker_dolphin_convert_single

                return worker_dolphin_convert_single(path, args, log_cb)
            if system == "psp":
                return self._get_worker("worker_psp_compress_single")(path, args, log_cb)

        logging.warning("No compression handler for %s", ext)
        return None

    def _recompression_dispatcher(self, path: Path, env: Any, args: Any, log_cb: Callable):
        ext = path.suffix.lower()
        if ext == ".rvz":
            return self._get_worker("worker_dolphin_recompress_single")(path, args, log_cb)

        if ext == ".chd":
            system = self._get_current_system_name()
            if system == "ps2":
                from emumanager.workers.ps2 import worker_chd_to_cso_single

                return worker_chd_to_cso_single(path, args, log_cb)

            from emumanager.workers.psx import worker_chd_recompress_single

            return worker_chd_recompress_single(path, args, log_cb)

        if ext in (".nsz", ".xcz"):
            return self._get_worker("worker_recompress_single")(path, env, args, log_cb)

        logging.warning("No recompression handler for %s", ext)
        return None

    def _decompression_dispatcher(self, path: Path, env: Any, args: Any, log_cb: Callable):
        ext = path.suffix.lower()
        if ext in (".rvz", ".gcz", ".wia"):
            return self._get_worker("worker_dolphin_decompress_single")(path, args, log_cb)
        if ext in (".nsz", ".xcz"):
            return self._get_worker("worker_decompress_single")(path, env, args, log_cb)
        if ext == ".7z" and ("3ds" in str(path).lower() or "n3ds" in str(path).lower()):
            return self._get_worker("worker_n3ds_decompress_single")(path, args, log_cb)
        if ext == ".chd":
            from emumanager.workers.psx import worker_chd_decompress_single

            return worker_chd_decompress_single(path, args, log_cb)

        logging.warning("No decompression handler for %s", ext)
        return None

    def _get_current_system_name(self) -> Optional[str]:
        try:
            sys_item = self.mw.sys_list.currentItem()
            return sys_item.text().lower() if sys_item else None
        except Exception as e:
            logging.debug(f"Failed to get current system: {e}")
            return None

    def on_compress_selected(self):
        self._run_single_file_task(self._compression_dispatcher, "Compress", needs_env=True)

    def on_recompress_selected(self):
        self._run_single_file_task(
            self._recompression_dispatcher,
            "Recompress",
            needs_env=True,
        )

    def on_decompress_selected(self):
        self._run_single_file_task(
            self._decompression_dispatcher,
            "Decompress",
            needs_env=True,
        )

    def _resolve_rom_path(self, rom_name: str, system: str) -> Optional[Path]:
        if not self.mw._last_base:
            return None
        rom_name = strip_status_prefixed_name(rom_name)
        base = Path(self.mw._last_base)
        if base.name == "roms":
            return base / system / rom_name
        return base / "roms" / system / rom_name

    def _handle_task_error_log(self, res: Any):
        if not (isinstance(res, str) and "see " in res and ".chdman.out" in res):
            logging.info(str(res))
            return

        try:
            qt = self.mw._qtwidgets
            idx = res.rfind("see ")
            logpath = res[idx + 4 :].strip()

            mb = qt.QMessageBox(self.mw.window)
            mb.setWindowTitle("Extraction Failed")
            mb.setText(f"{res}")
            open_btn = mb.addButton("Open Log", qt.QMessageBox.ActionRole)
            mb.addButton(qt.QMessageBox.StandardButton.Ok)
            mb.exec()

            if mb.clickedButton() == open_btn:
                import subprocess

                subprocess.run(["xdg-open", logpath], check=False)
        except Exception as e:
            logging.debug(f"Failed to show error dialog: {e}")
            logging.info(str(res))

    def _run_single_file_task(self, worker_func, label, needs_env=False):
        rom_item = self.mw.rom_list.currentItem() if self.mw.rom_list else None
        sys_item = self.mw.sys_list.currentItem() if self.mw.sys_list else None

        if not rom_item or not sys_item:
            logging.error("No ROM or system selected")
            return

        full_path = self._resolve_rom_path(rom_item.text(), sys_item.text())
        if not full_path or not full_path.exists():
            logging.error("File not found or base invalid: %s", full_path)
            return

        logging.info("%sing %s...", label, full_path.name)
        args = self.mw._get_common_args()
        env = self.mw._env

        def _work():
            if needs_env:
                return worker_func(full_path, env, args, self.mw.log_msg)
            return worker_func(full_path, args, self.mw.log_msg)

        def _done(res):
            self._handle_task_error_log(res)
            try:
                self.mw.on_list()
                if hasattr(self.mw, "_sync_after_verification"):
                    self.mw._sync_after_verification()
            except Exception:
                pass

        self._set_ui_enabled(False)
        self.mw._run_in_background(_work, _done)
