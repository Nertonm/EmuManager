from pathlib import Path
from types import SimpleNamespace

from emumanager.library import LibraryDB, LibraryEntry
from emumanager.workers import ps2


def list_files_fn(p: Path):
    try:
        return [x for x in p.iterdir() if x.is_file()]
    except Exception:
        return []


def test_ps2_skips_compressed_and_logs_action(tmp_path):
    target_dir = tmp_path / "roms" / "ps2"
    target_dir.mkdir(parents=True, exist_ok=True)
    rom = target_dir / "ps2_game.iso"
    rom.write_bytes(b"data")

    db = LibraryDB()
    st = rom.stat()
    entry = LibraryEntry(
        path=str(rom.resolve()),
        system="ps2",
        size=st.st_size,
        mtime=st.st_mtime,
        crc32=None,
        md5=None,
        sha1=None,
        sha256=None,
        status="COMPRESSED",
        match_name=None,
        dat_name=None,
    )
    db.update_entry(entry)

    args = SimpleNamespace(
        cancel_event=None,
        progress_callback=None,
        deep_verify=False,
        results=[],
        on_result=None,
    )

    def log_cb(msg):
        pass

    res = ps2.worker_ps2_verify(tmp_path, args, log_cb, list_files_fn)
    actions = db.get_actions(10)
    assert any(
        a[1] == "SKIPPED_COMPRESSED" and Path(a[0]).resolve() == rom.resolve()
        for a in actions
    )
    assert isinstance(res, str)
