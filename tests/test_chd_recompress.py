import subprocess
from pathlib import Path
from unittest.mock import patch

from emumanager.workers.psx import worker_chd_recompress_single


class DummyArgs:
    pass


def test_chd_recompress_success(tmp_path, monkeypatch):
    chd = tmp_path / "game.chd"
    chd.write_bytes(b"dummy")

    # We'll simulate chdman by creating the expected tmp files
    # when subprocess.run is called
    def fake_run(cmd, stdout=None, stderr=None):
        # last arg is output filename
        if (
            "extract" in cmd[1]
            or "extractdvd" in cmd[1]
            or "extractcd" in cmd[1]
            or cmd[1] == "extract"
        ):
            out = cmd[-1]
            Path(out).write_bytes(b"ISO-DATA")
            return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")
        if "createdvd" in cmd[1] or "createcd" in cmd[1] or cmd[1] == "createdvd":
            out = cmd[-1]
            Path(out).write_bytes(b"CHD-DATA")
            return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")
        return subprocess.CompletedProcess(cmd, 1, stdout=b"", stderr=b"")

    # Mock find_tool to return a path
    with patch(
        "emumanager.common.execution.find_tool", return_value=Path("/usr/bin/chdman")
    ):
        with patch("subprocess.run", side_effect=fake_run):
            logs = []

            def logcb(s):
                logs.append(s)

            res = worker_chd_recompress_single(chd, DummyArgs(), logcb)

            assert "Recompressed" in res or "Recompressed:" in res


def test_chd_recompress_extract_fail(tmp_path, monkeypatch):
    chd = tmp_path / "game.chd"
    chd.write_bytes(b"dummy")

    def fake_run_fail(cmd, stdout=None, stderr=None):
        return subprocess.CompletedProcess(cmd, 1, stdout=b"", stderr=b"error")

    with patch(
        "emumanager.common.execution.find_tool", return_value=Path("/usr/bin/chdman")
    ):
        with patch("subprocess.run", side_effect=fake_run_fail):
            logs = []

            def logcb(s):
                logs.append(s)

            res = worker_chd_recompress_single(chd, DummyArgs(), logcb)
            assert "Error: chdman failed" in res
