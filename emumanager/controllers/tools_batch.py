from __future__ import annotations

import logging


class ToolsBatchMixin:
    def _run_named_tool_task(self, key: str):
        worker_name, label, needs_env = self._get_tool_task_spec(key)
        self._run_tool_task(worker_name, label, needs_env=needs_env)

    def on_organize(self):
        self._run_named_tool_task("switch_organize")

    def on_health_check(self):
        self._run_named_tool_task("switch_health")

    def on_switch_compress(self):
        self._run_named_tool_task("switch_compress")

    def on_switch_decompress(self):
        self._run_named_tool_task("switch_decompress")

    def on_psx_convert(self):
        self._run_named_tool_task("psx_convert")

    def on_psx_verify(self):
        self._run_named_tool_task("psx_verify")

    def on_psx_organize(self):
        self._run_named_tool_task("psx_organize")

    def on_ps2_convert(self):
        self._run_named_tool_task("ps2_convert")

    def on_ps2_verify(self):
        self._run_named_tool_task("ps2_verify")

    def on_ps2_organize(self):
        self._run_named_tool_task("ps2_organize")

    def on_ps3_verify(self):
        self._run_named_tool_task("ps3_verify")

    def on_ps3_organize(self):
        self._run_named_tool_task("ps3_organize")

    def on_psp_verify(self):
        self._run_named_tool_task("psp_verify")

    def on_psp_organize(self):
        self._run_named_tool_task("psp_organize")

    def on_psp_compress(self):
        if not self._ensure_base_selected():
            return

        args = self.mw._get_common_args()
        args.level = 9
        args.rm_originals = self.ui.chk_rm_originals.isChecked()
        worker = self._get_worker("worker_psp_compress")

        def _work():
            return worker(
                self.mw._last_base,
                args,
                self.mw.log_msg,
                self.mw._get_list_files_fn(),
            )

        def _done(res):
            logging.info(str(res))
            self._set_ui_enabled(True)

        self._set_ui_enabled(False)
        self.mw._run_in_background(_work, _done)

    def on_dolphin_organize(self):
        self._run_named_tool_task("dolphin_organize")

    def on_dolphin_convert(self):
        self._run_named_tool_task("dolphin_convert")

    def on_dolphin_verify(self):
        self._run_named_tool_task("dolphin_verify")

    def on_n3ds_organize(self):
        self._run_named_tool_task("n3ds_organize")

    def on_n3ds_verify(self):
        self._run_named_tool_task("n3ds_verify")

    def on_n3ds_compress(self):
        self._run_named_tool_task("n3ds_compress")

    def on_n3ds_decompress(self):
        self._run_named_tool_task("n3ds_decompress")

    def on_n3ds_convert_cia(self):
        self._run_named_tool_task("n3ds_convert_cia")

    def on_clean_junk(self):
        if not self._ensure_base_selected():
            return

        reply = self.mw._qtwidgets.QMessageBox.question(
            self.mw.window,
            "Confirm Clean Junk",
            "This will remove .txt, .url, .nfo files and empty directories.\n"
            "Are you sure you want to proceed?",
            self.mw._qtwidgets.QMessageBox.StandardButton.Yes
            | self.mw._qtwidgets.QMessageBox.StandardButton.No,
            self.mw._qtwidgets.QMessageBox.StandardButton.No,
        )

        if reply != self.mw._qtwidgets.QMessageBox.StandardButton.Yes:
            return

        args = self.mw._get_common_args()
        worker = self._get_worker("worker_clean_junk")

        def list_dirs(path):
            return [p for p in path.rglob("*") if p.is_dir()]

        def _work():
            return worker(
                self.mw._last_base,
                args,
                self.mw.log_msg,
                self.mw._get_list_files_fn(),
                list_dirs,
            )

        def _done(res):
            logging.info(str(res))
            self._set_ui_enabled(True)
            self.mw._update_dashboard_stats()
            if hasattr(self.mw, "_sync_after_verification"):
                self.mw._sync_after_verification()

        self._set_ui_enabled(False)
        self.mw._run_in_background(_work, _done)

    def _run_tool_task(self, worker_name: str, label, needs_env=False):
        del label
        if not self._ensure_base_selected():
            return

        args = self.mw._get_common_args()
        env = self.mw._env
        worker_func = self._get_worker(worker_name)

        def _work():
            if needs_env:
                return worker_func(
                    self.mw._last_base,
                    env,
                    args,
                    self.mw.log_msg,
                    self.mw._get_list_files_fn(),
                )
            return worker_func(
                self.mw._last_base,
                args,
                self.mw.log_msg,
                self.mw._get_list_files_fn(),
            )

        def _done(res):
            logging.info(str(res))
            self._set_ui_enabled(True)
            self.mw._update_dashboard_stats()
            try:
                self.mw._sync_after_verification()
            except Exception as e:
                logging.debug(f"UI sync after tool task failed: {e}")

        self._set_ui_enabled(False)
        self.mw._run_in_background(_work, _done)
