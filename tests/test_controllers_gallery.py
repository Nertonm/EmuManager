import pytest
pytest.importorskip("PyQt6")
from unittest.mock import MagicMock, patch
from pathlib import Path
from emumanager.controllers.gallery import GalleryController

class TestGalleryController:
    @pytest.fixture
    def mock_mw(self):
        mw = MagicMock()
        mw.ui = MagicMock()
        mw._last_base = "/mock/base"
        mw.library_db = MagicMock()
        mw._qtwidgets = MagicMock()
        mw._qtcore = MagicMock()
        mw._Qt_enum = MagicMock()
        return mw

    def test_init_connects_signals(self, mock_mw):
        # Arrange & Act
        controller = GalleryController(mock_mw)
        
        # Assert
        mock_mw.ui.combo_gallery_system.currentIndexChanged.connect.assert_called()
        mock_mw.ui.btn_gallery_refresh.clicked.connect.assert_called_with(controller.populate_gallery)

    def test_on_gallery_system_changed_respects_guard(self, mock_mw):
        # Arrange
        controller = GalleryController(mock_mw)
        controller.populate_gallery = MagicMock()
        mock_mw._skip_list_side_effects = True
        
        # Act
        controller._on_gallery_system_changed(1)
        
        # Assert
        controller.populate_gallery.assert_not_called()

    def test_populate_gallery_no_base_aborts(self, mock_mw):
        # Arrange
        mock_mw._last_base = None
        controller = GalleryController(mock_mw)
        
        # Act
        controller.populate_gallery()
        
        # Assert
        mock_mw.ui.list_gallery.clear.assert_not_called()

    @patch("emumanager.controllers.gallery.CoverDownloader")
    def test_populate_gallery_starts_downloaders(self, mock_downloader_cls, mock_mw):
        # Arrange
        mock_mw.ui.combo_gallery_system.currentText.return_value = "nes"
        mock_entry = MagicMock()
        mock_entry.path = "/mock/base/roms/nes/game.nes"
        mock_mw.library_db.get_entries_by_system.return_value = [mock_entry]
        
        controller = GalleryController(mock_mw)
        
        # Act
        with patch("pathlib.Path.mkdir"): # Avoid real dir creation
            controller.populate_gallery()
        
        # Assert
        mock_mw.ui.list_gallery.clear.assert_called_once()
        mock_mw.ui.list_gallery.addItem.assert_called()
        mock_downloader_cls.assert_called()
        mock_mw._qtcore.QThreadPool.globalInstance().start.assert_called()

    def test_update_gallery_icon_skips_invalid_item(self, mock_mw):
        # Arrange
        controller = GalleryController(mock_mw)
        mock_item = MagicMock()
        mock_item.listWidget.return_value = None # Item was removed
        
        # Act
        controller._update_gallery_icon(mock_item, "/path/to/img.png")
        
        # Assert
        mock_mw._qtgui.QIcon.assert_not_called()

    def test_context_menu_open_location(self, mock_mw):
        # Arrange
        controller = GalleryController(mock_mw)
        mock_item = MagicMock()
        mock_item.toolTip.return_value = "/path/to/game.nes"
        mock_mw.ui.list_gallery.itemAt.return_value = mock_item
        
        # Mock QMenu actions
        mock_menu = mock_mw._qtwidgets.QMenu.return_value
        mock_action_open = MagicMock()
        mock_menu.addAction.side_effect = [mock_action_open, MagicMock(), MagicMock(), MagicMock()]
        mock_menu.exec.return_value = mock_action_open
        
        # Act
        controller._on_gallery_context_menu(MagicMock())
        
        # Assert
        mock_mw._open_file_location.assert_called_with(Path("/path/to/game.nes"))
