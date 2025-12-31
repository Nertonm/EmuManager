from pathlib import Path
import os
import tempfile
from types import SimpleNamespace

import emumanager.common.fileops as fileops


def test_is_exact_duplicate_fast_true(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"content")
    b.write_bytes(b"content")
    # align mtimes
    now = int(os.path.getmtime(a))
    os.utime(str(a), (now, now))
    os.utime(str(b), (now, now))
    assert fileops._is_exact_duplicate_fast(a, b) is True


def test_is_exact_duplicate_fast_false_on_error(tmp_path):
    # non-existent file causes exception -> False
    a = tmp_path / "nope.bin"
    b = tmp_path / "b.bin"
    b.write_bytes(b"x")
    assert fileops._is_exact_duplicate_fast(a, b) is False


def test_is_exact_duplicate_strict_true(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"hello")
    b.write_bytes(b"hello")
    def get_hash(p):
        return p.read_bytes().hex()
    assert fileops._is_exact_duplicate_strict(a, b, get_hash) is True


def test_is_exact_duplicate_strict_false_on_error(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"a")
    b.write_bytes(b"b")

    def bad_hash(p):
        raise RuntimeError("boom")

    assert fileops._is_exact_duplicate_strict(a, b, bad_hash) is False


def test_choose_duplicate_target_fast_removes_source(tmp_path):
    src = tmp_path / "s.bin"
    dst = tmp_path / "d" / "s.bin"
    dst.parent.mkdir()
    src.write_text("x")
    dst.write_text("x")
    # align mtimes so fast check triggers
    now = int(os.path.getmtime(src))
    os.utime(str(src), (now, now))
    os.utime(str(dst), (now, now))
    args = SimpleNamespace(dup_check="fast")
    logger = SimpleNamespace(
        info=lambda *a, **k: None,
        debug=lambda *a, **k: None,
    )
    chosen = fileops._choose_duplicate_target(
        src, dst, args, (lambda p: "h"), logger=logger
    )
    assert chosen is None
    assert not src.exists()


def test_choose_duplicate_target_strict_removes_source(tmp_path):
    src = tmp_path / "s2.bin"
    dst = tmp_path / "d2" / "s2.bin"
    dst.parent.mkdir()
    src.write_text("x")
    dst.write_text("x")
    args = SimpleNamespace(dup_check="strict")
    logger = SimpleNamespace(
        info=lambda *a, **k: None,
        debug=lambda *a, **k: None,
    )
    # provide equal hashes
    def get_hash(p):
        return "same"
    chosen = fileops._choose_duplicate_target(src, dst, args, get_hash, logger=logger)
    assert chosen is None
    assert not src.exists()


def test_choose_duplicate_target_returns_new_name(tmp_path):
    src = tmp_path / "s3.bin"
    dst = tmp_path / "dest" / "s3.bin"
    dst.parent.mkdir(parents=True)
    src.write_text("x")
    dst.write_text("other")
    args = SimpleNamespace(dup_check="fast")
    logger = SimpleNamespace(
        info=lambda *a, **k: None,
        debug=lambda *a, **k: None,
    )
    new = fileops._choose_duplicate_target(
        src, dst, args, (lambda p: "h"), logger=logger
    )
    assert new is not None
    assert not new.exists()


def test_copy_and_replace_hash_mismatch(tmp_path):
    src = tmp_path / "src.bin"
    src.write_bytes(b"aaa")
    dest_parent = tmp_path / "destdir"
    dest_parent.mkdir()
    dest = dest_parent / "out.bin"
    args = SimpleNamespace(dup_check="strict")
    # get_file_hash that always returns different values
    def get_hash(p):
        return "h_src" if p == src else "h_tmp"
    logger = SimpleNamespace(
        info=lambda *a, **k: None,
        debug=lambda *a, **k: None,
        exception=lambda *a, **k: None,
    )
    ok = fileops._copy_and_replace(src, dest, dest_parent, args, get_hash, logger)
    assert ok is False
    # ensure no temp files left
    leftover = list(dest_parent.iterdir())
    assert all(not p.name.startswith(".emumgr_tmp_") for p in leftover)


def test_verify_hashes_exception(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"1")
    b.write_bytes(b"2")

    def bad(p):
        raise RuntimeError("nope")

    logger = SimpleNamespace(debug=lambda *a, **k: None)
    assert fileops._verify_hashes(a, b, bad, logger) is False


def test_try_atomic_replace_success(tmp_path):
    src = tmp_path / "from.txt"
    src.write_text("ok")
    dest = tmp_path / "to.txt"
    logger = SimpleNamespace(info=lambda *a, **k: None, debug=lambda *a, **k: None)
    ok = fileops._try_atomic_replace(src, dest, logger)
    assert ok is True
    assert dest.exists()


def test_try_atomic_replace_failure():
    src = Path(tempfile.gettempdir()) / "no-such-file-xyz"
    dest = src.parent / "whatever"
    logger = SimpleNamespace()
    assert fileops._try_atomic_replace(src, dest, logger) is False


def test_safe_unlink_permission(monkeypatch, tmp_path):
    p = tmp_path / "todel.txt"
    p.write_text("x")

    def fake_unlink(self=None):
        raise PermissionError("denied")

    # patch the Path.unlink used by the module under test
    monkeypatch.setattr(fileops.Path, "unlink", fake_unlink)
    logger = SimpleNamespace(
        warning=lambda *a, **k: None,
        debug=lambda *a, **k: None,
        exception=lambda *a, **k: None,
    )
    # should not raise
    fileops.safe_unlink(p, logger)
