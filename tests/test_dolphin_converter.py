import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from emumanager.converters.dolphin_converter import DolphinConverter

@pytest.fixture
def mock_find_tool(monkeypatch):
    mock = MagicMock(return_value=Path("/usr/bin/dolphin-tool"))
    monkeypatch.setattr("emumanager.converters.dolphin_converter.find_tool", mock)
    return mock

@pytest.fixture
def converter(mock_find_tool):
    return DolphinConverter()

def test_check_tool_found(converter):
    assert converter.check_tool() is True

def test_check_tool_not_found(monkeypatch):
    monkeypatch.setattr("emumanager.converters.dolphin_converter.find_tool", lambda x: None)
    conv = DolphinConverter()
    assert conv.check_tool() is False

@patch("emumanager.converters.dolphin_converter.run_cmd")
def test_convert_to_rvz_success(mock_run_cmd, converter, tmp_path):
    input_file = tmp_path / "game.iso"
    input_file.touch()
    output_file = tmp_path / "game.rvz"
    output_file.touch() # Simulate creation
    
    mock_run_cmd.return_value = MagicMock(returncode=0)
    
    assert converter.convert_to_rvz(input_file, output_file) is True
    
    args = mock_run_cmd.call_args[0][0]
    assert args[1] == "convert"
    # args[2] is -i, args[3] is input
    # args[4] is -o, args[5] is output
    # args[6] is -f, args[7] is rvz
    assert args[6] == "-f"
    assert args[7] == "rvz"

@patch("emumanager.converters.dolphin_converter.run_cmd")
def test_verify_rvz_success(mock_run_cmd, converter, tmp_path):
    rvz_file = tmp_path / "game.rvz"
    rvz_file.touch()
    
    mock_run_cmd.return_value = MagicMock(returncode=0)
    
    assert converter.verify_rvz(rvz_file) is True
    
    args = mock_run_cmd.call_args[0][0]
    assert args[1] == "verify"

@patch("emumanager.converters.dolphin_converter.run_cmd")
def test_get_metadata_success(mock_run_cmd, converter, tmp_path):
    f = tmp_path / "game.iso"
    f.touch()
    
    mock_run_cmd.return_value = MagicMock(
        returncode=0,
        stdout=b"Game ID: GM4E01\nInternal Name: Mario Kart\nRevision: 0\n"
    )
    
    meta = converter.get_metadata(f)
    assert meta["game_id"] == "GM4E01"
    assert meta["internal_name"] == "Mario Kart"
    assert meta["revision"] == "0"
