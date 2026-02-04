import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from emumanager.controllers.duplicates import DuplicatesController

class TestDuplicatesController:
    @pytest.fixture
    def mock_mw(self):
        mw = MagicMock()
        mw.ui = MagicMock()
        mw.window = MagicMock()
        mw._last_base = "/mock/library"
        mw.library_db = MagicMock()
        mw._qtwidgets = MagicMock()
        mw._qtcore = MagicMock()
        mw._Qt_enum = MagicMock()
        
        # Immediate execution side effect for background tasks
        def side_effect(work_fn, done_cb):
            res = work_fn()
            done_cb(res)
        mw._run_in_background.side_effect = side_effect
        
        return mw

    def test_resolve_duplicates_root(self, mock_mw):
        controller = DuplicatesController(mock_mw)
        root = controller._resolve_duplicates_root()
        assert "duplicates" in str(root)

    def test_validate_move_selection_ok(self, mock_mw):
        controller = DuplicatesController(mock_mw)
        controller._current_group = {"entries": [1]}
        with patch.object(controller, "_get_keep_rows", return_value=[0]):
            assert controller._validate_move_selection() == 0

    @patch("emumanager.controllers.duplicates.safe_move")
    def test_move_others_to_duplicates_integration(self, mock_safe_move, mock_mw):
        mock_safe_move.return_value = True
        
        # Setup controller
        controller = DuplicatesController(mock_mw)
        controller._current_group = {"entries": [1, 2]}
        
        # Setup UI Mocks
        mock_mw.ui.table_dups_entries.rowCount.return_value = 2
        mock_item = MagicMock()
        mock_item.text.return_value = "/tmp/test.nes"
        mock_mw.ui.table_dups_entries.item.return_value = mock_item
        
        # Mock methods to skip complex logic
        controller._get_keep_rows = MagicMock(return_value=[0])
        controller._resolve_duplicates_root = MagicMock(return_value=Path("/tmp/dups"))
        controller._unique_dest_path = MagicMock(return_value=Path("/tmp/dups/game.nes"))
        
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "mkdir"):
                # Act
                controller._move_others_to_duplicates()
                
                # Assert
                assert mock_safe_move.called
                assert mock_mw.library_db.remove_entry.called

    def test_on_duplicate_move_finished_logs(self, mock_mw):
        controller = DuplicatesController(mock_mw)
        controller._on_duplicate_move_finished({"moved": [1], "skipped": []})
        assert any("Move complete" in str(c) for c in mock_mw.log_msg.call_args_list)