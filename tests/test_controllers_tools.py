import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from emumanager.controllers.tools import ToolsController

@pytest.fixture
def mock_main_window():
    mw = MagicMock()
    mw.ui = MagicMock()
    mw._last_base = Path("/path/to/library")
    mw._env = {}
    mw._get_common_args.return_value = MagicMock()
    mw.log_msg = MagicMock()
    mw._get_list_files_fn.return_value = MagicMock()
    
    # Mock lists
    mw.rom_list = MagicMock()
    mw.sys_list = MagicMock()
    
    # Mock run_in_background to execute immediately
    def run_bg(work_fn, done_fn):
        res = work_fn()
        done_fn(res)
    mw._run_in_background.side_effect = run_bg
    
    return mw

@pytest.fixture
def tools_controller(mock_main_window):
    return ToolsController(mock_main_window)

def test_init_connects_signals(mock_main_window):
    controller = ToolsController(mock_main_window)
    
    # Verify some key signals are connected
    mock_main_window.ui.btn_compress.clicked.connect.assert_called_with(controller.on_compress_selected)
    mock_main_window.ui.btn_organize.clicked.connect.assert_called_with(controller.on_organize)
    mock_main_window.ui.btn_dolphin_convert.clicked.connect.assert_called_with(controller.on_dolphin_convert)

@patch("emumanager.controllers.tools.worker_compress_single")
def test_on_compress_selected(mock_worker, tools_controller):
    # Setup mock return values for single file task
    tools_controller.mw.rom_list.currentItem.return_value.text.return_value = "game.nsp"
    tools_controller.mw.sys_list.currentItem.return_value.text.return_value = "switch"
    tools_controller.mw._last_base = Path("/library")
    
    # Mock Path to return a path with .nsp extension
    # The controller constructs full path: base / "roms" / system / rom_rel_path
    # We need to ensure it exists
    with patch("pathlib.Path.exists", return_value=True):
        tools_controller.on_compress_selected()
    
    mock_worker.assert_called_once()
    args = mock_worker.call_args[0]
    # Check path argument (first arg)
    assert str(args[0]).endswith("game.nsp")

@patch("emumanager.controllers.tools.worker_dolphin_convert")
def test_on_dolphin_convert(mock_worker, tools_controller):
    tools_controller.on_dolphin_convert()
    
    mock_worker.assert_called_once()

@patch("emumanager.controllers.tools.worker_organize")
def test_on_organize(mock_worker, tools_controller):
    tools_controller.on_organize()
    
    mock_worker.assert_called_once()

def test_on_organize_no_base_dir(tools_controller):
    tools_controller.mw._last_base = None
    
    # Mock logging to capture warning
    with patch("emumanager.controllers.tools.logging") as mock_log:
        tools_controller.on_organize()
        mock_log.warning.assert_called_with("Please select a base directory first (Open Library).")

@patch("emumanager.controllers.tools.worker_health_check")
def test_on_health_check(mock_worker, tools_controller):
    tools_controller.on_health_check()
    
    mock_worker.assert_called_once()

@patch("emumanager.controllers.tools.worker_ps2_convert")
def test_on_ps2_convert(mock_worker, tools_controller):
    tools_controller.on_ps2_convert()
    
    mock_worker.assert_called_once()
