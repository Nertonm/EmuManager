import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def test_gui_headless_smoke(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "emumanager_gui.py"

    if not script.exists():
        pytest.skip("GUI launcher script not found")

    xvfb = shutil.which("xvfb-run")
    has_display = "DISPLAY" in subprocess.os.environ

    # If no X server and no xvfb-run, skip test
    if not has_display and xvfb is None:
        pytest.skip(
            "No X server (DISPLAY) and xvfb-run not available; skipping GUI smoke test"
        )

    cmd = []
    # Prefer existing DISPLAY if available (avoids nesting xvfb-run)
    if has_display:
        cmd = [sys.executable, str(script), "--headless"]
    elif xvfb:
        cmd = [
            xvfb,
            "-s",
            "-screen 0 1024x768x24",
            sys.executable,
            str(script),
            "--headless",
        ]

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    # For debugging failures, include stdout/stderr in the assertion message
    assert proc.returncode == 0, (
        f"GUI smoke test failed (rc={proc.returncode})\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
