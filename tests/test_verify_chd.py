from pathlib import Path

from emumanager.workers import common


class DummyRes:
    def __init__(self, rc=0, stdout=""):
        self.returncode = rc
        self.stdout = stdout


def test_verify_chd_tool_missing(monkeypatch, tmp_path):
    # Simulate find_tool returning None
    monkeypatch.setattr(common, "find_tool", lambda name: None)
    ok = common.verify_chd(tmp_path / "game.chd")
    assert ok is False


def test_verify_chd_success_by_returncode(monkeypatch, tmp_path):
    # Simulate find_tool present and run_cmd returning rc 0
    monkeypatch.setattr(common, "find_tool", lambda name: Path("/usr/bin/chdman"))

    def fake_run_cmd(cmd, timeout=None):
        return DummyRes(rc=0, stdout="verify: OK")

    monkeypatch.setattr(common, "run_cmd", fake_run_cmd)
    ok = common.verify_chd(tmp_path / "game.chd")
    assert ok is True


def test_verify_chd_success_by_stdout(monkeypatch, tmp_path):
    # Simulate non-zero rc but stdout contains 'verify ok'
    monkeypatch.setattr(common, "find_tool", lambda name: Path("/usr/bin/chdman"))

    def fake_run_cmd(cmd, timeout=None):
        return DummyRes(rc=1, stdout="Verify OK: header matches")

    monkeypatch.setattr(common, "run_cmd", fake_run_cmd)
    ok = common.verify_chd(tmp_path / "game.chd")
    assert ok is True


def test_verify_chd_failure(monkeypatch, tmp_path):
    # Simulate non-zero rc and no success text
    monkeypatch.setattr(common, "find_tool", lambda name: Path("/usr/bin/chdman"))

    def fake_run_cmd(cmd, timeout=None):
        return DummyRes(rc=2, stdout="error: corrupt header")

    monkeypatch.setattr(common, "run_cmd", fake_run_cmd)
    ok = common.verify_chd(tmp_path / "game.chd")
    assert ok is False
