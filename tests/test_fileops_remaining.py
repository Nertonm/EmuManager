import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import emumanager.common.fileops as fo


class DummyLogger:
    def __init__(self):
        self.records = []

    def info(self, *a, **k):
        self.records.append(("info", a))

    def debug(self, *a, **k):
        self.records.append(("debug", a))

    def warning(self, *a, **k):
        self.records.append(("warning", a))

    def error(self, *a, **k):
        self.records.append(("error", a))

    def exception(self, *a, **k):
        self.records.append(("exception", a))


def test_duplicate_fast_removes_source(tmp_path):
    src = tmp_path / "a.bin"
    dst = tmp_path / "b.bin"
    src.write_bytes(b"abc")
    dst.write_bytes(b"abc")
    # ensure same mtime (fast check compares int mtime)
    mtime = int(src.stat().st_mtime)
    os.utime(src, (mtime, mtime))
    os.utime(dst, (mtime, mtime))

    args = SimpleNamespace(dup_check="fast")
    logger = DummyLogger()

    chosen = fo._choose_duplicate_target(src, dst, args, lambda p: "h", logger=logger)
    # fast duplicate should return None and remove source
    assert chosen is None
    assert not src.exists()


def test_duplicate_strict_removes_source(tmp_path):
    src = tmp_path / "s.bin"
    dst = tmp_path / "d.bin"
    src.write_bytes(b"content")
    dst.write_bytes(b"content")

    def hashfn(p: Path) -> str:  # identical hashes
        return "same"

    args = SimpleNamespace(dup_check="strict")
    logger = DummyLogger()
    chosen = fo._choose_duplicate_target(src, dst, args, hashfn, logger)
    assert chosen is None
    assert not src.exists()


def test_safe_move_trims_long_name(tmp_path):
    # create source
    src = tmp_path / "orig.bin"
    src.write_bytes(b"x")

    # create very long destination name (>240)
    long_name = "a" * 241 + ".iso"
    dst = tmp_path / long_name

    args = SimpleNamespace(dry_run=False, dup_check="fast")

    def hashfn(p: Path) -> str:
        return "h"

    logger = DummyLogger()
    # perform safe_move; should trim dest name
    ok = fo.safe_move(src, dst, args=args, get_file_hash=hashfn, logger=logger)
    assert ok is True
    # source should have been moved (no longer exists)
    assert not src.exists()
    # find file in tmp_path with truncated name (stem length 200)
    found = None
    for p in tmp_path.iterdir():
        if p.name.endswith(".iso"):
            found = p
            break
    assert found is not None
    assert len(found.stem) <= 200


def test_safe_move_falls_back_to_copy_and_replace(monkeypatch, tmp_path):
    src = tmp_path / "from.bin"
    dst = tmp_path / "to.bin"
    src.write_bytes(b"DATA")

    args = SimpleNamespace(dry_run=False, dup_check="fast")

    def hashfn(p: Path) -> str:
        return "h"

    logger = DummyLogger()

    called = {"copy_called": False}

    def fake_try_atomic_replace(s, d, log):
        # simulate atomic replace failing
        return False

    def fake_copy_and_replace(s, d, parent, args_in, hashf, log):
        called["copy_called"] = True
        # perform a real replacement so file appears at dest
        shutil.copy2(str(s), str(d))
        try:
            s.unlink()
        except Exception:
            pass
        return True

    monkeypatch.setattr(fo, "_try_atomic_replace", fake_try_atomic_replace)
    monkeypatch.setattr(fo, "_copy_and_replace", fake_copy_and_replace)

    ok = fo.safe_move(src, dst, args=args, get_file_hash=hashfn, logger=logger)
    assert ok is True
    assert called["copy_called"] is True
    assert dst.exists()
    assert not src.exists()
