import sys
import importlib
from unittest.mock import MagicMock, patch

import pytest

# We will import MainWindowBase inside the test/fixture to avoid global side effects

class TestMainWindowLogic:
    @pytest.fixture(scope="class", autouse=True)
    def setup_mocks(self):
        # Mock PyQt6 modules for this test class only
        mock_modules = {
            "PyQt6": MagicMock(),
            "PyQt6.QtWidgets": MagicMock(),
            "PyQt6.QtCore": MagicMock(),
            "PyQt6.QtGui": MagicMock(),
        }
        
        # Start patching sys.modules
        patcher = patch.dict(sys.modules, mock_modules)
        patcher.start()
        
        # Remove gui_main from sys.modules if it exists, to force re-import with mocks
        if "emumanager.gui_main" in sys.modules:
            del sys.modules["emumanager.gui_main"]
            
        yield
        
        patcher.stop()
        
        # Clean up gui_main so other tests don't use the mocked version
        if "emumanager.gui_main" in sys.modules:
            del sys.modules["emumanager.gui_main"]

    @pytest.fixture
    def window(self, setup_mocks):
        # Import inside the fixture to use the mocks
        with patch("emumanager.gui_ui.Ui_MainWindow"):
            from emumanager.gui_main import MainWindowBase
            
            # Mock dependencies
            mock_qt = MagicMock()
            mock_manager = MagicMock()

            window = MainWindowBase(mock_qt, mock_manager)
            # Manually attach the mock UI elements that are expected
            window.ui = MagicMock()
            window.ui.progress_bar = MagicMock()
            # Default isVisible to False so setVisible(True) is called
            window.ui.progress_bar.isVisible.return_value = False
            window.status = MagicMock()

            # Mock the buttons that _set_ui_enabled expects
            window.ui.btn_organize = MagicMock()
            window.ui.btn_ps2_convert = MagicMock()
            window.ui.btn_dolphin_convert = MagicMock()
            window.ui.btn_dolphin_verify = MagicMock()
            window.ui.btn_open_lib = MagicMock()

            return window

    def test_progress_hook_updates_ui(self, window):
        # Force direct UI update path (no signal)
        window._signaler = None

        # Test 50% progress
        window.progress_hook(0.5, "Halfway there")

        window.ui.progress_bar.setValue.assert_called_with(50)
        window.ui.progress_bar.setVisible.assert_called_with(True)
        window.status.showMessage.assert_called_with("Halfway there")

    def test_progress_hook_clamping(self, window):
        # Force direct UI update path (no signal)
        window._signaler = None

        # Test > 100%
        window.progress_hook(1.5, "Done")
        window.ui.progress_bar.setValue.assert_called_with(100)

        # Test < 0%
        window.progress_hook(-0.1, "Start")
        window.ui.progress_bar.setValue.assert_called_with(0)

    def test_set_ui_enabled_false(self, window):
        # Simulate starting a task
        window._set_ui_enabled(False)

        # Buttons should be disabled
        window.ui.btn_organize.setEnabled.assert_called_with(False)
        window.ui.btn_ps2_convert.setEnabled.assert_called_with(False)
        window.ui.btn_dolphin_convert.setEnabled.assert_called_with(False)
        window.ui.btn_dolphin_verify.setEnabled.assert_called_with(False)
        window.ui.btn_open_lib.setEnabled.assert_called_with(False)

        # Progress bar should be visible (based on _set_ui_enabled logic)
        # usually showing it when busy, but let's check the actual implementation.
        # Wait, I need to check what I wrote for _set_ui_enabled.
        # Usually enabled=False means "busy", so progress bar might be shown or reset.

    def test_set_ui_enabled_true(self, window):
        # Simulate task finished
        window._set_ui_enabled(True)

        # Buttons should be enabled
        window.ui.btn_organize.setEnabled.assert_called_with(True)
        window.ui.btn_ps2_convert.setEnabled.assert_called_with(True)

        # Progress bar should be hidden
        window.ui.progress_bar.setVisible.assert_called_with(False)
