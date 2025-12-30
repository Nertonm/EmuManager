from unittest.mock import MagicMock, patch

import pytest

from emumanager.common.models import VerifyReport
from emumanager.workers.verification import worker_hash_verify, worker_identify_all


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def mock_args():
    args = MagicMock()
    args.dat_path = None
    args.dats_roots = []
    args.dats_root = None
    return args


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.name = "TestDB"
    db.version = "1.0"
    return db


def test_worker_hash_verify_no_dat(tmp_path, mock_logger, mock_args):
    """Test verification when no DAT file is found."""
    # Setup base path with a system name
    base_path = tmp_path / "snes"
    base_path.mkdir()

    # Provide dats_roots so it attempts discovery and logs warning
    mock_args.dats_roots = [tmp_path / "dats"]

    report = worker_hash_verify(base_path, mock_args, mock_logger, lambda p: [])

    assert "Error: No valid DAT file selected or found" in report.text
    # Check for warning log
    assert any("WARN: " in str(call) for call in mock_logger.call_args_list)


def test_worker_hash_verify_auto_discovery(tmp_path, mock_logger, mock_args, mock_db):
    """Test auto-discovery of DAT file based on folder name."""
    base_path = tmp_path / "snes"
    base_path.mkdir()

    dats_root = tmp_path / "dats"
    dats_root.mkdir()
    dat_file = dats_root / "Nintendo - Super Nintendo Entertainment System.dat"
    dat_file.touch()

    mock_args.dats_roots = [dats_root]

    # Mock find_dat_for_system to return our dat file
    with (
        patch(
            "emumanager.workers.verification.find_dat_for_system", return_value=dat_file
        ),
        patch(
            "emumanager.workers.verification.dat_parser.parse_dat_file",
            return_value=mock_db,
        ),
        patch("emumanager.workers.verification._run_verification") as mock_run,
    ):
        mock_run.return_value = VerifyReport(text="Success")

        report = worker_hash_verify(base_path, mock_args, mock_logger, lambda p: [])

        assert report.text == "Success"
        mock_logger.assert_any_call(
            f"Auto-selected DAT: {dat_file.name} (in {dats_root})"
        )


def test_worker_hash_verify_parse_error(tmp_path, mock_logger, mock_args):
    """Test handling of DAT parsing errors."""
    base_path = tmp_path / "snes"
    dat_path = tmp_path / "snes.dat"
    dat_path.touch()
    mock_args.dat_path = dat_path

    with patch(
        "emumanager.workers.verification.dat_parser.parse_dat_file",
        side_effect=Exception("Parse Error"),
    ):
        report = worker_hash_verify(base_path, mock_args, mock_logger, lambda p: [])

        assert "Error parsing DAT: Parse Error" in report.text


def test_worker_identify_all_no_dats(tmp_path, mock_logger, mock_args):
    """Test identify_all when no DATs directory is found."""
    mock_args.dats_roots = []

    report = worker_identify_all(tmp_path, mock_args, mock_logger, lambda p: [])

    assert "Error: DATs directory not found" in report.text


def test_worker_identify_all_success(tmp_path, mock_logger, mock_args):
    """Test successful identification flow."""
    dats_root = tmp_path / "dats"
    dats_root.mkdir()
    (dats_root / "snes.dat").touch()
    mock_args.dats_roots = [dats_root]

    # Mock dependencies
    with (
        patch("emumanager.workers.verification.dat_parser.DatDb"),
        patch(
            "emumanager.workers.verification.dat_parser.parse_dat_file"
        ) as mock_parse,
        patch("emumanager.workers.verification._run_verification") as mock_run,
    ):
        mock_run.return_value = VerifyReport(text="Success")

        worker_identify_all(tmp_path, mock_args, mock_logger, lambda p: [])

        # Should parse found DATs
        assert mock_parse.call_count >= 1
        # Should run verification
        mock_run.assert_called()
