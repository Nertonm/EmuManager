import subprocess
import sys
from pathlib import Path

import pytest

from emumanager.common import execution


def test_run_cmd_timeout_raises():
    # This command sleeps longer than the timeout -> should raise TimeoutExpired
    cmd = [sys.executable, "-c", "import time; time.sleep(0.2)"]
    with pytest.raises(subprocess.TimeoutExpired):
        execution.run_cmd(cmd, timeout=0.01)


def test_run_cmd_stream_stream_to_file(tmp_path: Path):
    # This command writes two lines with a tiny sleep between them
    cmd = [
        sys.executable,
        "-c",
        (
            "import sys, time; print('line1'); sys.stdout.flush(); "
            "time.sleep(0.02); print('line2')"
        ),
    ]

    out_path = tmp_path / "stream_test"
    res = execution.run_cmd_stream(cmd, stream_to_file=out_path)
    assert isinstance(res, subprocess.CompletedProcess)

    out_file = out_path.with_suffix(".out")
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "line1" in content
    assert "line2" in content


def test_cancel_current_process_kills_running_process():
    # Start a long-running command in a background thread using run_cmd
    import threading

    def target():
        try:
            execution.run_cmd([sys.executable, "-c", "import time; time.sleep(5)"])
        except Exception:
            # run_cmd may raise if killed; ignore for the purpose of this test
            pass

    t = threading.Thread(target=target)
    t.start()

    # Give it a moment to start and register
    import time

    time.sleep(0.05)

    cancelled = execution.cancel_current_process()
    assert cancelled is True

    t.join(timeout=1.0)
    assert not t.is_alive()
