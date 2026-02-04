import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from emumanager.switch.provider import SwitchProvider

class TestSwitchProvider:
    @pytest.fixture
    def provider(self):
        return SwitchProvider()

    @patch("emumanager.switch.provider.metadata")
    def test_extract_metadata_categorization(self, mock_meta, provider):
        with patch("emumanager.switch.provider.validate_path_exists") as mock_val:
            mock_val.side_effect = lambda p, *args, **kwargs: Path(p)
            
            # Case 1: Base Game
            mock_meta.get_metadata_minimal.return_value = {
                "title_id": "0100000000010000",
                "title": "Super Mario Odyssey"
            }
            meta = provider.extract_metadata(Path("game.nsp"))
            assert meta["category"] == "Base Games"
            
            # Case 2: Update
            mock_meta.get_metadata_minimal.return_value = {
                "title_id": "0100000000010800",
                "title": "Super Mario Odyssey"
            }
            meta = provider.extract_metadata(Path("update.nsp"))
            assert meta["category"] == "Updates"

            # Case 3: DLC
            mock_meta.get_metadata_minimal.return_value = {
                "title_id": "0100000000010001",
                "title": "Extra Content"
            }
            meta = provider.extract_metadata(Path("dlc.nsp"))
            assert meta["category"] == "DLCs"

    def test_get_ideal_filename_structure(self, provider):
        # Arrange
        path = Path("mario.nsz")
        meta = {
            "title": "Mario",
            "serial": "0100ABC",
            "version": "1.0",
            "category": "Base Games"
        }
        
        # Act
        result = provider.get_ideal_filename(path, meta)
        
        # Assert
        expected = str(Path("Base Games") / "Mario" / "Mario [0100ABC] [v1.0].nsz")
        assert result == expected

    def test_needs_conversion(self, provider):
        assert provider.needs_conversion(Path("game.nsp")) is True
        assert provider.needs_conversion(Path("game.nsz")) is False
        assert provider.needs_conversion(Path("game.xci")) is True
        assert provider.needs_conversion(Path("game.xcz")) is False
