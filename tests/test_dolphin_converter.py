import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from emumanager.converters.dolphin_converter import DolphinConverter

@pytest.fixture
def mock_logger():
    return MagicMock()

@pytest.fixture
def converter(mock_logger):
    with patch("emumanager.converters.dolphin_converter.find_tool") as mock_find:
        mock_find.return_value = Path("/usr/bin/dolphin-tool")
        conv = DolphinConverter(logger=mock_logger)
        return conv

def test_init_finds_tool(mock_logger):
    with patch("emumanager.converters.dolphin_converter.find_tool") as mock_find:
        mock_find.return_value = Path("/usr/bin/dolphin-tool")
        conv = DolphinConverter(logger=mock_logger)
        assert conv.dolphin_tool == Path("/usr/bin/dolphin-tool")
        assert not conv.use_flatpak

def test_init_finds_flatpak(mock_logger):
    with patch("emumanager.converters.dolphin_converter.find_tool", return_value=None), \
         patch("shutil.which", return_value="/usr/bin/flatpak"), \
         patch("emumanager.converters.dolphin_converter.run_cmd") as mock_run:
        
        mock_run.return_value.returncode = 0
        conv = DolphinConverter(logger=mock_logger)
        
        assert conv.use_flatpak
        assert conv.dolphin_tool == Path("/usr/bin/flatpak")
        mock_logger.info.assert_called_with("Using Dolphin via Flatpak")

def test_check_tool(converter):
    assert converter.check_tool() is True
    
    converter.dolphin_tool = None
    assert converter.check_tool() is False

def test_get_base_cmd_native(converter):
    cmd = converter._get_base_cmd()
    assert cmd == ["/usr/bin/dolphin-tool"]

def test_get_base_cmd_flatpak(mock_logger):
    with patch("emumanager.converters.dolphin_converter.find_tool", return_value=None), \
         patch("shutil.which", return_value="/usr/bin/flatpak"), \
         patch("emumanager.converters.dolphin_converter.run_cmd") as mock_run:
        
        mock_run.return_value.returncode = 0
        conv = DolphinConverter(logger=mock_logger)
        
        paths = [Path("/path/to/roms"), Path("/path/to/output")]
        cmd = conv._get_base_cmd(paths)
        
        assert cmd[0] == "/usr/bin/flatpak"
        assert cmd[1] == "run"
        assert "--command=dolphin-tool" in cmd
        assert "org.DolphinEmu.dolphin-emu" in cmd
        # Check filesystem permissions
        assert any(f"--filesystem={p.resolve()}" in cmd for p in paths)

def test_convert_to_rvz_success(converter, tmp_path):
    with patch("emumanager.converters.dolphin_converter.run_cmd") as mock_run:
        mock_run.return_value.returncode = 0
        
        input_file = tmp_path / "game.iso"
        output_file = tmp_path / "game.rvz"
        
        # Simulate output file creation
        output_file.touch()
        
        result = converter.convert_to_rvz(input_file, output_file)
        
        assert result is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "convert" in args
        assert "-f" in args
        assert "rvz" in args

def test_convert_to_rvz_failure(converter, tmp_path):
    with patch("emumanager.converters.dolphin_converter.run_cmd") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Error"
        
        input_file = tmp_path / "game.iso"
        output_file = tmp_path / "game.rvz"
        
        result = converter.convert_to_rvz(input_file, output_file)
        
        assert result is False
        converter.logger.error.assert_any_call("Conversion failed with code 1")

def test_convert_to_iso_success(converter, tmp_path):
    with patch("emumanager.converters.dolphin_converter.run_cmd") as mock_run:
        mock_run.return_value.returncode = 0
        
        input_file = tmp_path / "game.rvz"
        output_file = tmp_path / "game.iso"
        output_file.touch()
        
        result = converter.convert_to_iso(input_file, output_file)
        
        assert result is True
        args = mock_run.call_args[0][0]
        assert "convert" in args
        assert "-f" in args
        assert "iso" in args