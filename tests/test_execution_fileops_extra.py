import subprocess
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

import emumanager.common.execution as ex
import emumanager.common.fileops as fo


class SimpleLogger:
    def __init__(self):
        self.records = []

    def info(self, *a, **k):
        self.records.append(("info", a))

    def debug(self, *a, **k):
        self.records.append(("debug", a))

    def warning(self, *a, **k):
        self.records.append(("warning", a))

    def exception(self, *a, **k):
        self.records.append(("exception", a))


def test_run_cmd_popen_timeout(monkeypatch):
    class FakePopen:
        def __init__(
            self,
            cmd,
            stdout,
            stderr,
            text,
            encoding,
            errors,
            startupinfo=None,
        ):
            self._killed = False
            self.returncode = None

        def communicate(self, timeout=None):
            if not self._killed and timeout is not None:
                # simulate timeout on first call
                raise subprocess.TimeoutExpired(cmd=["fake"], timeout=timeout)
            return ("partial", "err")

        def kill(self):
            self._killed = True

        def wait(self):
            return 1

    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    with pytest.raises(subprocess.TimeoutExpired):
        ex.run_cmd(["fake"], timeout=0.01)


def test_run_cmd_writes_filebase(monkeypatch, tmp_path):
    class FakePopen:
        def __init__(
            self,
            cmd,
            stdout,
            stderr,
            text,
            encoding,
            errors,
            startupinfo=None,
        ):
            self.returncode = 0

        def communicate(self, timeout=None):
            return ("OUTTEXT", "ERRTEXT")

    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    fb = tmp_path / "fb"
    ex.run_cmd(["echo"], filebase=fb)
    assert (fb.with_suffix(".out")).exists()
    assert (fb.with_suffix(".err")).exists()
    assert fb.with_suffix(".out").read_text() == "OUTTEXT"


def test_run_cmd_stream_stream_to_file_and_parser_exception(monkeypatch, tmp_path):
    class FakePopen:
        def __init__(
            self,
            cmd,
            stdout,
            stderr,
            text,
            encoding,
            errors,
            startupinfo=None,
        ):
            self.stdout = iter(["line1\n", "badpercent%\n"])
            self.returncode = 0

        def wait(self):
            return 0

    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    def bad_parser(line):
        raise ValueError("bad")

    outp = tmp_path / "stream"
    ex.run_cmd_stream(["fake"], parser=bad_parser, stream_to_file=outp)
    # stream file should be written
    assert outp.with_suffix(".out").exists()
    assert "line1" in outp.with_suffix(".out").read_text()


def test_cancel_current_process_returns_false_when_none():
    # ensure registered processes cleared
    # unregister any existing ones for the test
    with ex._LOCK:
        ex._RUNNING_PROCESSES.clear()
    assert ex.cancel_current_process() is False


def test_choose_duplicate_target_collision_loop(tmp_path):
    src = tmp_path / "s.bin"
    dst = tmp_path / "d.bin"
    src.write_text("x")
    dst.write_text("yy")
    # create existing copies _COPY_1 and _COPY_2
    (dst.parent / (dst.stem + "_COPY_1" + dst.suffix)).write_text("c1")
    (dst.parent / (dst.stem + "_COPY_2" + dst.suffix)).write_text("c2")

    args = SimpleNamespace(dup_check="fast")

    new = fo._choose_duplicate_target(
        src, dst, args, lambda p: "h", logger=SimpleLogger()
    )
    assert new.name.endswith("_COPY_3" + dst.suffix)


def test_copy_and_replace_cleanup_on_copy_failure(monkeypatch, tmp_path):
    src = tmp_path / "a.bin"
    src.write_bytes(b"data")
    dest = tmp_path / "b.bin"

    args = SimpleNamespace(dup_check="fast")

    # force shutil.copy2 to raise
    def fake_copy2(s, d):
        raise OSError("fail")

    monkeypatch.setattr(shutil, "copy2", fake_copy2)

    ok = fo._copy_and_replace(
        src, dest, tmp_path, args, lambda p: "h", logger=SimpleLogger()
    )
    assert ok is False
    # no tmp files left
    assert not any(p.name.startswith(".emumgr_tmp_") for p in tmp_path.iterdir())


def test_verify_hashes_exception():
    def bad_hash(p):
        raise RuntimeError("boom")

    ok = fo._verify_hashes(Path("a"), Path("b"), bad_hash, logger=SimpleLogger())
    assert ok is False


def test_safe_unlink_permission(monkeypatch, tmp_path):
    p = tmp_path / "z.bin"
    p.write_text("x")

    logger = SimpleLogger()

    def raise_perm(self):
        raise PermissionError("denied")

    monkeypatch.setattr(fo.Path, "unlink", raise_perm)
    fo.safe_unlink(p, logger)
    # should have logged a warning entry
    assert any(r[0] == "warning" for r in logger.records)
import subprocess
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

import emumanager.common.execution as ex
import emumanager.common.fileops as fo


class SimpleLogger:
    def __init__(self):
        self.records = []

    def info(self, *a, **k):
        self.records.append(("info", a))

    def debug(self, *a, **k):
        self.records.append(("debug", a))

    def warning(self, *a, **k):
        self.records.append(("warning", a))

    def exception(self, *a, **k):
        self.records.append(("exception", a))


def test_run_cmd_popen_timeout(monkeypatch):
    class FakePopen:
        def __init__(
            self,
            cmd,
            stdout,
            stderr,
            text,
            encoding,
            errors,
            startupinfo=None,
        ):
            self._killed = False
            self.returncode = None

        def communicate(self, timeout=None):
            if not self._killed and timeout is not None:
                # simulate timeout on first call
                raise subprocess.TimeoutExpired(cmd=["fake"], timeout=timeout)
            return ("partial", "err")

        def kill(self):
            self._killed = True

        def wait(self):
            return 1

    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    with pytest.raises(subprocess.TimeoutExpired):
        ex.run_cmd(["fake"], timeout=0.01)


def test_run_cmd_writes_filebase(monkeypatch, tmp_path):
    class FakePopen:
        def __init__(
            self,
            cmd,
            stdout,
            stderr,
            text,
            encoding,
            errors,
            startupinfo=None,
        ):
            self.returncode = 0

        def communicate(self, timeout=None):
            return ("OUTTEXT", "ERRTEXT")

    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    fb = tmp_path / "fb"
    ex.run_cmd(["echo"], filebase=fb)
    assert (fb.with_suffix(".out")).exists()
    assert (fb.with_suffix(".err")).exists()
    assert fb.with_suffix(".out").read_text() == "OUTTEXT"


def test_run_cmd_stream_stream_to_file_and_parser_exception(monkeypatch, tmp_path):
    class FakePopen:
        def __init__(
            self,
            cmd,
            stdout,
            stderr,
            text,
            encoding,
            errors,
            startupinfo=None,
        ):
            self.stdout = iter(["line1\n", "badpercent%\n"])
            self.returncode = 0

        def wait(self):
            return 0

    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    def bad_parser(line):
        raise ValueError("bad")

    outp = tmp_path / "stream"
    ex.run_cmd_stream(["fake"], parser=bad_parser, stream_to_file=outp)
    # stream file should be written
    assert outp.with_suffix(".out").exists()
    assert "line1" in outp.with_suffix(".out").read_text()


def test_cancel_current_process_returns_false_when_none():
    # ensure registered processes cleared
    # unregister any existing ones for the test
    with ex._LOCK:
        ex._RUNNING_PROCESSES.clear()
    assert ex.cancel_current_process() is False


def test_choose_duplicate_target_collision_loop(tmp_path):
    src = tmp_path / "s.bin"
    dst = tmp_path / "d.bin"
    src.write_text("x")
    dst.write_text("yy")
    # create existing copies _COPY_1 and _COPY_2
    (dst.parent / (dst.stem + "_COPY_1" + dst.suffix)).write_text("c1")
    (dst.parent / (dst.stem + "_COPY_2" + dst.suffix)).write_text("c2")

    args = SimpleNamespace(dup_check="fast")

    new = fo._choose_duplicate_target(
        src, dst, args, lambda p: "h", logger=SimpleLogger()
    )
    assert new.name.endswith("_COPY_3" + dst.suffix)


def test_copy_and_replace_cleanup_on_copy_failure(monkeypatch, tmp_path):
    src = tmp_path / "a.bin"
    src.write_bytes(b"data")
    dest = tmp_path / "b.bin"

    args = SimpleNamespace(dup_check="fast")

    # force shutil.copy2 to raise
    def fake_copy2(s, d):
        raise OSError("fail")

    monkeypatch.setattr(shutil, "copy2", fake_copy2)

    ok = fo._copy_and_replace(
        src, dest, tmp_path, args, lambda p: "h", logger=SimpleLogger()
    )
    assert ok is False
    # no tmp files left
    assert not any(p.name.startswith(".emumgr_tmp_") for p in tmp_path.iterdir())


def test_verify_hashes_exception():
    def bad_hash(p):
        raise RuntimeError("boom")

    ok = fo._verify_hashes(Path("a"), Path("b"), bad_hash, logger=SimpleLogger())
    assert ok is False


def test_safe_unlink_permission(monkeypatch, tmp_path):
    p = tmp_path / "z.bin"
    p.write_text("x")

    logger = SimpleLogger()

    def raise_perm(self):
        raise PermissionError("denied")

    monkeypatch.setattr(fo.Path, "unlink", raise_perm)
    fo.safe_unlink(p, logger)
    # should have logged a warning entry
    assert any(r[0] == "warning" for r in logger.records)
import subprocess
import shutil
from pathlib import Path

import pytest

import emumanager.common.execution as ex
import emumanager.common.fileops as fo


class SimpleLogger:
    def __init__(self):
        self.records = []

    def info(self, *a, **k):
        self.records.append(("info", a))

    def debug(self, *a, **k):
        self.records.append(("debug", a))

    def warning(self, *a, **k):
        self.records.append(("warning", a))

    def exception(self, *a, **k):
        self.records.append(("exception", a))


def test_run_cmd_popen_timeout(monkeypatch):
    class FakePopen:
        def __init__(
            self,
            cmd,
            stdout,
            stderr,
            text,
            encoding,
            errors,
            startupinfo=None,
        ):
            self._killed = False
            self.returncode = None

        def communicate(self, timeout=None):
            if not self._killed and timeout is not None:
                # simulate timeout on first call
                raise subprocess.TimeoutExpired(cmd=["fake"], timeout=timeout)
            return ("partial", "err")

        def kill(self):
            self._killed = True

        def wait(self):
            return 1

    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    with pytest.raises(subprocess.TimeoutExpired):
        ex.run_cmd(["fake"], timeout=0.01)


def test_run_cmd_writes_filebase(monkeypatch, tmp_path):
    class FakePopen:
        def __init__(
            self,
            cmd,
            stdout,
            stderr,
            text,
            encoding,
            errors,
            startupinfo=None,
        ):
            self.returncode = 0

        def communicate(self, timeout=None):
            return ("OUTTEXT", "ERRTEXT")

    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    fb = tmp_path / "fb"
    ex.run_cmd(["echo"], filebase=fb)
    assert (fb.with_suffix(".out")).exists()
    assert (fb.with_suffix(".err")).exists()
    assert fb.with_suffix(".out").read_text() == "OUTTEXT"


def test_run_cmd_stream_stream_to_file_and_parser_exception(monkeypatch, tmp_path):
    class FakePopen:
        def __init__(
            self,
            cmd,
            stdout,
            stderr,
            text,
            encoding,
            errors,
            startupinfo=None,
        ):
            self.stdout = iter(["line1\n", "badpercent%\n"])
            self.returncode = 0

        def wait(self):
            return 0

    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    def bad_parser(line):
        raise ValueError("bad")

    outp = tmp_path / "stream"
    ex.run_cmd_stream(["fake"], parser=bad_parser, stream_to_file=outp)
    # stream file should be written
    assert outp.with_suffix(".out").exists()
    assert "line1" in outp.with_suffix(".out").read_text()


def test_cancel_current_process_returns_false_when_none():
    # ensure registered processes cleared
    # unregister any existing ones for the test
    with ex._LOCK:
        ex._RUNNING_PROCESSES.clear()
    assert ex.cancel_current_process() is False


def test_choose_duplicate_target_collision_loop(tmp_path):
    src = tmp_path / "s.bin"
    dst = tmp_path / "d.bin"
    src.write_text("x")
    dst.write_text("yy")
    # create existing copies _COPY_1 and _COPY_2
    (dst.parent / (dst.stem + "_COPY_1" + dst.suffix)).write_text("c1")
    (dst.parent / (dst.stem + "_COPY_2" + dst.suffix)).write_text("c2")

    args = SimpleNamespace(dup_check="fast")

    new = fo._choose_duplicate_target(
        src, dst, args, lambda p: "h", logger=SimpleLogger()
    )
    assert new.name.endswith("_COPY_3" + dst.suffix)


def test_copy_and_replace_cleanup_on_copy_failure(monkeypatch, tmp_path):
    src = tmp_path / "a.bin"
    src.write_bytes(b"data")
    dest = tmp_path / "b.bin"

    args = SimpleNamespace(dup_check="fast")

    # force shutil.copy2 to raise
    def fake_copy2(s, d):
        raise OSError("fail")

    monkeypatch.setattr(shutil, "copy2", fake_copy2)

    ok = fo._copy_and_replace(
        src, dest, tmp_path, args, lambda p: "h", logger=SimpleLogger()
    )
    assert ok is False
    # no tmp files left
    assert not any(p.name.startswith(".emumgr_tmp_") for p in tmp_path.iterdir())


def test_verify_hashes_exception():
    def bad_hash(p):
        raise RuntimeError("boom")

    ok = fo._verify_hashes(Path("a"), Path("b"), bad_hash, logger=SimpleLogger())
    assert ok is False


def test_safe_unlink_permission(monkeypatch, tmp_path):
    p = tmp_path / "z.bin"
    p.write_text("x")

    logger = SimpleLogger()

    def raise_perm(self):
        raise PermissionError("denied")

    monkeypatch.setattr(fo.Path, "unlink", raise_perm)
    fo.safe_unlink(p, logger)
    # should have logged a warning entry
    assert any(r[0] == "warning" for r in logger.records)
import subprocess
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

import emumanager.common.execution as ex
import emumanager.common.fileops as fo


class SimpleLogger:
    def __init__(self):
        self.records = []

    def info(self, *a, **k):
        self.records.append(("info", a))

    def debug(self, *a, **k):
        self.records.append(("debug", a))

    def warning(self, *a, **k):
        self.records.append(("warning", a))

    def exception(self, *a, **k):
        self.records.append(("exception", a))


def test_run_cmd_popen_timeout(monkeypatch):
    class FakePopen:
        def __init__(
            self,
            cmd,
            stdout,
            stderr,
            text,
            encoding,
            errors,
            startupinfo=None,
        ):
            self._killed = False
            self.returncode = None

        def communicate(self, timeout=None):
            if not self._killed and timeout is not None:
                # simulate timeout on first call
                raise subprocess.TimeoutExpired(cmd=["fake"], timeout=timeout)
            return ("partial", "err")

        def kill(self):
            self._killed = True

        def wait(self):
            return 1

    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    with pytest.raises(subprocess.TimeoutExpired):
        ex.run_cmd(["fake"], timeout=0.01)


def test_run_cmd_writes_filebase(monkeypatch, tmp_path):
    class FakePopen:
        def __init__(
            self,
            cmd,
            stdout,
            stderr,
            text,
            encoding,
            errors,
            startupinfo=None,
        ):
            self.returncode = 0

        def communicate(self, timeout=None):
            return ("OUTTEXT", "ERRTEXT")

    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    fb = tmp_path / "fb"
    ex.run_cmd(["echo"], filebase=fb)
    assert (fb.with_suffix(".out")).exists()
    assert (fb.with_suffix(".err")).exists()
    assert fb.with_suffix(".out").read_text() == "OUTTEXT"


def test_run_cmd_stream_stream_to_file_and_parser_exception(monkeypatch, tmp_path):
    class FakePopen:
        def __init__(
            self,
            cmd,
            stdout,
            stderr,
            text,
            encoding,
            errors,
            startupinfo=None,
        ):
            self.stdout = iter(["line1\n", "badpercent%\n"])
            self.returncode = 0

        def wait(self):
            return 0

    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    def bad_parser(line):
        raise ValueError("bad")

    outp = tmp_path / "stream"
    ex.run_cmd_stream(["fake"], parser=bad_parser, stream_to_file=outp)
    # stream file should be written
    assert outp.with_suffix(".out").exists()
    assert "line1" in outp.with_suffix(".out").read_text()


def test_cancel_current_process_returns_false_when_none():
    # ensure registered processes cleared
    # unregister any existing ones for the test
    with ex._LOCK:
        ex._RUNNING_PROCESSES.clear()
    assert ex.cancel_current_process() is False


def test_choose_duplicate_target_collision_loop(tmp_path):
    src = tmp_path / "s.bin"
    dst = tmp_path / "d.bin"
    src.write_text("x")
    dst.write_text("yy")
    # create existing copies _COPY_1 and _COPY_2
    (dst.parent / (dst.stem + "_COPY_1" + dst.suffix)).write_text("c1")
    (dst.parent / (dst.stem + "_COPY_2" + dst.suffix)).write_text("c2")

    args = SimpleNamespace(dup_check="fast")

    new = fo._choose_duplicate_target(
        src, dst, args, lambda p: "h", logger=SimpleLogger()
    )
    assert new.name.endswith("_COPY_3" + dst.suffix)


def test_copy_and_replace_cleanup_on_copy_failure(monkeypatch, tmp_path):
    src = tmp_path / "a.bin"
    src.write_bytes(b"data")
    dest = tmp_path / "b.bin"

    args = SimpleNamespace(dup_check="fast")

    # force shutil.copy2 to raise
    def fake_copy2(s, d):
        raise OSError("fail")

    monkeypatch.setattr(shutil, "copy2", fake_copy2)

    ok = fo._copy_and_replace(
        src, dest, tmp_path, args, lambda p: "h", logger=SimpleLogger()
    )
    assert ok is False
    # no tmp files left
    assert not any(p.name.startswith(".emumgr_tmp_") for p in tmp_path.iterdir())


def test_verify_hashes_exception():
    def bad_hash(p):
        raise RuntimeError("boom")

    ok = fo._verify_hashes(Path("a"), Path("b"), bad_hash, logger=SimpleLogger())
    assert ok is False


def test_safe_unlink_permission(monkeypatch, tmp_path):
    p = tmp_path / "z.bin"
    p.write_text("x")

    logger = SimpleLogger()

    def raise_perm(self):
        raise PermissionError("denied")

    monkeypatch.setattr(fo.Path, "unlink", raise_perm)
    fo.safe_unlink(p, logger)
    # should have logged a warning entry
    assert any(r[0] == "warning" for r in logger.records)
import os
import subprocess
import shutil
import tempfile
from pathlib import Path

import emumanager.common.execution as ex
import emumanager.common.fileops as fo


class SimpleLogger:
    def __init__(self):
        self.records = []

    def info(self, *a, **k):
        self.records.append(("info", a))

    def debug(self, *a, **k):
        self.records.append(("debug", a))

    def warning(self, *a, **k):
        self.records.append(("warning", a))

    def exception(self, *a, **k):
        self.records.append(("exception", a))


def test_run_cmd_popen_timeout(monkeypatch):
    class FakePopen:
        def __init__(self, cmd, stdout, stderr, text, encoding, errors, startupinfo=None):
            self._killed = False
            self.returncode = None

        def communicate(self, timeout=None):
            if not self._killed and timeout is not None:
                # simulate timeout on first call
                raise subprocess.TimeoutExpired(cmd=["fake"], timeout=timeout)
            return ("partial", "err")

        def kill(self):
            self._killed = True

        def wait(self):
            return 1

    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    with pytest.raises(subprocess.TimeoutExpired):
        ex.run_cmd(["fake"], timeout=0.01)


def test_run_cmd_writes_filebase(monkeypatch, tmp_path):
    class FakePopen:
        def __init__(self, cmd, stdout, stderr, text, encoding, errors, startupinfo=None):
            self.returncode = 0

        def communicate(self, timeout=None):
            return ("OUTTEXT", "ERRTEXT")

    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    fb = tmp_path / "fb"
    res = ex.run_cmd(["echo"], filebase=fb)
    assert (str(fb) + ".out") and (str(fb) + ".err")
    assert (fb.with_suffix(".out")).exists()
    assert (fb.with_suffix(".err")).exists()
    assert fb.with_suffix(".out").read_text() == "OUTTEXT"


def test_run_cmd_stream_stream_to_file_and_parser_exception(monkeypatch, tmp_path):
    class FakePopen:
        def __init__(self, cmd, stdout, stderr, text, encoding, errors, startupinfo=None):
            self.stdout = iter(["line1\n", "badpercent%\n"])
            self.returncode = 0

        def wait(self):
            return 0

    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    def bad_parser(line):
        raise ValueError("bad")

    outp = tmp_path / "stream"
    res = ex.run_cmd_stream(["fake"], parser=bad_parser, stream_to_file=outp)
    # stream file should be written
    assert outp.with_suffix(".out").exists()
    assert "line1" in outp.with_suffix(".out").read_text()


def test_cancel_current_process_returns_false_when_none():
    # ensure registered processes cleared
    # unregister any existing ones for the test
    with ex._LOCK:
        ex._RUNNING_PROCESSES.clear()
    assert ex.cancel_current_process() is False


def test_choose_duplicate_target_collision_loop(tmp_path):
    src = tmp_path / "s.bin"
    dst = tmp_path / "d.bin"
    src.write_text("x")
    dst.write_text("y")
    # create existing copies _COPY_1 and _COPY_2
    (dst.parent / (dst.stem + "_COPY_1" + dst.suffix)).write_text("c1")
    (dst.parent / (dst.stem + "_COPY_2" + dst.suffix)).write_text("c2")

    args = SimpleNamespace(dup_check="fast")

    new = fo._choose_duplicate_target(src, dst, args, lambda p: "h", logger=SimpleLogger())
    assert new.name.endswith("_COPY_3" + dst.suffix)


def test_copy_and_replace_cleanup_on_copy_failure(monkeypatch, tmp_path):
    src = tmp_path / "a.bin"
    src.write_bytes(b"data")
    dest = tmp_path / "b.bin"

    args = SimpleNamespace(dup_check="fast")

    # force shutil.copy2 to raise
    monkeypatch.setattr(shutil, "copy2", lambda s, d: (_ for _ in ()).throw(OSError("fail")))

    ok = fo._copy_and_replace(src, dest, tmp_path, args, lambda p: "h", logger=SimpleLogger())
    assert ok is False
    # no tmp files left
    assert not any(p.name.startswith(".emumgr_tmp_") for p in tmp_path.iterdir())


def test_verify_hashes_exception():
    def bad_hash(p):
        raise RuntimeError("boom")

    ok = fo._verify_hashes(Path("a"), Path("b"), bad_hash, logger=SimpleLogger())
    assert ok is False


def test_safe_unlink_permission(monkeypatch, tmp_path):
    p = tmp_path / "z.bin"
    p.write_text("x")

    logger = SimpleLogger()

    def raise_perm(self):
        raise PermissionError("denied")

    monkeypatch.setattr(fo.Path, "unlink", raise_perm)
    fo.safe_unlink(p, logger)
    # should have logged a warning entry
    assert any(r[0] == "warning" for r in logger.records)
