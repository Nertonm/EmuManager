import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from emumanager.n3ds.provider import N3DSProvider

class TestN3DSProvider:
    @pytest.fixture
    def provider(self):
        return N3DSProvider()

    def test_basic_properties(self, provider):
        assert provider.system_id == "3ds"
        assert ".cia" in provider.get_supported_extensions()

    @patch("emumanager.n3ds.provider.metadata")
    def test_extract_metadata_success(self, mock_meta, provider):
        # Arrange
        mock_meta.get_metadata.return_value = {"serial": "CTR-P-AGME"}
        
        # Act
        meta = provider.extract_metadata(Path("Luigi.3ds"))
        
        # Assert
        assert meta["serial"] == "CTR-P-AGME"
        assert meta["title"] == "Luigi"

    def test_needs_conversion(self, provider):
        # 3DS doesn't have a specific conversion flow in provider yet
        assert provider.needs_conversion(Path("game.3ds")) is False
