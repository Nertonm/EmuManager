from pathlib import Path
from types import SimpleNamespace

from emumanager.library import LibraryDB
from emumanager.workers import common, ps2
from emumanager.gui_main import MainWindowBase


def _fake_ctrl_true():
    return SimpleNamespace(isChecked=lambda: True)


def _fake_spin(val=1):
    return SimpleNamespace(value=lambda: val)


def _fake_combo(text="None"):
    return SimpleNamespace(currentText=lambda: text)


def test_gui_args_toggle_decompress_cso(tmp_path, monkeypatch):
    # Build a minimal MainWindowBase-like instance without running __init__
    mw = object.__new__(MainWindowBase)

    # Provide the attributes _get_common_args expects
    mw.chk_dry_run = _fake_ctrl_true()
    mw.spin_level = _fake_spin(3)
    mw.combo_profile = _fake_combo("None")
    mw.chk_rm_originals = _fake_ctrl_true()
    mw.chk_quarantine = _fake_ctrl_true()
    mw.chk_deep_verify = _fake_ctrl_true()
    mw.chk_standardize_names = _fake_ctrl_true()
    mw.progress_hook = lambda p, m: None
    mw._cancel_event = None

    # Call _get_common_args and assert we can add decompress flag
    args = mw._get_common_args()
    assert hasattr(args, "deep_verify")
    # Toggle decompress_cso via args as GUI consumer would
    args.decompress_cso = True

    # Prepare a simple CSO file under roms/ps2
    target_dir = tmp_path / "roms" / "ps2"
    target_dir.mkdir(parents=True, exist_ok=True)
    rom = target_dir / "game.cso"
    rom.write_bytes(b"cso data")

    # Ensure find_tool reports maxcso available
    def _fake_find_tool(name):
        if name == "maxcso":
            return Path("/usr/bin/maxcso")
        return None

    monkeypatch.setattr(common, "find_tool", _fake_find_tool)

    # Fake run_cmd_stream to create tmp iso at -o argument
    class DummyRes:
        def __init__(self, rc=0, stdout=""):
            self.returncode = rc
            self.stdout = stdout

    def fake_run_cmd_stream(
        cmd,
        progress_cb=None,
        parser=None,
        timeout=None,
        filebase=None,
        stream_to_file=None,
        check=False,
    ):
        try:
            if "-o" in cmd:
                o_idx = cmd.index("-o")
                out_path = Path(cmd[o_idx + 1])
                out_path.write_bytes(b"fake iso data")
        except Exception:
            pass
        return DummyRes(rc=0, stdout="")

    monkeypatch.setattr(ps2, "run_cmd_stream", fake_run_cmd_stream)

    # Patch serial/title discovery and hashing similar to worker tests
    monkeypatch.setattr(ps2, "ps2_meta", ps2.ps2_meta)
    monkeypatch.setattr(ps2.ps2_meta, "get_ps2_serial", lambda p: "SLUS-42424")
    monkeypatch.setattr(ps2, "ps2_db", ps2.ps2_db)
    monkeypatch.setattr(ps2.ps2_db.db, "get_title", lambda s: "GUI CSO Game")

    def fake_calc(p, algo, chunk_size=8192, progress_cb=None):
        if algo == "md5":
            return "gui-md5"
        if algo == "sha1":
            return "gui-sha1"
        return ""

    monkeypatch.setattr(ps2, "calculate_file_hash", fake_calc)

    # Run the worker using the args coming from GUI
    res = ps2.worker_ps2_verify(
        tmp_path,
        args,
        lambda m: None,
        lambda p: [x for x in p.iterdir() if x.is_file()],
    )

    assert isinstance(res, str)
    db = LibraryDB()
    entry = db.get_entry(str(rom.resolve()))
    assert entry is not None
    assert entry.md5 == "gui-md5"
    assert entry.sha1 == "gui-sha1"
