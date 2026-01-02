from typer.testing import CliRunner

from emumanager import tui


runner = CliRunner()


def test_help_shows_commands():
    result = runner.invoke(tui.app, ["--help"])
    assert result.exit_code == 0
    # Ensure a few key commands are listed
    assert "organize" in result.stdout
    assert "tui" in result.stdout
    assert "tui-full" in result.stdout


def test_tui_menu_quick_exit(tmp_path):
    # Should render menu and exit cleanly when user selects 0
    result = runner.invoke(tui.app, ["tui", "--base", str(tmp_path)], input="0\n")
    assert result.exit_code == 0
    assert "EmuManager :: TUI" in result.stdout
