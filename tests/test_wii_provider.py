import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from emumanager.wii.provider import WiiProvider

class TestWiiProvider:
    @pytest.fixture
    def provider(self):
        return WiiProvider()

    def test_basic_properties(self, provider):
        assert provider.system_id == "dolphin"
        assert ".wbfs" in provider.get_supported_extensions()

    @patch("emumanager.wii.provider.metadata")
    def test_extract_metadata_success(self, mock_meta, provider):
        # Arrange
        mock_meta.get_metadata.return_value = {
            "game_id": "RSBE01",
            "internal_name": "Super Smash Bros. Brawl"
        }
        
        # Act
        meta = provider.extract_metadata(Path("game.wbfs"))
        
        # Assert
        assert meta["serial"] == "RSBE01"
        assert "Brawl" in meta["title"]

    def test_needs_conversion(self, provider):
        assert provider.needs_conversion(Path("game.iso")) is True
        assert provider.needs_conversion(Path("game.wbfs")) is True
        assert provider.needs_conversion(Path("game.rvz")) is False
