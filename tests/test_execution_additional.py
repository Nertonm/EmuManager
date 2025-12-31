import subprocess
from pathlib import Path

import emumanager.common.execution as ex


def test_cancel_current_process_kills_and_returns_true():
    class FakeProc:
        def __init__(self):
            self.killed = False
            self.terminated = False

        def kill(self):
            self.killed = True

        def terminate(self):
            self.terminated = True

    p = FakeProc()
    # register and ensure cancel returns True and kill used
    ex._register_process(p)  # use internal registration for test
    try:
        assert ex.cancel_current_process() is True
        assert p.killed or p.terminated
    finally:
        ex._unregister_process(p)


def test_find_tool_uses_shutil_which(monkeypatch, tmp_path):
    # prefer shutil.which when available
    monkeypatch.setattr("shutil.which", lambda name: "/bin/echo")
    p = ex.find_tool("echo")
    assert p is not None
    assert p.name == "echo"

    # fallback to local file when which returns None
    monkeypatch.setattr("shutil.which", lambda name: None)
    oldcwd = Path.cwd()
    try:
        tmp = tmp_path / "mytool"
        tmp.write_text("x")
        # change cwd so ./mytool exists
        import os

        os.chdir(tmp_path)
        p2 = ex.find_tool("mytool")
        assert p2 is not None
        assert p2.resolve() == tmp.resolve()
    finally:
        os.chdir(oldcwd)


def test_run_cmd_uses_monkeypatched_subprocess_run_and_check(monkeypatch):
    # fake subprocess.run to simulate CompletedProcess
    def fake_run(cmd, stdout=None, stderr=None):
        return subprocess.CompletedProcess(cmd, 0, stdout="OUT", stderr="ERR")

    monkeypatch.setattr(subprocess, "run", fake_run)
    res = ex.run_cmd(["echo", "x"])  # should go through subprocess.run path
    assert isinstance(res, subprocess.CompletedProcess)
    assert res.stdout == "OUT"

    # when returncode non-zero and check=True, raise CalledProcessError
    def fake_run_fail(cmd, stdout=None, stderr=None):
        return subprocess.CompletedProcess(cmd, 2, stdout="", stderr="err")

    monkeypatch.setattr(subprocess, "run", fake_run_fail)
    try:
        import pytest

        with pytest.raises(subprocess.CalledProcessError):
            ex.run_cmd(["false"], check=True)
    finally:
        # restore nothing; monkeypatch handles teardown
        pass


def test_run_cmd_stream_with_fake_popen_reports_progress(monkeypatch):
    # Create a fake Popen that yields lines including percent values
    class FakePopen:
        def __init__(
            self, cmd, stdout, stderr, text, encoding, errors, startupinfo=None
        ):
            self.returncode = 0
            # simulate file-like stdout iterator
            self._lines = ["10%\n", "20%\n", "20%\n", "100%\n"]
            self.stdout = iter(self._lines)

        def wait(self):
            return 0

    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    calls = []

    def prog(pct, line):
        calls.append((pct, line))

    res = ex.run_cmd_stream(["fake"], progress_cb=prog)
    assert isinstance(res, subprocess.CompletedProcess)
    # progress should have been emitted at least for 10%, 20% and 100%
    assert any(abs(p - 0.1) < 1e-6 for p, _ in calls)
    assert any(abs(p - 0.2) < 1e-6 for p, _ in calls)
    assert any(abs(p - 1.0) < 1e-6 for p, _ in calls)


def test_run_cmd_stream_prefers_subprocess_run_when_monkeypatched(monkeypatch):
    # monkeypatch subprocess.run to execute fast path
    def fake_run(cmd, stdout=None, stderr=None):
        return subprocess.CompletedProcess(cmd, 0, stdout="line1\n50%\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    res = ex.run_cmd_stream(["fake"])
    assert isinstance(res, subprocess.CompletedProcess)
    assert "line1" in (res.stdout or "")
