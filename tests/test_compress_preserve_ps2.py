import os
from pathlib import Path
from types import SimpleNamespace

from emumanager.library import LibraryDB
from emumanager.workers.ps2 import worker_chd_to_cso_single


def fake_run_cmd_stream(cmd, progress_cb=None):
    # Create any .iso or .cso targets referenced in the command to simulate
    # successful extraction and compression.
    for arg in cmd:
        if isinstance(arg, str) and arg.endswith(".iso"):
            Path(arg).write_bytes(b"tmp-iso")
        if isinstance(arg, str) and arg.endswith(".cso"):
            Path(arg).write_bytes(b"cso")

    class R:
        returncode = 0

    return R()


def test_ps2_chd_to_cso_preserves_hashes_and_logs(tmp_path: Path, monkeypatch):
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        chd = tmp_path / "game.chd"
        chd.write_bytes(b"chddata")

        # Monkeypatch run_cmd_stream and tools
        import emumanager.workers.ps2 as ps2_mod

        monkeypatch.setattr(ps2_mod, "run_cmd_stream", fake_run_cmd_stream)
        monkeypatch.setattr(ps2_mod, "find_tool", lambda name: "/usr/bin/fake")

        args = SimpleNamespace(progress_callback=None)
        worker_chd_to_cso_single(chd, args, lambda m: None)

        cso = chd.with_suffix(".cso")
        db = LibraryDB()
        entry = db.get_entry(str(cso))
        assert entry is not None

        # tmp_iso content used to compute hashes in code; ensure values present
        assert entry.sha1 is not None or entry.md5 is not None

        actions = db.get_actions(20)
        assert any(
            a[1] == "COMPRESSED" and Path(a[0]).name == cso.name for a in actions
        )
    finally:
        os.chdir(cwd)
