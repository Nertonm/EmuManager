import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path
from emumanager.workers.distributor import worker_distribute_root

@pytest.fixture
def mock_logger():
    return MagicMock()

@pytest.fixture
def mock_progress():
    return MagicMock()

@pytest.fixture
def mock_cancel_event():
    event = MagicMock()
    event.is_set.return_value = False
    return event

def test_distribute_root_no_files(tmp_path, mock_logger):
    """Test distribution when no files are present."""
    stats = worker_distribute_root(tmp_path, mock_logger)
    assert stats == {"moved": 0, "skipped": 0, "errors": 0}
    mock_logger.assert_any_call("No files found in root folder to distribute.")

def test_distribute_root_success(tmp_path, mock_logger, mock_progress):
    """Test successful distribution of files to system folders."""
    # Create dummy files
    (tmp_path / "game.iso").touch()  # Should go to ps2/gamecube/etc depending on guess
    (tmp_path / "game.nes").touch()  # Should go to nes
    
    # Mock guess_system_for_file to return specific systems
    with patch("emumanager.workers.distributor.guess_system_for_file") as mock_guess:
        mock_guess.side_effect = lambda p: "ps2" if p.suffix == ".iso" else "nes"
        
        stats = worker_distribute_root(tmp_path, mock_logger, mock_progress)
        
        assert stats["moved"] == 2
        assert (tmp_path / "ps2" / "game.iso").exists()
        assert (tmp_path / "nes" / "game.nes").exists()
        assert not (tmp_path / "game.iso").exists()
        
        # Verify progress callbacks
        assert mock_progress.call_count == 2

def test_distribute_root_skip_ignored(tmp_path, mock_logger):
    """Test skipping of ignored files."""
    (tmp_path / ".hidden").touch()
    (tmp_path / "_INSTALL_LOG.txt").touch()
    
    stats = worker_distribute_root(tmp_path, mock_logger)
    
    assert stats["skipped"] == 2
    assert stats["moved"] == 0
    assert (tmp_path / ".hidden").exists()

def test_distribute_root_unknown_system(tmp_path, mock_logger):
    """Test handling of files with unknown systems."""
    (tmp_path / "unknown.xyz").touch()
    
    with patch("emumanager.workers.distributor.guess_system_for_file", return_value=None):
        stats = worker_distribute_root(tmp_path, mock_logger)
        
        assert stats["skipped"] == 1
        assert stats["moved"] == 0
        mock_logger.assert_any_call("WARN: Could not determine system for: unknown.xyz")

def test_distribute_root_target_exists(tmp_path, mock_logger):
    """Test handling when target file already exists."""
    (tmp_path / "game.nes").touch()
    (tmp_path / "nes").mkdir()
    (tmp_path / "nes" / "game.nes").touch()
    
    with patch("emumanager.workers.distributor.guess_system_for_file", return_value="nes"):
        stats = worker_distribute_root(tmp_path, mock_logger)
        
        assert stats["skipped"] == 1
        assert stats["moved"] == 0
        # Check if any warning was logged
        assert any("WARN: " in str(call) for call in mock_logger.call_args_list)

def test_distribute_root_cancellation(tmp_path, mock_logger, mock_cancel_event):
    """Test cancellation of the worker."""
    (tmp_path / "game1.nes").touch()
    (tmp_path / "game2.nes").touch()
    
    # Cancel after first check
    mock_cancel_event.is_set.side_effect = [False, True]
    
    with patch("emumanager.workers.distributor.guess_system_for_file", return_value="nes"):
        stats = worker_distribute_root(tmp_path, mock_logger, progress_cb=None, cancel_event=mock_cancel_event)
        
        assert stats["moved"] == 1
        mock_logger.assert_any_call("WARN: Distribution cancelled.")

def test_distribute_root_error_listing(tmp_path, mock_logger):
    """Test error handling when listing directory fails."""
    # Mock iterdir to raise exception
    with patch.object(Path, "iterdir", side_effect=PermissionError("Access denied")):
        stats = worker_distribute_root(tmp_path, mock_logger)
        assert stats["errors"] == 1
        # Check for error log
        assert any("ERROR: " in str(call) for call in mock_logger.call_args_list)
