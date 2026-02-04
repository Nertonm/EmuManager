import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from emumanager.core.scanner import Scanner
from emumanager.library import LibraryEntry

class TestScanner:
    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def mock_dat_manager(self):
        return MagicMock()

    @pytest.fixture
    def scanner(self, mock_db, mock_dat_manager):
        return Scanner(mock_db, mock_dat_manager)

    def test_get_system_directories(self, scanner, tmp_path):
        # Arrange
        (tmp_path / "nes").mkdir()
        (tmp_path / "snes").mkdir()
        (tmp_path / ".hidden").mkdir()
        (tmp_path / "file.txt").touch()
        
        # Act
        dirs = scanner._get_system_directories(tmp_path)
        
        # Assert
        names = [d.name for d in dirs]
        assert "nes" in names
        assert "snes" in names
        assert ".hidden" not in names
        assert len(dirs) == 2

    def test_check_needs_hashing(self, scanner):
        mock_stat = MagicMock(st_size=100, st_mtime=1000.0)
        
        # Case 1: No entry in DB -> Needs hashing
        assert scanner._check_needs_hashing(Path("test"), mock_stat, None, False) is True
        
        # Case 2: Deep scan forced -> Needs hashing
        mock_entry = MagicMock(size=100, mtime=1000.0)
        assert scanner._check_needs_hashing(Path("test"), mock_stat, mock_entry, True) is True
        
        # Case 3: Match size and mtime -> Skip hashing
        assert scanner._check_needs_hashing(Path("test"), mock_stat, mock_entry, False) is False
        
        # Case 4: Size changed -> Needs hashing
        mock_entry.size = 200
        assert scanner._check_needs_hashing(Path("test"), mock_stat, mock_entry, False) is True

    def test_extract_provider_metadata_error_handling(self, scanner):
        # Arrange
        mock_provider = MagicMock()
        mock_provider.extract_metadata.side_effect = Exception("Crash")
        scanner.logger = MagicMock()
        
        # Act
        meta = scanner._extract_provider_metadata(Path("test.nes"), mock_provider)
        
        # Assert
        assert meta == {}
        assert scanner.logger.debug.called

    @patch("emumanager.verification.hasher.calculate_hashes")
    def test_handle_verification_dat_match(self, mock_calc, scanner):
        # Arrange
        mock_calc.return_value = {"crc32": "1234", "sha1": "abc", "md5": "md5"}
        mock_dat_db = MagicMock()
        mock_match = MagicMock()
        mock_match.name = "Super Mario"
        mock_match.serial = "NES-SM"
        mock_dat_db.lookup.return_value = [mock_match]
        
        # Act
        _, info = scanner._handle_verification(
            Path("mario.nes"), None, mock_dat_db, True, {}, "nes"
        )
        
        # Assert
        assert info["status"] == "VERIFIED"
        assert info["match_name"] == "Super Mario"
        assert info["dat_name"] == "NES-SM"

    def test_cleanup_removed_entries(self, scanner):
        # Arrange
        existing = {"/path/old": MagicMock(), "/path/stay": MagicMock()}
        found = {"/path/stay"}
        stats = {"removed": 0}
        
        # Act
        scanner._cleanup_removed_entries(existing, found, stats)
        
        # Assert
        scanner.db.remove_entry.assert_called_with("/path/old")
        assert stats["removed"] == 1

    def test_scan_directory_full_flow(self, scanner, tmp_path):
        # Arrange
        nes_dir = tmp_path / "nes"
        nes_dir.mkdir()
        (nes_dir / "game.nes").touch()
        
        scanner.db.get_all_entries.return_value = []
        scanner.dat_manager.find_dat_for_system.return_value = None
        
        # Act
        with patch.object(scanner, "_process_system") as mock_proc:
            stats = scanner.scan_directory(tmp_path)
            
            # Assert
            assert mock_proc.called
            assert stats["added"] == 0 # Stats are updated inside _process_system
