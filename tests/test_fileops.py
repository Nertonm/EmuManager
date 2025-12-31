import logging
import os
import time
from pathlib import Path
from types import SimpleNamespace

import emumanager.common.fileops as fileops
from emumanager.common.fileops import safe_move


def simple_hash(p: Path) -> str:
    return p.read_bytes().hex()


def test_safe_unlink_nonexistent(tmp_path):
    p = tmp_path / "nope.txt"
    # should not raise
    fileops.safe_unlink(p, logger=logging.getLogger(__name__))
    assert not p.exists()


def test_safe_unlink_existing(tmp_path):
    p = tmp_path / "file.txt"
    p.write_text("data")
    logger = logging.getLogger(__name__)
    fileops.safe_unlink(p, logger=logger)
    assert not p.exists()


def test_safe_move_dry_run(tmp_path):
    src = tmp_path / "a.nsp"
    dst = tmp_path / "dest" / "a.nsp"
    src.write_text("data")
    args = SimpleNamespace(dry_run=True, dup_check="fast")
    result = safe_move(
        src,
        dst,
        args=args,
        get_file_hash=lambda p: "h",
        logger=SimpleNamespace(
            info=print,
            warning=print,
            debug=print,
            error=print,
            exception=print,
        ),
    )
    assert result is True
    assert src.exists()


def test_safe_move_atomic(tmp_path):
    src = tmp_path / "src.txt"
    src.write_text("atomic")
    dst = tmp_path / "dst.txt"
    args = SimpleNamespace(dry_run=False, dup_check="fast")
    # use a proper logger object
    logger = logging.getLogger(__name__)
    res = fileops.safe_move(
        src, dst, args=args, get_file_hash=simple_hash, logger=logger
    )
    assert res is True
    assert dst.exists()
    assert not src.exists()


def test_safe_move_duplicate_fast(tmp_path):
    src = tmp_path / "a.nsp"
    dst = tmp_path / "existing" / "a.nsp"
    src.write_bytes(b"same")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(b"same")
    # align mtime for fast check
    now = int(time.time())
    os.utime(str(src), (now, now))
    os.utime(str(dst), (now, now))
    args = SimpleNamespace(dry_run=False, dup_check="fast")
    logger = SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        debug=lambda *a, **k: None,
        error=lambda *a, **k: None,
        exception=lambda *a, **k: None,
    )
    result = safe_move(
        src, dst, args=args, get_file_hash=lambda p: "h1", logger=logger
    )
    assert result is False
    assert not src.exists()


def test_safe_move_duplicate_strict_rename(tmp_path):
    src = tmp_path / "a.nsp"
    dst = tmp_path / "existing" / "a.nsp"
    src.write_bytes(b"srcdata")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(b"otherdata")
    args = SimpleNamespace(dry_run=False, dup_check="strict")
    logger = SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        debug=lambda *a, **k: None,
        error=lambda *a, **k: None,
        exception=lambda *a, **k: None,
    )
    result = safe_move(
        src,
        dst,
        args=args,
        get_file_hash=lambda p: "h1" if p == src else "h2",
        logger=logger,
    )
    assert result is True
    found = list(tmp_path.rglob("*_COPY_*"))
    assert len(found) == 1


def test_safe_move_duplicate_strict_exact(tmp_path):
    src = tmp_path / "a.nsp"
    dst = tmp_path / "existing" / "a.nsp"
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"same-data")
    dst.write_bytes(b"same-data")
    now = int(time.time())
    os.utime(str(src), (now, now))
    os.utime(str(dst), (now, now))
    args = SimpleNamespace(dry_run=False, dup_check="strict")
    logger = SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        debug=lambda *a, **k: None,
        error=lambda *a, **k: None,
        exception=lambda *a, **k: None,
    )
    result = safe_move(src, dst, args=args, get_file_hash=lambda p: "h", logger=logger)
    assert result is False
    assert not src.exists()
    assert dst.exists()


def test_safe_move_normal_move(tmp_path):
    src = tmp_path / "a.nsp"
    dst = tmp_path / "dest" / "a.nsp"
    src.write_bytes(b"content")
    args = SimpleNamespace(dry_run=False, dup_check="fast")
    logger = SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        debug=lambda *a, **k: None,
        error=lambda *a, **k: None,
        exception=lambda *a, **k: None,
    )
    result = safe_move(src, dst, args=args, get_file_hash=lambda p: "h", logger=logger)
    assert result is True
    assert not src.exists()
    assert dst.exists()
