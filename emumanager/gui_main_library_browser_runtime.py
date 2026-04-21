from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any


@dataclass
class GuiActionArgs:
    dry_run: bool
    level: int
    compression_profile: str | None
    rm_originals: bool
    quarantine: bool
    deep_verify: bool
    clean_junk: bool = False
    organize: bool = False
    compress: bool = False
    decompress: bool = False
    recompress: bool = False
    keep_on_failure: bool = False
    cmd_timeout: Any = None
    quarantine_dir: Any = None
    report_csv: Any = None
    dup_check: str = "fast"
    verbose: bool = False
    progress_callback: Any = None
    cancel_event: Any = None
    standardize_names: bool = False
    orchestrator: Any = None
    library_db: Any = None


class MainWindowLibraryBrowserRuntimeMixin:
    def _ensure_env(self, base_path: Path):
        if self._env and self._env.get("ROMS_DIR") == base_path:
            return

        try:
            from emumanager.common.execution import find_tool
            from emumanager.switch.main_helpers import configure_environment

            keys_path = base_path / "keys.txt"
            if not keys_path.exists():
                keys_path = base_path / "prod.keys"

            args = SimpleNamespace(
                dir=str(base_path),
                keys=str(keys_path),
                compress=False,
                decompress=False,
            )

            class GuiLogger:
                def __init__(self, window):
                    self._window = window

                def info(self, msg, *args):
                    self._window.log_msg(msg % args if args else msg)

                def warning(self, msg, *args):
                    self._window.log_msg("WARN: " + (msg % args if args else msg))

                def error(self, msg, *args):
                    self._window.log_msg("ERROR: " + (msg % args if args else msg))

                def debug(self, msg, *args):
                    del msg, args

                def exception(self, msg, *args):
                    self._window.log_msg("EXCEPTION: " + (msg % args if args else msg))

            self._env = configure_environment(args, GuiLogger(self), find_tool)
            self.log_msg(f"Environment configured for {base_path}")
        except Exception as exc:
            self.log_msg(f"Failed to configure environment: {exc}")
            self._env = {}

    def _get_common_args(self):
        profile = self.combo_profile.currentText()
        return GuiActionArgs(
            dry_run=self.chk_dry_run.isChecked(),
            level=self.spin_level.value(),
            compression_profile=profile if profile != "None" else None,
            rm_originals=self.chk_rm_originals.isChecked(),
            quarantine=self.chk_quarantine.isChecked(),
            deep_verify=self.chk_deep_verify.isChecked(),
            progress_callback=self.progress_hook,
            cancel_event=self._cancel_event,
            standardize_names=self.chk_standardize_names.isChecked(),
            orchestrator=self._orchestrator,
            library_db=self.library_db,
        )
