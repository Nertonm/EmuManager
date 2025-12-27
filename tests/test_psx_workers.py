from pathlib import Path

from emumanager.workers.psx import worker_psx_organize, worker_psx_verify
from tests.helpers import Args


def _list_files_recursive(base: Path):
    return [p for p in base.rglob("*") if p.is_file()]


def test_worker_psx_verify_counts(tmp_path):
    # Prepare roms/psx structure
    psx_dir = tmp_path / "roms" / "psx"
    psx_dir.mkdir(parents=True)

    good = psx_dir / "good.iso"
    good.write_bytes(b"BOOT = cdrom:\\SLUS_005.94;1")
    bad = psx_dir / "bad.iso"
    bad.write_bytes(b"no serial here")

    args = Args()
    # Set attrs used by worker
    args.deep_verify = False
    args.cancel_event = None
    args.progress_callback = None

    res = worker_psx_verify(tmp_path, args, lambda s: None, _list_files_recursive)
    assert "Identified: 1" in res and "Unknown: 1" in res


def test_worker_psx_organize_with_db(tmp_path):
    # Create psx_db.csv at base
    db = tmp_path / "psx_db.csv"
    db.write_text("SLUS-00594,Test Game\n", encoding="utf-8")

    psx_dir = tmp_path / "roms" / "psx"
    psx_dir.mkdir(parents=True)

    f = psx_dir / "foo.bin"
    f.write_bytes(b"BOOT = cdrom0:\\SLUS_005.94;1")

    args = Args()
    args.dry_run = False
    args.cancel_event = None
    args.progress_callback = None

    res = worker_psx_organize(tmp_path, args, lambda s: None, _list_files_recursive)
    # New file should exist
    new_path = psx_dir / "Test Game [SLUS-00594].bin"
    assert new_path.exists(), res


def test_worker_psx_organize_without_db(tmp_path):
    psx_dir = tmp_path / "roms" / "psx"
    psx_dir.mkdir(parents=True)

    f = psx_dir / "bar.iso"
    f.write_bytes(b"BOOT = cdrom:\\SLUS_005.94;1")

    args = Args()
    args.dry_run = False
    args.cancel_event = None
    args.progress_callback = None

    res = worker_psx_organize(tmp_path, args, lambda s: None, _list_files_recursive)
    # Expect Unknown Title fallback
    new_path = psx_dir / "Unknown Title [SLUS-00594].iso"
    assert new_path.exists(), res


def test_worker_psx_verify_cue_bin_combo(tmp_path):
    psx_dir = tmp_path / "roms" / "psx"
    psx_dir.mkdir(parents=True)
    # Create both CUE and BIN; serial inside BIN
    cue = psx_dir / "combo.cue"
    binf = psx_dir / "combo.bin"
    cue.write_text(
        'FILE "combo.bin" BINARY\n TRACK 01 MODE2/2352\n INDEX 01 00:00:00\n',
        encoding="utf-8",
    )
    binf.write_bytes(b"BOOT = cdrom:\\SLUS_005.94;1")

    args = Args()
    args.deep_verify = False
    args.cancel_event = None
    args.progress_callback = None

    # Expect at least one identified (could be 2 if both files are processed)
    res = worker_psx_verify(tmp_path, args, lambda s: None, _list_files_recursive)
    assert "Identified:" in res


def test_worker_psx_organize_dry_run(tmp_path):
    psx_dir = tmp_path / "roms" / "psx"
    psx_dir.mkdir(parents=True)
    f = psx_dir / "dry.iso"
    f.write_bytes(b"BOOT = cdrom:\\SLUS_005.94;1")

    args = Args()
    args.dry_run = True
    args.cancel_event = None
    args.progress_callback = None

    res = worker_psx_organize(tmp_path, args, lambda s: None, _list_files_recursive)
    # Original should remain, new path should NOT exist (dry run)
    assert f.exists(), res
    assert not (psx_dir / "Unknown Title [SLUS-00594].iso").exists()
