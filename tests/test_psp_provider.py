import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from emumanager.psp.provider import PSPProvider

class TestPSPProvider:
    @pytest.fixture
    def provider(self):
        return PSPProvider()

    def test_basic_properties(self, provider):
        assert provider.system_id == "psp"
        assert ".pbp" in provider.get_supported_extensions()

    @patch("emumanager.psp.provider.metadata")
    @patch("emumanager.psp.provider.database")
    def test_extract_metadata_success(self, mock_db, mock_meta, provider):
        # Arrange
        mock_meta.get_metadata.return_value = {
            "serial": "ULUS-10041",
            "title": "Lumines"
        }
        mock_db.db.get_title.return_value = "Lumines: Puzzle Fusion"
        
        # Act
        meta = provider.extract_metadata(Path("game.iso"))
        
        # Assert
        assert meta["serial"] == "ULUS-10041"
        assert meta["title"] == "Lumines: Puzzle Fusion"

    def test_needs_conversion(self, provider):
        assert provider.needs_conversion(Path("game.iso")) is True
        assert provider.needs_conversion(Path("game.cso")) is False
        assert provider.needs_conversion(Path("EBOOT.PBP")) is False
