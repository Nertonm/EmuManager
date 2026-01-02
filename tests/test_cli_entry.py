"""Small CLI smoke tests.

This file exists to ensure CLI entrypoints don't regress. It's intentionally
lightweight: we avoid running long workers and verify that help and basic
commands don't crash.
"""

from typer.testing import CliRunner


def test_emumanager_tui_help_smoke():
    from emumanager import tui

    runner = CliRunner()
    res = runner.invoke(tui.app, ["--help"])
    assert res.exit_code == 0
    # A few representative commands
    assert "scan" in res.stdout
    assert "verify" in res.stdout
    assert "tui" in res.stdout
