import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from emumanager.core.integrity import IntegrityManager
from emumanager.core.models import IntegrityEvent

class TestIntegrityManager:
    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def manager(self, tmp_path, mock_db):
        return IntegrityManager(tmp_path, mock_db)

    def test_quarantine_file_physical_move(self, manager, tmp_path):
        # Arrange
        rom_dir = tmp_path / "roms" / "nes"
        rom_dir.mkdir(parents=True)
        rom_file = rom_dir / "bad_game.nes"
        rom_file.write_text("corrupt data")
        
        # Act
        dest = manager.quarantine_file(rom_file, "nes", "Corruption", "Hash mismatch")
        
        # Assert
        assert not rom_file.exists()
        assert dest.exists()
        assert "_QUARANTINE" in str(dest)
        assert "nes" in str(dest)
        manager.db.log_action.assert_called()

    def test_quarantine_file_updates_db(self, manager, tmp_path):
        # Arrange
        rom_file = tmp_path / "game.nes"
        rom_file.touch()
        mock_entry = MagicMock()
        manager.db.get_entry.return_value = mock_entry
        
        # Act
        manager.quarantine_file(rom_file, "nes", "Corruption", "Details")
        
        # Assert
        manager.db.remove_entry.assert_called()
        manager.db.update_entry.assert_called()
        assert mock_entry.status == "QUARANTINED"

    def test_restore_file_success(self, manager, tmp_path):
        # Arrange
        quar_dir = tmp_path / "_QUARANTINE" / "nes"
        quar_dir.mkdir(parents=True)
        q_file = quar_dir / "game.nes"
        q_file.touch()
        
        target_dir = tmp_path / "roms" / "nes"
        
        # Act
        success = manager.restore_file(q_file, target_dir)
        
        # Assert
        assert success is True
        assert not q_file.exists()
        assert (target_dir / "game.nes").exists()
        manager.db.log_action.assert_called()

    def test_restore_file_not_found(self, manager, tmp_path):
        # Act
        success = manager.restore_file(Path("/non/existent"), tmp_path)
        
        # Assert
        assert success is False

    def test_subscription_and_emission(self, manager, tmp_path):
        # Arrange
        callback = MagicMock()
        manager.subscribe(callback)
        
        event = IntegrityEvent(
            path=Path("test"), 
            system="nes", 
            issue_type="Corruption", 
            severity="High", 
            details="Test"
        )
        
        # Act
        manager._emit(event)
        
        # Assert
        callback.assert_called_with(event)
