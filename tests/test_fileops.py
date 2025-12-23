from pathlib import Path
import time
import types

from emumanager.common.fileops import safe_move


def touch(p: Path, content: bytes = b"x"):
    p.write_bytes(content)
    # normalize mtime
    now = int(time.time())
    os_time = now
    p.utime((os_time, os_time))


def test_safe_move_dry_run(tmp_path):
    src = tmp_path / "a.nsp"
    dst = tmp_path / "dest" / "a.nsp"
    src.write_text("data")
    args = types.SimpleNamespace(dry_run=True, dup_check="fast")
    result = safe_move(src, dst, args=args, get_file_hash=lambda p: "h", logger=types.SimpleNamespace(info=print, warning=print, debug=print, error=print, exception=print))
    assert result is True
    assert src.exists()


def test_safe_move_duplicate_fast(tmp_path):
    src = tmp_path / "a.nsp"
    dst = tmp_path / "existing" / "a.nsp"
    src.write_bytes(b"same")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(b"same")
    # align mtime
    now = int(time.time())
    import os as _os
    _os.utime(str(src), (now, now))
    _os.utime(str(dst), (now, now))
    args = types.SimpleNamespace(dry_run=False, dup_check="fast")
    logger = types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, debug=lambda *a, **k: None, error=lambda *a, **k: None, exception=lambda *a, **k: None)
    result = safe_move(src, dst, args=args, get_file_hash=lambda p: "h1", logger=logger)
    # duplicate fast leads to source removal and False return
    assert result is False
    assert not src.exists()


def test_safe_move_duplicate_strict_rename(tmp_path):
    src = tmp_path / "a.nsp"
    dst = tmp_path / "existing" / "a.nsp"
    src.write_bytes(b"srcdata")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(b"otherdata")
    args = types.SimpleNamespace(dry_run=False, dup_check="strict")
    logger = types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, debug=lambda *a, **k: None, error=lambda *a, **k: None, exception=lambda *a, **k: None)
    # get_file_hash returns different values so rename path will be used
    result = safe_move(src, dst, args=args, get_file_hash=lambda p: "h1" if p==src else "h2", logger=logger)
    assert result is True
    # file moved to COPY_1
    found = list(tmp_path.rglob("*_COPY_*"))
    assert len(found) == 1
