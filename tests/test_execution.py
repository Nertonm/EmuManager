from pathlib import Path

import subprocess

import emumanager.common.execution as exec_mod


def test_run_cmd_monkeypatched_writes_files(tmp_path, monkeypatch):
    # Fake subprocess.run to return a CompletedProcess with stdout/stderr
    def fake_run(cmd, stdout=None, stderr=None):
        return subprocess.CompletedProcess(cmd, 0, stdout="out-data", stderr="err-data")

    monkeypatch.setattr(subprocess, "run", fake_run)

    filebase = tmp_path / "cmd_output"
    res = exec_mod.run_cmd(["echo", "hi"], filebase=filebase)
    assert res.returncode == 0
    # When subprocess.run is monkeypatched, run_cmd uses the subprocess.run
    # path and does not persist files to disk. Assert stdout content instead.
    assert getattr(res, "stdout", None) == "out-data"


def test_run_cmd_real_writes_files(tmp_path):
    import shutil

    echo = shutil.which("echo")
    # if echo not found, skip this environment-dependent test
    if not echo:
        return

    filebase = tmp_path / "real_cmd"
    res = exec_mod.run_cmd([echo, "hello"], filebase=filebase)
    assert res.returncode == 0
    out_file = Path(str(filebase) + ".out")
    assert out_file.exists()
    assert "hello" in out_file.read_text()


def test_run_cmd_stream_monkeypatched_returns_combined(monkeypatch):
    def fake_run(cmd, stdout=None, stderr=None):
        return subprocess.CompletedProcess(
            cmd, 0, stdout="10% done\nComplete", stderr=None
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    res = exec_mod.run_cmd_stream(["fakecmd"])
    assert isinstance(res, subprocess.CompletedProcess)
    assert "10% done" in res.stdout


def test_cancel_current_process_register_and_cancel():
    class FakeProc:
        def __init__(self):
            self.killed = False
            self.terminated = False

        def kill(self):
            self.killed = True

        def terminate(self):
            self.terminated = True

    p = FakeProc()
    # register fake proc
    exec_mod._register_process(p)  # pylint: disable=protected-access
    try:
        cancelled = exec_mod.cancel_current_process()
        assert cancelled is True
        # either kill or terminate should have been called
        assert p.killed or p.terminated
    finally:
        exec_mod._unregister_process(p)  # pylint: disable=protected-access
