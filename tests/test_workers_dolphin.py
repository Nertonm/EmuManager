import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path
from emumanager.workers.dolphin import worker_dolphin_convert, DOLPHIN_CONVERTIBLE_EXTENSIONS

@pytest.fixture
def mock_logger():
    return MagicMock()

@pytest.fixture
def mock_args():
    args = MagicMock()
    args.rm_originals = False
    args.progress_callback = MagicMock()
    args.cancel_event = MagicMock()
    args.cancel_event.is_set.return_value = False
    return args

@pytest.fixture
def mock_converter():
    with patch("emumanager.workers.dolphin.DolphinConverter") as mock:
        instance = mock.return_value
        instance.check_tool.return_value = True
        instance.convert_to_rvz.return_value = True
        yield instance

def test_dolphin_convert_no_targets(tmp_path, mock_logger, mock_args):
    """Test when no GameCube/Wii directories are found."""
    with patch("emumanager.workers.dolphin._resolve_dolphin_targets", return_value=[]):
        result = worker_dolphin_convert(tmp_path, mock_args, mock_logger, lambda p: [])
        assert result == "No GameCube or Wii directories found."

def test_dolphin_convert_tool_missing(tmp_path, mock_logger, mock_args, mock_converter):
    """Test when dolphin-tool is missing."""
    mock_converter.check_tool.return_value = False
    
    with patch("emumanager.workers.dolphin._resolve_dolphin_targets", return_value=[tmp_path]):
        result = worker_dolphin_convert(tmp_path, mock_args, mock_logger, lambda p: [])
        assert "Error: 'dolphin-tool' not found" in result

def test_dolphin_convert_success(tmp_path, mock_logger, mock_args, mock_converter):
    """Test successful conversion of files."""
    # Setup files
    iso_file = tmp_path / "game.iso"
    iso_file.touch()
    
    # Mock file listing
    def list_files(p):
        return [iso_file]
    
    with patch("emumanager.workers.dolphin._resolve_dolphin_targets", return_value=[tmp_path]):
        worker_dolphin_convert(tmp_path, mock_args, mock_logger, list_files)
        
        # Verify conversion called
        mock_converter.convert_to_rvz.assert_called_with(iso_file, iso_file.with_suffix(".rvz"))
        
        # Verify progress callback
        mock_args.progress_callback.assert_called()

def test_dolphin_convert_skip_existing(tmp_path, mock_logger, mock_args, mock_converter):
    """Test skipping conversion if RVZ already exists."""
    iso_file = tmp_path / "game.iso"
    rvz_file = tmp_path / "game.rvz"
    iso_file.touch()
    rvz_file.touch()
    
    def list_files(p):
        return [iso_file]
    
    with patch("emumanager.workers.dolphin._resolve_dolphin_targets", return_value=[tmp_path]):
        worker_dolphin_convert(tmp_path, mock_args, mock_logger, list_files)
        
        # Should NOT convert
        mock_converter.convert_to_rvz.assert_not_called()
        mock_logger.assert_any_call(f"Skipping {iso_file.name}, RVZ already exists.")

def test_dolphin_convert_rm_originals(tmp_path, mock_logger, mock_args, mock_converter):
    """Test removing original files after conversion."""
    mock_args.rm_originals = True
    iso_file = tmp_path / "game.iso"
    iso_file.touch()
    
    def list_files(p):
        return [iso_file]
    
    with patch("emumanager.workers.dolphin._resolve_dolphin_targets", return_value=[tmp_path]), \
         patch("emumanager.common.fileops.safe_unlink") as mock_unlink:
        
        worker_dolphin_convert(tmp_path, mock_args, mock_logger, list_files)
        
        mock_converter.convert_to_rvz.assert_called()
        # safe_unlink receives the GuiLogger instance, not our mock_logger callback
        # We can check if it was called with the file
        mock_unlink.assert_called()
        assert mock_unlink.call_args[0][0] == iso_file

def test_dolphin_convert_cancellation(tmp_path, mock_logger, mock_args, mock_converter):
    """Test cancellation during conversion loop."""
    files = [tmp_path / f"game{i}.iso" for i in range(3)]
    for f in files: f.touch()
    
    def list_files(p):
        return files
    
    # Cancel after first file
    mock_args.cancel_event.is_set.side_effect = [False, True, True]
    
    with patch("emumanager.workers.dolphin._resolve_dolphin_targets", return_value=[tmp_path]):
        worker_dolphin_convert(tmp_path, mock_args, mock_logger, list_files)
        
        # Should process at least one, but not all
        # Note: The loop checks cancel_event at start.
        # Iter 0: False -> Process
        # Iter 1: True -> Break
        assert mock_converter.convert_to_rvz.call_count == 1
        mock_logger.assert_any_call("WARN: Operation cancelled by user.")

def test_dolphin_convert_failure(tmp_path, mock_logger, mock_args, mock_converter):
    """Test handling of conversion failure."""
    mock_converter.convert_to_rvz.return_value = False
    mock_args.rm_originals = True
    
    iso_file = tmp_path / "game.iso"
    iso_file.touch()
    
    def list_files(p):
        return [iso_file]
    
    with patch("emumanager.workers.dolphin._resolve_dolphin_targets", return_value=[tmp_path]), \
         patch("emumanager.common.fileops.safe_unlink") as mock_unlink:
        
        worker_dolphin_convert(tmp_path, mock_args, mock_logger, list_files)
        
        # Should attempt convert
        mock_converter.convert_to_rvz.assert_called()
        # Should NOT delete original if failed
        mock_unlink.assert_not_called()
