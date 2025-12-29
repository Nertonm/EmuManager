from unittest.mock import MagicMock, patch

import pytest

from emumanager.workers import common, ps2, psp


class MockLogger:
    """Mock GuiLogger to capture logs in tests."""

    def __init__(self):
        self.logs = []

    def info(self, msg, *args):
        self.logs.append(("INFO", msg % args if args else msg))

    def warning(self, msg, *args):
        self.logs.append(("WARN", msg % args if args else msg))

    def error(self, msg, *args):
        self.logs.append(("ERROR", msg % args if args else msg))

    def exception(self, msg, *args):
        self.logs.append(("EXCEPTION", msg % args if args else msg))


@pytest.fixture
def mock_logger():
    return MockLogger()


@pytest.fixture
def mock_args():
    args = MagicMock()
    args.dry_run = False
    args.progress_callback = None
    args.cancel_event = None
    return args


def test_clean_junk(tmp_path, mock_args):
    # Setup junk files
    (tmp_path / "test.txt").touch()
    (tmp_path / "test.nfo").touch()
    (tmp_path / "keep.iso").touch()
    (tmp_path / "empty_dir").mkdir()

    def list_files(p):
        return list(p.rglob("*"))

    def list_dirs(p):
        return [x for x in p.rglob("*") if x.is_dir()]

    log_cb = MagicMock()

    res = common.worker_clean_junk(
        tmp_path,
        mock_args,
        log_cb,
        list_files,
        list_dirs,
    )

    assert not (tmp_path / "test.txt").exists()
    assert not (tmp_path / "test.nfo").exists()
    assert (tmp_path / "keep.iso").exists()
    assert not (tmp_path / "empty_dir").exists()
    assert "Deleted 2 files and 1 empty directories" in res


def test_ps2_verify_no_files(tmp_path, mock_args):
    log_cb = MagicMock()
    res = ps2.worker_ps2_verify(tmp_path, mock_args, log_cb, lambda p: [])
    # It might return "PS2 ROMs directory not found." if dir doesn't exist
    # or "No PS2 files found" if dir exists but is empty.
    # In this test, tmp_path exists but has no subdirs, so find_target_dir
    # might fail or return tmp_path if fallback works.
    assert "PS2 ROMs directory not found" in res


@patch("emumanager.workers.ps2.LibraryDB")
@patch("emumanager.ps2.metadata.get_ps2_serial")
@patch(
    "emumanager.ps2.database.db.get_title",
)
def test_ps2_verify_found(
    mock_get_title,
    mock_get_serial,
    mock_lib_db,
    tmp_path,
    mock_args,
):
    # Setup
    ps2_dir = tmp_path / "roms" / "ps2"
    ps2_dir.mkdir(parents=True)
    iso = ps2_dir / "game.iso"
    iso.touch()

    mock_get_serial.return_value = "SLUS-12345"
    mock_get_title.return_value = "Test Game"

    log_cb = MagicMock()

    def list_files(p):
        return [iso]

    res = ps2.worker_ps2_verify(tmp_path, mock_args, log_cb, list_files)

    assert "Identified: 1" in res
    mock_get_serial.assert_called_with(iso)
    mock_get_title.assert_called_with("SLUS-12345")


def test_psp_verify_no_files(tmp_path, mock_args):
    log_cb = MagicMock()
    res = psp.worker_psp_verify(
        tmp_path,
        mock_args,
        log_cb,
        lambda p: [],
    )
    assert "Scan complete. Identified: 0" in res


@patch("emumanager.psp.metadata.get_metadata")
@patch("emumanager.psp.database.db.get_title")
def test_psp_verify_found(
    mock_get_title,
    mock_get_meta,
    tmp_path,
    mock_args,
):
    # Setup
    psp_dir = tmp_path / "roms" / "psp"
    psp_dir.mkdir(parents=True)
    iso = psp_dir / "game.iso"
    iso.touch()

    mock_get_meta.return_value = {"serial": "ULUS10041"}
    mock_get_title.return_value = "Lumines"

    log_cb = MagicMock()

    def list_files(p):
        return [iso]

    res = psp.worker_psp_verify(
        tmp_path,
        mock_args,
        log_cb,
        list_files,
    )

    assert "Identified: 1" in res
    mock_get_meta.assert_called_with(iso)
    mock_get_title.assert_called_with("ULUS10041")
