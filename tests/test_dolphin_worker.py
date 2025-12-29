from unittest.mock import MagicMock, patch

import pytest

from emumanager.workers.dolphin import worker_dolphin_organize, worker_dolphin_verify


@pytest.fixture
def mock_args():
    args = MagicMock()
    args.dry_run = False
    args.deep_verify = False
    args.progress_callback = MagicMock()
    args.cancel_event = MagicMock()
    args.cancel_event.is_set.return_value = False
    return args


@pytest.fixture
def mock_logger():
    return MagicMock()


@patch("emumanager.workers.dolphin._resolve_dolphin_targets")
@patch("emumanager.workers.dolphin._load_dolphin_databases")
@patch("emumanager.workers.dolphin._organize_dolphin_file")
def test_worker_dolphin_organize(
    mock_organize, mock_load_db, mock_resolve, mock_args, mock_logger, tmp_path
):
    # Setup
    base_path = tmp_path / "roms" / "gamecube"
    base_path.mkdir(parents=True)

    target_dir = base_path / "ISOs (RVZ)"
    target_dir.mkdir()

    mock_resolve.return_value = [target_dir]

    file1 = target_dir / "game1.rvz"
    file1.touch()

    list_files_fn = MagicMock(return_value=[file1])

    mock_organize.return_value = "renamed"

    # Execute
    result = worker_dolphin_organize(base_path, mock_args, mock_logger, list_files_fn)

    # Verify
    assert "Renamed: 1" in result
    mock_organize.assert_called_once()
    mock_args.progress_callback.assert_called()


@patch("emumanager.workers.dolphin.DolphinConverter")
@patch("emumanager.workers.dolphin._resolve_dolphin_targets")
@patch("emumanager.workers.dolphin._verify_dolphin_file")
def test_worker_dolphin_verify(
    mock_verify_file,
    mock_resolve,
    mock_converter_cls,
    mock_args,
    mock_logger,
    tmp_path,
):
    # Setup
    base_path = tmp_path / "roms" / "gamecube"
    base_path.mkdir(parents=True)

    target_dir = base_path / "ISOs (RVZ)"
    target_dir.mkdir()

    mock_resolve.return_value = [target_dir]

    # Mock converter
    mock_converter = mock_converter_cls.return_value
    mock_converter.check_tool.return_value = True

    file1 = target_dir / "game1.rvz"
    file1.touch()

    list_files_fn = MagicMock(return_value=[file1])

    mock_verify_file.return_value = (True, "OK")

    # Execute
    result = worker_dolphin_verify(base_path, mock_args, mock_logger, list_files_fn)

    # Verify
    assert "Passed: 1" in result
    mock_verify_file.assert_called_once()
    mock_args.progress_callback.assert_called()


@patch("emumanager.workers.dolphin.DolphinConverter")
@patch("emumanager.workers.dolphin._resolve_dolphin_targets")
@patch("emumanager.workers.dolphin._verify_dolphin_file")
def test_worker_dolphin_verify_deep(
    mock_verify_file,
    mock_resolve,
    mock_converter_cls,
    mock_args,
    mock_logger,
    tmp_path,
):
    # Setup
    mock_args.deep_verify = True
    base_path = tmp_path / "roms" / "gamecube"
    base_path.mkdir(parents=True)

    target_dir = base_path / "ISOs (RVZ)"
    target_dir.mkdir()

    mock_resolve.return_value = [target_dir]

    # Mock converter
    mock_converter = mock_converter_cls.return_value
    mock_converter.check_tool.return_value = True

    file1 = target_dir / "game1.rvz"
    file1.touch()

    list_files_fn = MagicMock(return_value=[file1])

    mock_verify_file.return_value = (True, "OK (Hash Verified)")

    # Execute
    result = worker_dolphin_verify(base_path, mock_args, mock_logger, list_files_fn)

    # Verify
    assert "Passed: 1" in result
    mock_verify_file.assert_called_once()
    # Check if deep=True was passed
    _, kwargs = mock_verify_file.call_args
    assert kwargs.get("deep_verify") is True
    assert kwargs.get("progress_cb") is not None
