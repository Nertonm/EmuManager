from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from emumanager.workers.n3ds import (
    worker_n3ds_compress,
    worker_n3ds_convert_cia,
    worker_n3ds_decompress,
    worker_n3ds_decrypt,
)


@pytest.fixture
def mock_compress():
    with patch("emumanager.workers.n3ds.compress_to_7z") as m:
        yield m


@pytest.fixture
def mock_decompress():
    with patch("emumanager.workers.n3ds.decompress_7z") as m:
        yield m


@pytest.fixture
def mock_find_target_dir():
    with patch("emumanager.workers.n3ds.find_target_dir") as m:
        yield m


@pytest.fixture
def mock_convert_cia():
    with patch("emumanager.workers.n3ds.convert_to_cia") as m:
        yield m


@pytest.fixture
def mock_decrypt():
    with patch("emumanager.workers.n3ds.decrypt_3ds") as m:
        yield m


def test_worker_n3ds_compress(mock_compress, mock_find_target_dir):
    mock_find_target_dir.return_value = Path("/roms/3ds")

    args = MagicMock()
    args.dry_run = False
    args.cancel_event = None
    log_cb = MagicMock()

    files = [Path("/roms/3ds/game1.3ds"), Path("/roms/3ds/game2.cia")]
    list_files_fn = MagicMock(return_value=files)

    mock_compress.return_value = True

    # Mock unlink
    with patch("pathlib.Path.unlink") as mock_unlink:  # noqa: F841
        with patch("pathlib.Path.exists", return_value=False):  # dest doesn't exist
            res = worker_n3ds_compress(Path("/base"), args, log_cb, list_files_fn)

    assert "Compressed: 2" in res
    assert mock_compress.call_count == 2


def test_worker_n3ds_decompress(mock_decompress, mock_find_target_dir):
    mock_find_target_dir.return_value = Path("/roms/3ds")

    args = MagicMock()
    args.dry_run = False
    args.cancel_event = None
    log_cb = MagicMock()

    files = [Path("/roms/3ds/game1.7z")]
    list_files_fn = MagicMock(return_value=files)

    mock_decompress.return_value = True

    # Mock unlink
    with patch("pathlib.Path.unlink") as mock_unlink:  # noqa: F841
        res = worker_n3ds_decompress(Path("/base"), args, log_cb, list_files_fn)

    assert "Decompressed: 1" in res
    assert mock_decompress.call_count == 1


def test_worker_n3ds_convert_cia(mock_convert_cia, mock_find_target_dir):
    mock_find_target_dir.return_value = Path("/roms/3ds")

    args = MagicMock()
    args.dry_run = False
    args.cancel_event = None
    log_cb = MagicMock()

    files = [Path("/roms/3ds/game1.3ds")]
    list_files_fn = MagicMock(return_value=files)

    mock_convert_cia.return_value = True

    with patch("pathlib.Path.exists", return_value=False):
        res = worker_n3ds_convert_cia(Path("/base"), args, log_cb, list_files_fn)

    assert "Converted: 1" in res
    assert mock_convert_cia.call_count == 1


def test_worker_n3ds_decrypt(mock_decrypt, mock_find_target_dir):
    mock_find_target_dir.return_value = Path("/roms/3ds")

    args = MagicMock()
    args.dry_run = False
    args.cancel_event = None
    log_cb = MagicMock()

    files = [Path("/roms/3ds/game1.3ds")]
    list_files_fn = MagicMock(return_value=files)

    mock_decrypt.return_value = True

    with patch("pathlib.Path.exists", return_value=False):
        res = worker_n3ds_decrypt(Path("/base"), args, log_cb, list_files_fn)

    assert "Decrypted: 1" in res
    assert mock_decrypt.call_count == 1
