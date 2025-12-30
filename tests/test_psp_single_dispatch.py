from pathlib import Path

from emumanager.controllers.tools import ToolsController


class DummyClicked:
    def connect(self, fn):
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
        self.rom_list = type(
            "R", (), {"currentItem": lambda self: DummyItem(rel_path)}
        )()
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
        pass

    def _run_in_background(self, work_fn, done_cb):
        res = work_fn()
        done_cb(res)


def test_psp_single_dispatch_calls_worker(tmp_path, monkeypatch):
    base = tmp_path
    roms_dir = base / "roms" / "psp"
    roms_dir.mkdir(parents=True)
    iso = roms_dir / "game.iso"
    iso.write_bytes(b"data")

    rel_path = "game.iso"
    mw = DummyMainWindow(base, rel_path, "psp")

    # Prevent real signal hookups
    monkeypatch.setattr(
        "emumanager.controllers.tools.ToolsController._connect_signals",
        lambda self: None,
    )

    controller = ToolsController(mw)

    called = {"flag": False}

    def fake_psp_single(path, args, log_cb):
        called["flag"] = True
        assert Path(path).name == iso.name
        log_cb("psp worker invoked")
        return "OK"

    # Patch the single-file worker symbol used by the controller
    monkeypatch.setattr(
        "emumanager.controllers.tools.worker_psp_compress_single", fake_psp_single
    )

    controller.on_compress_selected()

    assert called["flag"] is True
    assert any("psp worker invoked" in m for m in mw._log_messages)
