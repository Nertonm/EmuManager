import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from emumanager.core.dat_manager import DATManager

class TestDATManager:
    @pytest.fixture
    def mock_downloader(self):
        return MagicMock()

    @pytest.fixture
    def manager(self, tmp_path, mock_downloader):
        with patch("emumanager.core.dat_manager.DatDownloader", return_value=mock_downloader):
            return DATManager(tmp_path)

    def test_update_all_sources_empty(self, manager, mock_downloader):
        # Arrange
        mock_downloader.list_available_dats.return_value = []
        manager.logger = MagicMock()
        
        # Act
        count = manager.update_all_sources()
        
        # Assert
        assert count == 0
        manager.logger.warning.assert_called_with("Nenhum DAT disponível para download.")

    def test_update_all_sources_success(self, manager, mock_downloader):
        # Arrange
        mock_downloader.list_available_dats.return_value = ["dat1.dat", "dat2.dat"]
        
        # Simulate downloader calling the progress callback for each file
        def mock_download_all(source, max_workers, progress_callback):
            progress_callback("dat1.dat", 1, 2)
            progress_callback("dat2.dat", 2, 2)
            return 2
        mock_downloader.download_all.side_effect = mock_download_all
        
        progress_calls = []
        def progress_cb(p, m):
            progress_calls.append((p, m))
            
        # Act
        count = manager.update_all_sources(progress_cb=progress_cb)
        
        # Assert
        assert count == 4 # 2 sources * 2 files each
        assert len(progress_calls) == 4
        assert progress_calls[-1][0] == 1.0
        assert "redump" in progress_calls[-1][1]

    @patch("emumanager.verification.dat_manager.find_dat_for_system")
    def test_find_dat_for_system_delegation(self, mock_find, manager):
        # Arrange
        mock_find.return_value = Path("/path/to/my.dat")
        
        # Act
        result = manager.find_dat_for_system("ps2")
        
        # Assert
        assert result == Path("/path/to/my.dat")
        mock_find.assert_called_with(manager.dats_root, "ps2")
