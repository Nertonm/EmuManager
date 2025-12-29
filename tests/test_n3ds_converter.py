import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from emumanager.converters.n3ds_converter import (
    compress_to_7z,
    convert_to_cia,
    decompress_7z,
    decrypt_3ds,
)


@pytest.fixture
def mock_find_tool():
    with patch("emumanager.converters.n3ds_converter.find_tool") as m:
        yield m


@pytest.fixture
def mock_run_tool_with_progress():
    with patch("emumanager.converters.n3ds_converter._run_tool_with_progress") as m:
        yield m


def test_compress_to_7z_no_tool(mock_find_tool):
    mock_find_tool.return_value = None
    with pytest.raises(FileNotFoundError):
        compress_to_7z(Path("game.3ds"), Path("game.7z"))


def test_compress_to_7z_success(mock_find_tool, mock_run_tool_with_progress):
    mock_find_tool.return_value = Path("/usr/bin/7z")
    mock_run_tool_with_progress.return_value = True

    # Mock exists to return True for dest
    with patch("pathlib.Path.exists", return_value=True):
        res = compress_to_7z(Path("game.3ds"), Path("game.7z"))
        assert res is True
        mock_run_tool_with_progress.assert_called_once()
        cmd = mock_run_tool_with_progress.call_args[0][0]
        assert cmd[0] == "/usr/bin/7z"
        assert "a" in cmd
        assert "-t7z" in cmd


def test_decompress_7z_success(mock_find_tool, mock_run_tool_with_progress):
    mock_find_tool.return_value = Path("/usr/bin/7z")
    mock_run_tool_with_progress.return_value = True

    res = decompress_7z(Path("game.7z"), Path("out_dir"))
    assert res is True
    mock_run_tool_with_progress.assert_called_once()
    cmd = mock_run_tool_with_progress.call_args[0][0]
    assert cmd[0] == "/usr/bin/7z"
    assert "x" in cmd


def test_decrypt_3ds_no_tool(mock_find_tool):
    mock_find_tool.return_value = None
    with pytest.raises(FileNotFoundError):
        decrypt_3ds(Path("game.3ds"), Path("game_dec.3ds"))


def test_convert_to_cia_success(mock_find_tool, mock_run_tool_with_progress):
    mock_find_tool.side_effect = lambda x: Path(f"/usr/bin/{x}") if x == "3dsconv" else None
    mock_run_tool_with_progress.return_value = True

    with patch("pathlib.Path.exists", return_value=True):
        res = convert_to_cia(Path("game.3ds"), Path("game.cia"))
        assert res is True
        mock_run_tool_with_progress.assert_called_once()
        cmd = mock_run_tool_with_progress.call_args[0][0]
        assert cmd[0] == "/usr/bin/3dsconv"
