import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from emumanager.gamecube.provider import GameCubeProvider

class TestGameCubeProvider:
    @pytest.fixture
    def provider(self):
        return GameCubeProvider()

    def test_basic_properties(self, provider):
        assert provider.system_id == "dolphin"
        assert ".rvz" in provider.get_supported_extensions()

    @patch("emumanager.gamecube.provider.metadata")
    def test_extract_metadata_success(self, mock_meta, provider):
        # Arrange
        mock_meta.get_metadata.return_value = {
            "game_id": "GALE01",
            "internal_name": "Super Smash Bros. Melee"
        }
        
        # Act
        meta = provider.extract_metadata(Path("ssbm.iso"))
        
        # Assert
        assert meta["serial"] == "GALE01"
        assert "Smash Bros" in meta["title"]

    def test_needs_conversion(self, provider):
        assert provider.needs_conversion(Path("game.iso")) is True
        assert provider.needs_conversion(Path("game.gcm")) is True
        assert provider.needs_conversion(Path("game.rvz")) is False
