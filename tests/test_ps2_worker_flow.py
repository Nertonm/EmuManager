from pathlib import Path
from types import SimpleNamespace

from emumanager.library import LibraryDB
from emumanager.workers import common, ps2

# worker module to patch internal imports


def list_files_fn(p: Path):
    try:
        return [x for x in p.iterdir() if x.is_file()]
    except Exception:
        return []


def test_ps2_chd_verify_skips_when_verify_fails(tmp_path, monkeypatch):
    target_dir = tmp_path / "roms" / "ps2"
    target_dir.mkdir(parents=True, exist_ok=True)
    rom = target_dir / "game.chd"
    rom.write_bytes(b"chddata")

    # Ensure chd verification fails
    monkeypatch.setattr(common, "verify_chd", lambda p: False)

    args = SimpleNamespace(
        cancel_event=None,
        progress_callback=None,
        deep_verify=False,
        results=[],
        per_file_cb=None,
    )

    def log_cb(msg):
        # swallow logs in test
        pass

    res = ps2.worker_ps2_verify(tmp_path, args, log_cb, list_files_fn)

    # Since we early-return on failed CHD verification, no DB entry is written
    db = LibraryDB()
    entry = db.get_entry(str(rom.resolve()))
    assert entry is None
    assert "Identified: 0" in res or "Unknown: 1" in res


def test_ps2_cso_requires_decompress_flag(tmp_path):
    target_dir = tmp_path / "roms" / "ps2"
    target_dir.mkdir(parents=True, exist_ok=True)
    rom = target_dir / "game.cso"
    rom.write_bytes(b"cso data")

    # Call internal processor directly with no decompress flag
    from emumanager.workers.common import GuiLogger

    logger = GuiLogger(lambda m: None)
    args = SimpleNamespace()
    # default: no decompress_cso attribute => treated as False

    res = ps2._process_ps2_file(rom, logger, args=args, deep_verify=False)
    assert res == "unknown"


def test_ps2_deep_verify_saves_hashes(tmp_path, monkeypatch):
    target_dir = tmp_path / "roms" / "ps2"
    target_dir.mkdir(parents=True, exist_ok=True)
    rom = target_dir / "game.iso"
    rom.write_bytes(b"iso data")

    # Simulate PS2 serial/title discovery
    # ps2 module imports metadata/db as ps2_meta/ps2_db.
    # Patch those on the workers module
    monkeypatch.setattr(ps2, "ps2_meta", ps2.ps2_meta)
    monkeypatch.setattr(ps2.ps2_meta, "get_ps2_serial", lambda p: "SLUS-12345")
    monkeypatch.setattr(ps2, "ps2_db", ps2.ps2_db)
    monkeypatch.setattr(ps2.ps2_db.db, "get_title", lambda s: "Game Title")

    # Stub calculate_file_hash to return deterministic values
    def fake_calc(p, algo, chunk_size=8192, progress_cb=None):
        if algo == "md5":
            return "md5val"
        if algo == "sha1":
            return "sha1val"
        return ""

    # _process_ps2_file uses calculate_file_hash imported into the ps2 module,
    # so patch it there.
    monkeypatch.setattr(ps2, "calculate_file_hash", fake_calc)

    from emumanager.workers.common import GuiLogger

    logger = GuiLogger(lambda m: None)
    args = SimpleNamespace()

    res = ps2._process_ps2_file(
        rom, logger, args=args, deep_verify=True, progress_cb=None, per_file_cb=None
    )

    db = LibraryDB()
    entry = db.get_entry(str(rom.resolve()))
    assert entry is not None
    assert entry.md5 == "md5val"
    assert entry.sha1 == "sha1val"
    assert entry.status == "VERIFIED"
    assert entry.match_name == "Game Title"
    assert res == "found"


def test_ps2_cso_decompress_success_creates_and_removes_tmp_iso(tmp_path, monkeypatch):
    """
    Simulate decompressing a CSO with maxcso: the worker should call run_cmd_stream
    (we'll monkeypatch it), the fake runner will write the temporary ISO file
    indicated by the '-o' argument, and return success. After processing the
    temporary ISO should be removed and the resulting entry saved in DB when
    serial/title are discoverable.
    """
    target_dir = tmp_path / "roms" / "ps2"
    target_dir.mkdir(parents=True, exist_ok=True)
    rom = target_dir / "game.cso"
    rom.write_bytes(b"cso data")

    # Ensure find_tool returns a path for maxcso
    def _fake_find_tool(name):
        if name == "maxcso":
            return Path("/usr/bin/maxcso")
        return None

    monkeypatch.setattr(common, "find_tool", _fake_find_tool)

    # Capture the -o value and write a fake ISO there
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
        # find the -o <tmp_iso> argument and create the file
        try:
            if "-o" in cmd:
                o_idx = cmd.index("-o")
                out_path = Path(cmd[o_idx + 1])
                out_path.write_bytes(b"fake iso data")
        except Exception:
            pass
        return DummyRes(rc=0, stdout="")

    monkeypatch.setattr(ps2, "run_cmd_stream", fake_run_cmd_stream)

    # Patch serial/title discovery
    monkeypatch.setattr(ps2, "ps2_meta", ps2.ps2_meta)
    monkeypatch.setattr(ps2.ps2_meta, "get_ps2_serial", lambda p: "SLUS-99999")
    monkeypatch.setattr(ps2, "ps2_db", ps2.ps2_db)
    monkeypatch.setattr(ps2.ps2_db.db, "get_title", lambda s: "CSO Game")

    # Patch hashing to deterministic values (worker will hash tmp ISO)
    def fake_calc(p, algo, chunk_size=8192, progress_cb=None):
        if algo == "md5":
            return "cso-md5"
        if algo == "sha1":
            return "cso-sha1"
        return ""

    monkeypatch.setattr(ps2, "calculate_file_hash", fake_calc)

    from emumanager.workers.common import GuiLogger

    logger = GuiLogger(lambda m: None)
    args = SimpleNamespace()
    args.decompress_cso = True
    args.deep_verify = True

    res = ps2._process_ps2_file(rom, logger, args=args, deep_verify=True)

    # Confirm it returned 'found' (serial extracted)
    assert res == "found"

    # DB should contain the CSO entry with hashes
    db = LibraryDB()
    entry = db.get_entry(str((rom).resolve()))
    # Because the worker stores hashes on the source path only when it computed
    # from tmp ISO and updated entry for the original file, check any entry exists
    assert entry is not None
    assert entry.md5 == "cso-md5"
    assert entry.sha1 == "cso-sha1"

    # Ensure temporary ISO created by our fake runner was removed by the worker
    # The worker attempts to unlink tmp_iso; since we wrote to wherever the
    # fake runner pointed, there should be no leftover .iso files in tmp dir
    tmp_iso_files = list(tmp_path.rglob("*.iso"))
    assert not tmp_iso_files
