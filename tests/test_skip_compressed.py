from pathlib import Path
from types import SimpleNamespace

from emumanager.library import LibraryDB, LibraryEntry
from emumanager.workers import psp


def list_files_fn(p: Path):
    try:
        return [x for x in p.iterdir() if x.is_file()]
    except Exception:
        return []


def test_worker_skips_compressed_and_logs_action(tmp_path):
    # Create a fake ROM file
    rom = tmp_path / "test_game.iso"
    rom.write_bytes(b"dummy data")

    # Insert an entry marked as COMPRESSED into the default LibraryDB used by
    # the workers (LibraryDB() defaults to 'library.db' in the project root).
    # We also create the temp DB path for completeness but workers check the
    # default DB instance, so we must insert there.
    db = LibraryDB()

    # Insert an entry marked as COMPRESSED
    st = rom.stat()
    entry = LibraryEntry(
        path=str(rom.resolve()),
        system="psp",
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

    # Prepare args
    args = SimpleNamespace()
    args.cancel_event = None
    args.progress_callback = None
    args.deep_verify = False
    args.results = []
    args.on_result = None

    # Run the PSP verify worker pointing to tmp_path as base
    # Use a simple log callback that does nothing
    def log_cb(msg):
        # Keep output minimal for test
        pass

    result = psp.worker_psp_verify(tmp_path, args, log_cb, list_files_fn)

    # Check that an action was logged
    actions = db.get_actions(10)
    assert any(
        a[1] == "SKIPPED_COMPRESSED" and Path(a[0]).resolve() == rom.resolve()
        for a in actions
    )

    # Worker should return a string summary and not crash
    assert isinstance(result, str)
