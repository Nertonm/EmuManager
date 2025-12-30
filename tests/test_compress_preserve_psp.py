import os
from pathlib import Path
from types import SimpleNamespace

from emumanager.library import LibraryDB
from emumanager.workers.common import calculate_file_hash
from emumanager.workers.psp import worker_psp_compress_single


def test_psp_compress_preserves_hashes_and_logs(tmp_path: Path, monkeypatch):
    # Run inside tmp_path so LibraryDB uses local library.db
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        system_dir = tmp_path / "roms" / "psp"
        system_dir.mkdir(parents=True)
        src = system_dir / "game.iso"
        src.write_bytes(b"original-data")

        # Monkeypatch compressor to create a .cso file and return True
        def fake_compress(src_path, out_path, level=9, dry_run=False):
            # emulate compression by copying file
            out_path.write_bytes(src_path.read_bytes())
            return True

        import emumanager.converters.psp_converter as psp_converter

        monkeypatch.setattr(psp_converter, "compress_to_cso", fake_compress)

        # Run worker single-file compress
        # We don't remove originals for the preservation test so the source
        # remains available for hash calculation.
        args = SimpleNamespace(dry_run=False, rm_originals=False, level=9)
        worker_psp_compress_single(src, args, lambda m: None)

        # DB should exist in tmp_path
        db = LibraryDB()

        cso = src.with_suffix(".cso")
        entry = db.get_entry(str(cso))
        assert entry is not None

        # Hashes should match original
        md5 = calculate_file_hash(src, "md5")
        sha1 = calculate_file_hash(src, "sha1")
        assert entry.md5 == md5
        assert entry.sha1 == sha1

        # Action log should include COMPRESSED for the cso
        actions = db.get_actions(20)
        assert any(
            a[1] == "COMPRESSED" and Path(a[0]).name == cso.name for a in actions
        )
    finally:
        os.chdir(cwd)
