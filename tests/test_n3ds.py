import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from emumanager.workers import n3ds

@patch("emumanager.n3ds.metadata.get_metadata")
@patch("emumanager.n3ds.database.db.get_title")
def test_n3ds_verify_found(mock_get_title, mock_get_meta, tmp_path):
    # Setup
    n3ds_dir = tmp_path / "roms" / "3ds"
    n3ds_dir.mkdir(parents=True)
    rom = n3ds_dir / "game.3ds"
    rom.touch()

    mock_get_meta.return_value = {"serial": "CTR-P-AGME"}
    mock_get_title.return_value = "Luigi's Mansion 2"

    log_cb = MagicMock()
    args = MagicMock()
    args.cancel_event.is_set.return_value = False
    args.deep_verify = False

    def list_files(p):
        return [rom]

    res = n3ds.worker_n3ds_verify(tmp_path, args, log_cb, list_files)
    
    assert "Identified: 1" in res
    assert "Unknown: 0" in res
    mock_get_meta.assert_called_with(rom)

@patch("emumanager.n3ds.metadata.get_metadata")
def test_n3ds_organize_rename(mock_get_meta, tmp_path):
    # Setup
    n3ds_dir = tmp_path / "roms" / "3ds"
    n3ds_dir.mkdir(parents=True)
    rom = n3ds_dir / "game.3ds"
    rom.touch()

    mock_get_meta.return_value = {"serial": "CTR-P-AGME"}
    
    # Mock DB to return title
    with patch("emumanager.n3ds.database.db.get_title", return_value="Luigi's Mansion 2"):
        log_cb = MagicMock()
        args = MagicMock()
        args.dry_run = False
        args.cancel_event.is_set.return_value = False

        def list_files(p):
            return [rom]

        res = n3ds.worker_n3ds_organize(tmp_path, args, log_cb, list_files)
        
        assert "Renamed: 1" in res
        expected_path = n3ds_dir / "Luigi's Mansion 2 [CTR-P-AGME].3ds"
        assert expected_path.exists()
        assert not rom.exists()
