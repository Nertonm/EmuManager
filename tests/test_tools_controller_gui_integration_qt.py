import os
from pathlib import Path

import pytest


def _import_qtwidgets():
    try:
        from PyQt6 import QtWidgets as qtwidgets

        return qtwidgets
    except Exception:
        try:
            from PySide6 import QtWidgets as qtwidgets  # type: ignore

            return qtwidgets
        except Exception:
            raise RuntimeError("No Qt bindings available for tests")


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Skip heavy GUI test in CI unless explicitly allowed",
)
def test_toolscontroller_compress_click_triggers_worker(tmp_path, monkeypatch):
    # Headless mode
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    qtwidgets = _import_qtwidgets()
    QApplication = qtwidgets.QApplication
    QMainWindow = qtwidgets.QMainWindow
    QListWidgetItem = qtwidgets.QListWidgetItem

    # Ensure QApplication exists (call expression to create if missing)
    QApplication.instance() or QApplication([])

    # Build a simple UI
    from emumanager.gui_ui import MainWindowUI

    main_win = QMainWindow()
    ui = MainWindowUI()
    ui.setup_ui(main_win, qtwidgets)

    # Create a real file in the library
    base = tmp_path
    rom_dir = base / "roms" / "gamecube"
    rom_dir.mkdir(parents=True)
    iso = rom_dir / "demo.iso"
    iso.write_bytes(b"data")

    # Wrap the QMainWindow in a thin object exposing the attributes
    # ToolsController expects
    class TestMainWindow:
        def __init__(self, qwin, ui):
            self._qwin = qwin
            self.ui = ui
            # ToolsController expects these attributes on mw
            self.rom_list = ui.rom_list
            self.sys_list = ui.sys_list
            self._last_base = str(base)
            self._env = None
            self._log_messages = []

        def _get_common_args(self):
            return type("A", (), {"rm_originals": False})()

        def log_msg(self, msg):
            self._log_messages.append(msg)

        def on_list(self):
            # invoked after worker completes
            pass

        def _run_in_background(self, work_fn, done_cb):
            # run synchronously for test
            res = work_fn()
            done_cb(res)

        def _set_ui_enabled(self, v):
            pass

    mw = TestMainWindow(main_win, ui)

    # Add items to the UI lists and select them (controller uses currentItem())
    sys_item = QListWidgetItem("gamecube")
    ui.sys_list.addItem(sys_item)
    ui.sys_list.setCurrentItem(sys_item)

    rom_item = QListWidgetItem("demo.iso")
    ui.rom_list.addItem(rom_item)
    ui.rom_list.setCurrentItem(rom_item)

    # Import ToolsController and instantiate (this will connect signals)
    from emumanager.controllers.tools import ToolsController

    controller = ToolsController(mw)  # noqa: F841

    called = {"flag": False}

    # Patch the controller-level symbol for the dolphin single-file worker
    def fake_worker(path, args, log_cb):
        called["flag"] = True
        # ensure the path points to the expected file
        assert Path(path).name == iso.name
        log_cb("fake dolphin invoked")
        return "Converted: 1"

    # Patch the worker in the workers module since controller imports it locally
    monkeypatch.setattr(
        "emumanager.workers.dolphin.worker_dolphin_convert_single", fake_worker
    )

    # Simulate button click which should trigger the compression flow
    ui.btn_compress.click()

    assert called["flag"] is True
    assert any("fake dolphin invoked" in m for m in mw._log_messages)
