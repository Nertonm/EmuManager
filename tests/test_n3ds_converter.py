import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from emumanager.converters.n3ds_converter import compress_to_7z, decompress_7z


@pytest.fixture
def mock_find_tool():
    with patch("emumanager.converters.n3ds_converter.find_tool") as m:
        yield m


@pytest.fixture
def mock_run_cmd():
    with patch("emumanager.converters.n3ds_converter.run_cmd") as m:
        yield m


def test_compress_to_7z_no_tool(mock_find_tool):
    mock_find_tool.return_value = None
    with pytest.raises(FileNotFoundError):
        compress_to_7z(Path("game.3ds"), Path("game.7z"))


def test_compress_to_7z_success(mock_find_tool, mock_run_cmd):
    mock_find_tool.return_value = Path("/usr/bin/7z")
    mock_run_cmd.return_value = MagicMock(returncode=0)
    
    # Mock exists to return True for dest
    with patch("pathlib.Path.exists", return_value=True):
        res = compress_to_7z(Path("game.3ds"), Path("game.7z"))
        assert res is True
        mock_run_cmd.assert_called_once()
        cmd = mock_run_cmd.call_args[0][0]
        assert cmd[0] == "/usr/bin/7z"
        assert "a" in cmd
        assert "-t7z" in cmd


def test_decompress_7z_success(mock_find_tool, mock_run_cmd):
    mock_find_tool.return_value = Path("/usr/bin/7z")
    mock_run_cmd.return_value = MagicMock(returncode=0)

    res = decompress_7z(Path("game.7z"), Path("out_dir"))
    assert res is True
    mock_run_cmd.assert_called_once()
    cmd = mock_run_cmd.call_args[0][0]
    assert cmd[0] == "/usr/bin/7z"
    assert "x" in cmd
