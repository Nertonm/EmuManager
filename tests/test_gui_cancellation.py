from unittest.mock import MagicMock, patch
from pathlib import Path
import threading
from emumanager.gui_workers import worker_organize, worker_health_check

class TestWorkerCancellation:
    @patch("emumanager.workers.switch.process_files")
    def test_organize_cancellation(self, mock_process_files, tmp_path):
        # Setup
        args = MagicMock()
        cancel_event = threading.Event()
        args.cancel_event = cancel_event
        
        # Set cancel event immediately
        cancel_event.set()
        
        env = {
            "ROMS_DIR": tmp_path,
            "CSV_FILE": tmp_path / "test.csv",
        }
        
        # Mock process_files to verify it receives the cancel_event
        mock_process_files.return_value = ([], {})
        
        # Run
        worker_organize(tmp_path, env, args, lambda x: None, lambda x: [Path("test.nsp")])
        
        # Verify
        mock_process_files.assert_called_once()
        ctx = mock_process_files.call_args[0][1]
        assert ctx["cancel_event"] == cancel_event
        assert ctx["cancel_event"].is_set()

    @patch("emumanager.workers.switch.run_health_check")
    def test_health_check_cancellation(self, mock_run_health_check, tmp_path):
        # Setup
        args = MagicMock()
        cancel_event = threading.Event()
        args.cancel_event = cancel_event
        cancel_event.set()
        
        env = {
            "ROMS_DIR": tmp_path,
        }
        
        mock_run_health_check.return_value = {
            "corrupted": [],
            "infected": [],
            "unknown_av": [],
            "report_rows": [],
            "problems": False
        }
        
        # Run
        worker_health_check(tmp_path, env, args, lambda x: None, lambda x: [Path("test.nsp")])
        
        # Verify
        mock_run_health_check.assert_called_once()
        call_args = mock_run_health_check.call_args[0]
        # args is the second argument to run_health_check
        passed_args = call_args[1]
        assert passed_args.cancel_event == cancel_event
        assert passed_args.cancel_event.is_set()

    def test_process_files_cancellation_logic(self, tmp_path):
        # Test the actual logic in process_files (integration-ish)
        from emumanager.switch.main_helpers import process_files
        
        cancel_event = threading.Event()
        ctx = {
            "cancel_event": cancel_event,
            "logger": MagicMock(),
            "progress_callback": MagicMock(),
            # Mock other required ctx items to avoid errors before cancellation check
            "safe_move": MagicMock(),
            "ROMS_DIR": tmp_path,
        }
        
        files = [Path("file1"), Path("file2"), Path("file3")]
        
        # We want to cancel after the first file
        # But process_files checks cancellation at the start of the loop.
        # So if we set it before calling, it should process 0 files?
        # Wait, the loop is: for i, fpath in enumerate(files, 1): check cancel; process...
        # So if set initially, it breaks immediately.
        
        cancel_event.set()
        
        catalog, stats = process_files(files, ctx)
        
        # Should have processed 0 files
        assert len(catalog) == 0
        assert stats["ok"] == 0
        assert stats["erro"] == 0
        assert stats["skipped"] == 0
        
        # Verify logger warning
        ctx["logger"].warning.assert_called_with("Operation cancelled by user.")

    def test_run_health_check_cancellation_logic(self, tmp_path):
        from emumanager.switch.main_helpers import run_health_check
        
        cancel_event = threading.Event()
        args = MagicMock()
        args.cancel_event = cancel_event
        args.dry_run = True
        
        files = [Path("file1"), Path("file2")]
        
        cancel_event.set()
        
        # Mock dependencies
        logger = MagicMock()
        
        summary = run_health_check(
            files, 
            args, 
            tmp_path, 
            lambda f, **k: (True, ""), 
            lambda f: (False, ""), 
            lambda f, d: True, 
            logger
        )
        
        # Should have processed 0 files (or at least stopped early)
        # The loop checks cancel at start.
        # So report_rows should be empty?
        # Wait, run_health_check calls _scan_files.
        # _scan_files checks cancel.
        
        assert len(summary["report_rows"]) == 0
        logger.warning.assert_called_with("Operation cancelled by user.")
