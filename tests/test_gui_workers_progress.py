from pathlib import Path
from unittest.mock import MagicMock, patch

from emumanager.gui_workers import worker_dolphin_convert, worker_ps2_convert


class TestWorkerProgress:
    @patch("emumanager.workers.ps2.LibraryDB")
    @patch("emumanager.workers.ps2.ps2_converter.convert_directory")
    @patch("emumanager.workers.ps2.find_tool")
    def test_ps2_convert_progress(
        self, mock_find_tool, mock_convert_directory, mock_lib_db, tmp_path
    ):
        # Setup
        mock_find_tool.return_value = Path("/usr/bin/fake_tool")

        # Mock convert_directory to simulate progress calls if we were testing
        # the converter itself, but here we are testing the worker calling the
        # converter with the callback.
        # Actually, the worker passes the callback to convert_directory.
        # So we just check if convert_directory was called with the callback.

        mock_convert_directory.return_value = []

        args = MagicMock()
        args.dry_run = False
        args.rm_originals = False
        progress_cb = MagicMock()
        args.progress_callback = progress_cb

        base_path = tmp_path / "base"
        (base_path / "roms" / "ps2").mkdir(parents=True)

        # Run
        worker_ps2_convert(base_path, args, lambda x: None)

        # Verify
        mock_convert_directory.assert_called_once()
        call_kwargs = mock_convert_directory.call_args[1]
        assert call_kwargs["progress_callback"] == progress_cb

    @patch("emumanager.workers.dolphin.DolphinConverter")
    def test_dolphin_convert_progress(self, mock_dolphin_cls, tmp_path):
        # Setup
        mock_converter = mock_dolphin_cls.return_value
        mock_converter.check_tool.return_value = True
        mock_converter.convert_to_rvz.return_value = True

        args = MagicMock()
        args.rm_originals = False
        args.cancel_event = None
        progress_cb = MagicMock()
        args.progress_callback = progress_cb

        base_path = tmp_path / "base"
        gc_dir = base_path / "roms" / "gamecube"
        gc_dir.mkdir(parents=True)

        # Create dummy files
        (gc_dir / "game1.iso").touch()
        (gc_dir / "game2.iso").touch()

        def list_files_fn(path):
            return list(path.glob("*"))

        # Run
        worker_dolphin_convert(base_path, args, lambda x: None, list_files_fn)

        # Verify progress calls
        # Should be called for each file + completion
        # 2 files -> 0.0, 0.5 (approx), 1.0
        assert progress_cb.call_count >= 3
        progress_cb.assert_any_call(1.0, "Dolphin Conversion complete")

    @patch("emumanager.workers.dolphin.LibraryDB")
    @patch("emumanager.workers.dolphin.DolphinConverter")
    def test_dolphin_verify_progress(self, mock_dolphin_cls, mock_lib_db, tmp_path):
        # Setup
        mock_converter = mock_dolphin_cls.return_value
        mock_converter.check_tool.return_value = True
        mock_converter.verify_rvz.return_value = True

        args = MagicMock()
        args.cancel_event = None
        progress_cb = MagicMock()
        args.progress_callback = progress_cb

        base_path = tmp_path / "base"
        gc_dir = base_path / "roms" / "gamecube"
        gc_dir.mkdir(parents=True)

        # Create dummy files
        (gc_dir / "game1.rvz").touch()
        (gc_dir / "game2.rvz").touch()

        def list_files_fn(path):
            return list(path.glob("*"))

        # Run
        from emumanager.gui_workers import worker_dolphin_verify

        worker_dolphin_verify(base_path, args, lambda x: None, list_files_fn)

        # Verify progress calls
        assert progress_cb.call_count >= 3
        progress_cb.assert_any_call(1.0, "Dolphin Verification complete")

    def test_clean_junk_progress(self, tmp_path):
        # Setup
        args = MagicMock()
        args.dry_run = True
        progress_cb = MagicMock()
        args.progress_callback = progress_cb

        base_path = tmp_path / "base"
        base_path.mkdir()

        # Create dummy files
        files = []
        for i in range(100):
            f = base_path / f"file{i}.txt"
            f.touch()
            files.append(f)

        def list_files_fn(path):
            return files

        def list_dirs_fn(path):
            return []

        # Run
        from emumanager.gui_workers import worker_clean_junk

        worker_clean_junk(base_path, args, lambda x: None, list_files_fn, list_dirs_fn)

        # Verify progress calls
        # Should be called at least twice (start and end) plus intermediate updates
        assert progress_cb.call_count >= 2
        progress_cb.assert_any_call(1.0, "Cleanup complete")

    @patch("emumanager.switch.main_helpers.LibraryDB")
    def test_health_check_progress(self, mock_lib_db, tmp_path):
        # Setup
        args = MagicMock()
        args.dry_run = True
        args.quarantine = False
        args.deep_verify = False
        args.report_csv = None
        args.cancel_event = None
        progress_cb = MagicMock()
        args.progress_callback = progress_cb

        base_path = tmp_path / "base"
        base_path.mkdir()

        # Create dummy files
        files = []
        for i in range(10):
            f = base_path / f"game{i}.nsp"
            f.touch()
            files.append(f)

        # Mock dependencies
        verify_integrity = MagicMock(return_value=(True, "OK"))
        scan_for_virus = MagicMock(return_value=(False, "Clean"))
        safe_move = MagicMock()
        logger = MagicMock()

        # Run
        from emumanager.switch.main_helpers import run_health_check

        run_health_check(
            files,
            args,
            base_path,
            verify_integrity,
            scan_for_virus,
            safe_move,
            logger,
        )

        # Verify progress calls
        assert progress_cb.call_count >= 10
        progress_cb.assert_any_call(1.0, "Health Check complete")
