import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from emumanager.controllers.tools import ToolsController

class TestToolsController:
    @pytest.fixture
    def mock_mw(self):
        mw = MagicMock()
        mw.ui = MagicMock()
        mw.window = MagicMock()
        mw._last_base = "/mock/base"
        mw._qtwidgets = MagicMock()
        mw._qtcore = MagicMock()
        mw.rom_list = MagicMock()
        mw.sys_list = MagicMock()
        mw._get_common_args.return_value = MagicMock()
        
        # Make background runner execute immediately for synchronous testing
        def side_effect(work_fn, done_cb):
            res = work_fn()
            done_cb(res)
        mw._run_in_background.side_effect = side_effect
        
        return mw

    def test_on_clean_junk_confirmed_calls_worker(self, mock_mw):
        # Arrange
        controller = ToolsController(mock_mw)
        # Mock QMessageBox to return Yes
        mock_mw._qtwidgets.QMessageBox.question.return_value = mock_mw._qtwidgets.QMessageBox.StandardButton.Yes
        
        with patch("emumanager.controllers.tools.worker_clean_junk") as mock_worker:
            # Act
            controller.on_clean_junk()
            
            # Assert
            mock_worker.assert_called()
            mock_mw._run_in_background.assert_called()

    def test_on_clean_junk_cancelled_does_nothing(self, mock_mw):
        # Arrange
        controller = ToolsController(mock_mw)
        # Mock QMessageBox to return No
        mock_mw._qtwidgets.QMessageBox.question.return_value = mock_mw._qtwidgets.QMessageBox.StandardButton.No
        
        with patch("emumanager.controllers.tools.worker_clean_junk") as mock_worker:
            # Act
            controller.on_clean_junk()
            
            # Assert
            mock_worker.assert_not_called()

    def test_resolve_rom_path_variants(self, mock_mw):
        controller = ToolsController(mock_mw)
        
        # Case 1: base is library root
        mock_mw._last_base = "/mock/base"
        path = controller._resolve_rom_path("game.nes", "nes")
        assert path == Path("/mock/base/roms/nes/game.nes")
        
        # Case 2: base is already inside roms folder
        mock_mw._last_base = "/mock/base/roms"
        path = controller._resolve_rom_path("game.nes", "nes")
        assert path == Path("/mock/base/roms/nes/game.nes")

    def test_run_single_file_task_no_selection_aborts(self, mock_mw):
        # Arrange
        mock_mw.rom_list.currentItem.return_value = None
        controller = ToolsController(mock_mw)
        
        # Act
        controller._run_single_file_task(MagicMock(), "Label")
        
        # Assert
        mock_mw._run_in_background.assert_not_called()

    @patch("emumanager.controllers.tools.worker_compress_single")
    def test_compression_dispatcher_switch(self, mock_worker, mock_mw):
        # Arrange
        controller = ToolsController(mock_mw)
        mock_path = Path("game.nsp")
        
        # Act
        controller._compression_dispatcher(mock_path, {}, {}, MagicMock())
        
        # Assert
        mock_worker.assert_called_with(mock_path, {}, {}, ANY)

    @patch("emumanager.controllers.tools.worker_psp_compress_single")
    def test_compression_dispatcher_psp_iso(self, mock_worker, mock_mw):
        # Arrange
        controller = ToolsController(mock_mw)
        mock_path = Path("game.iso")
        # Simulate system selection
        mock_sys_item = MagicMock()
        mock_sys_item.text.return_value = "psp"
        mock_mw.sys_list.currentItem.return_value = mock_sys_item
        
        # Act
        controller._compression_dispatcher(mock_path, {}, {}, MagicMock())
        
        # Assert
        mock_worker.assert_called_with(mock_path, {}, ANY)

    def test_handle_task_error_log_shows_dialog(self, mock_mw):
        # Arrange
        controller = ToolsController(mock_mw)
        res_with_log = "Error: extraction failed; see /tmp/test.chdman.out"
        
        # Act
        controller._handle_task_error_log(res_with_log)
        
        # Assert
        mock_mw._qtwidgets.QMessageBox.assert_called()
        # Verify title or text if needed
        args, kwargs = mock_mw._qtwidgets.QMessageBox.call_args
        assert "Extraction Failed" in str(args) or "Extraction Failed" in str(mock_mw._qtwidgets.QMessageBox.return_value.setWindowTitle.call_args)

from unittest.mock import ANY
