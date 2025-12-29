from unittest.mock import MagicMock, patch

import pytest

from emumanager.verification import hasher
from emumanager.workers.verification import worker_hash_verify


@pytest.fixture
def mock_args():
    args = MagicMock()
    args.dat_path = "/tmp/test.dat"
    args.progress_callback = MagicMock()
    args.cancel_event = MagicMock()
    args.cancel_event.is_set.return_value = False
    return args


@pytest.fixture
def mock_logger():
    return MagicMock()


@patch("emumanager.workers.verification.LibraryDB")
@patch("emumanager.workers.verification.dat_parser")
@patch("emumanager.workers.verification.hasher")
def test_worker_hash_verify_success(
    mock_hasher, mock_dat_parser, mock_lib_db, mock_args, mock_logger, tmp_path
):
    # Setup
    base_path = tmp_path / "roms" / "nes"
    base_path.mkdir(parents=True)

    file1 = base_path / "game1.nes"
    file1.touch()

    list_files_fn = MagicMock(return_value=[file1])

    # Mock DAT parser
    mock_db = MagicMock()
    mock_db.name = "Nintendo - NES"
    mock_db.version = "1.0"
    mock_match = MagicMock()
    mock_match.game_name = "Super Mario Bros."
    mock_db.lookup.return_value = [mock_match]
    mock_dat_parser.parse_dat_file.return_value = mock_db

    # Mock hasher
    mock_hasher.calculate_hashes.return_value = {
        "crc32": "12345678",
        "sha1": "abcdef",
    }

    # Mock LibraryDB
    mock_lib_instance = mock_lib_db.return_value
    mock_lib_instance.get_entry.return_value = None

    # Execute
    with patch("pathlib.Path.exists", return_value=True):
        report = worker_hash_verify(base_path, mock_args, mock_logger, list_files_fn)

    # Verify
    assert "Verified: 1" in report.text
    assert len(report.results) == 1
    assert report.results[0].status == "VERIFIED"
    assert report.results[0].match_name == "Super Mario Bros."
    assert report.results[0].full_path is not None

    mock_dat_parser.parse_dat_file.assert_called_once()
    mock_hasher.calculate_hashes.assert_called_once()
    mock_args.progress_callback.assert_called()
    mock_lib_instance.update_entry.assert_called()


@patch("emumanager.workers.verification.LibraryDB")
@patch("emumanager.workers.verification.dat_parser")
@patch("emumanager.workers.verification.hasher")
def test_worker_hash_verify_unknown(
    mock_hasher, mock_dat_parser, mock_lib_db, mock_args, mock_logger, tmp_path
):
    # Setup
    base_path = tmp_path / "roms" / "nes"
    base_path.mkdir(parents=True)

    file1 = base_path / "game1.nes"
    file1.touch()

    list_files_fn = MagicMock(return_value=[file1])

    # Mock DAT parser
    mock_db = MagicMock()
    mock_db.lookup.return_value = None
    mock_dat_parser.parse_dat_file.return_value = mock_db

    # Mock hasher
    mock_hasher.calculate_hashes.return_value = {
        "crc32": "12345678",
        "sha1": "abcdef",
    }

    # Mock LibraryDB
    mock_lib_instance = mock_lib_db.return_value
    mock_lib_instance.get_entry.return_value = None

    # Execute
    with patch("pathlib.Path.exists", return_value=True):
        report = worker_hash_verify(base_path, mock_args, mock_logger, list_files_fn)

    # Verify
    assert "Unknown: 1" in report.text
    assert len(report.results) == 1
    assert report.results[0].status == "UNKNOWN"
    assert report.results[0].full_path is not None


def test_hasher_calculate_hashes(tmp_path):
    # Create a dummy file
    f = tmp_path / "test.bin"
    f.write_bytes(b"1234567890")

    # Test without progress
    hashes = hasher.calculate_hashes(f, algorithms=("md5",))
    assert "md5" in hashes

    # Test with progress
    progress_cb = MagicMock()
    hashes = hasher.calculate_hashes(f, algorithms=("md5",), progress_cb=progress_cb)
    assert "md5" in hashes
    progress_cb.assert_called()
