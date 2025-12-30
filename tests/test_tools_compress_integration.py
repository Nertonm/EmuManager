from pathlib import Path

from emumanager.controllers.tools import ToolsController


class DummyClicked:
    def connect(self, fn):
        # No-op for signal connection during test
        pass


class DummyUI:
    def __init__(self):
        self.btn_compress = type("B", (), {"clicked": DummyClicked()})()


class DummyItem:
    def __init__(self, text):
        self._text = text

    def text(self):
        return self._text


class DummyMainWindow:
    def __init__(self, base_path, rel_path, system_name):
        self.ui = DummyUI()
        # rom_list with a currentItem() method
        self.rom_list = type(
            "R", (), {"currentItem": lambda self: DummyItem(rel_path)}
        )()
        # sys_list with currentItem() returning object with text()
        self.sys_list = type(
            "S", (), {"currentItem": lambda self: DummyItem(system_name)}
        )()
        self._last_base = str(base_path)
        self._env = None
        self._log_messages = []

    def _get_common_args(self):
        return type("A", (), {"rm_originals": False})()

    def log_msg(self, msg):
        self._log_messages.append(msg)

    def on_list(self):
        # called when background work completes; no-op for test
        pass

    def _run_in_background(self, work_fn, done_cb):
        # Run synchronously for tests
        res = work_fn()
        done_cb(res)


def test_on_compress_selected_routes_to_dolphin_single(tmp_path, monkeypatch):
    # Arrange: create a fake rom file under base/roms/gamecube
    base = tmp_path
    roms_dir = base / "roms" / "gamecube"
    roms_dir.mkdir(parents=True)
    iso = roms_dir / "demo.iso"
    iso.write_bytes(b"dummy")

    # Build a dummy main window with the relative path as shown in UI
    rel_path = "demo.iso"
    mw = DummyMainWindow(base, rel_path, "gamecube")

    # Prevent ToolsController from trying to connect real UI signals at init
    monkeypatch.setattr(
        "emumanager.controllers.tools.ToolsController._connect_signals",
        lambda self: None,
    )

    controller = ToolsController(mw)

    called = {"flag": False}

    # Monkeypatch the worker to assert it receives the expected path and to mark called
    def fake_worker(path, args, log_cb):
        assert Path(path).name == iso.name
        called["flag"] = True
        log_cb("fake worker called")
        return "Converted: 1"

    monkeypatch.setattr(
        "emumanager.workers.dolphin.worker_dolphin_convert_single", fake_worker
    )

    # Act
    controller.on_compress_selected()

    # Assert
    assert called["flag"] is True
    # Ensure the fake worker logged something into mw
    assert any("fake worker called" in m for m in mw._log_messages)
