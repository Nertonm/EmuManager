from unittest.mock import MagicMock
from pathlib import Path
from emumanager.workers.common import BaseWorker, worker_clean_junk

class MockWorker(BaseWorker):
    def _process_item(self, item: Path) -> str:
        return "success"

def test_safe_hash(tmp_path):
    f = tmp_path / "test.bin"
    f.write_bytes(b"test content" * 100)
    
    worker = MockWorker(tmp_path, lambda x: None)
    h = worker.safe_hash(f, "md5")
    assert len(h) == 32

def test_atomic_move(tmp_path):
    src = tmp_path / "source.bin"
    src.touch()
    dst = tmp_path / "target" / "dest.bin"
    
    worker = MockWorker(tmp_path, lambda x: None)
    success = worker.atomic_move(src, dst)
    
    assert success
    assert dst.exists()
    assert not src.exists()

def test_worker_clean_junk(tmp_path):
    # Setup
    base = tmp_path / "collection"
    base.mkdir()
    (base / "roms").mkdir()

    # Junk
    (base / "roms" / "info.txt").touch()
    (base / "roms" / "site.url").touch()
    (base / "roms" / "game.iso").touch()

    # Mock list functions
    def list_files(p): return [f for f in p.rglob("*") if f.is_file()]
    def list_dirs(p): return [d for d in p.rglob("*") if d.is_dir()]

    args = MagicMock()
    args.dry_run = False

    res = worker_clean_junk(base / "roms", args, lambda x: None, list_files, list_dirs)
    assert "Deleted 2 files" in res
    assert not (base / "roms" / "info.txt").exists()
    assert (base / "roms" / "game.iso").exists()