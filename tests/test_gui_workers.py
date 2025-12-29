from unittest.mock import MagicMock, patch

import pytest

from emumanager.gui_workers import (
    worker_dolphin_convert,
    worker_dolphin_organize,
    worker_dolphin_verify,
    worker_ps2_organize,
)


@pytest.fixture
def mock_converter(monkeypatch):
    mock = MagicMock()
    mock.check_tool.return_value = True
    mock.convert_to_rvz.return_value = True
    mock.verify_rvz.return_value = True

    # Patch the class instantiation
    monkeypatch.setattr(
        "emumanager.workers.dolphin.DolphinConverter",
        MagicMock(return_value=mock),
    )
    return mock


@pytest.fixture
def mock_list_files():
    return MagicMock(return_value=[])


def test_worker_dolphin_convert_no_dirs(tmp_path, mock_converter, mock_list_files):
    # No roms/gamecube or roms/wii
    res = worker_dolphin_convert(tmp_path, MagicMock(), lambda x: None, mock_list_files)
    assert "No GameCube or Wii directories found" in res


def test_worker_dolphin_convert_success(tmp_path, mock_converter):
    # Setup directories
    gc_dir = tmp_path / "roms" / "gamecube"
    gc_dir.mkdir(parents=True)

    iso_file = gc_dir / "game.iso"
    iso_file.touch()

    def list_files(d):
        print(f"DEBUG: list_files called with {d}, name={d.name}")
        if d.name == "gamecube":
            return [iso_file]
        return []

    args = MagicMock()
    args.rm_originals = False
    args.cancel_event.is_set.return_value = False

    res = worker_dolphin_convert(tmp_path, args, print, list_files)

    assert "Converted: 1" in res
    mock_converter.convert_to_rvz.assert_called_once()


def test_worker_dolphin_verify_success(tmp_path, mock_converter):
    # Setup directories
    wii_dir = tmp_path / "roms" / "wii"
    wii_dir.mkdir(parents=True)

    rvz_file = wii_dir / "game.rvz"
    rvz_file.touch()

    def list_files(d):
        if d.name == "wii":
            return [rvz_file]
        return []

    args = MagicMock()
    args.cancel_event.is_set.return_value = False
    res = worker_dolphin_verify(tmp_path, args, lambda x: None, list_files)

    assert "Passed: 1" in res
    mock_converter.verify_rvz.assert_called_once()


@patch("emumanager.workers.dolphin.gc_meta")
@patch("emumanager.workers.dolphin.wii_meta")
def test_worker_dolphin_organize_success(
    mock_wii_meta, mock_gc_meta, tmp_path, mock_converter
):
    # Setup directories
    gc_dir = tmp_path / "roms" / "gamecube"
    gc_dir.mkdir(parents=True)

    iso_file = gc_dir / "game.iso"
    iso_file.touch()

    # Mock metadata
    mock_gc_meta.get_metadata.return_value = {
        "game_id": "GM4E01",
        "internal_name": "Mario Kart",
    }

    def list_files(d):
        if d.name == "gamecube":
            return [iso_file]
        return []

    args = MagicMock()
    args.dry_run = False
    args.cancel_event.is_set.return_value = False

    res = worker_dolphin_organize(tmp_path, args, lambda x: None, list_files)

    assert "Renamed: 1" in res

    # Check if file was renamed
    expected_path = gc_dir / "Mario Kart [GM4E01].iso"
    assert expected_path.exists()
    assert not iso_file.exists()


@patch("emumanager.ps2.metadata.get_ps2_serial")
def test_worker_ps2_organize_success(mock_get_serial, tmp_path):
    ps2_dir = tmp_path / "roms" / "ps2"
    ps2_dir.mkdir(parents=True)

    iso_file = ps2_dir / "game.iso"
    iso_file.touch()

    mock_get_serial.return_value = "SLUS-20002"

    # Patch the global db instance
    with patch("emumanager.ps2.database.db.get_title") as mock_get_title:
        mock_get_title.return_value = "Ridge Racer V"

        def list_files(d):
            return [iso_file]

        args = MagicMock()
        args.dry_run = False
        args.cancel_event.is_set.return_value = False

        res = worker_ps2_organize(tmp_path, args, lambda x: None, list_files)

        assert "Renamed: 1" in res
        assert (ps2_dir / "Ridge Racer V [SLUS-20002].iso").exists()
        assert not iso_file.exists()


@patch("emumanager.workers.dolphin.gc_meta")
@patch("emumanager.workers.dolphin.wii_meta")
def test_worker_dolphin_organize_with_db(mock_wii_meta, mock_gc_meta, tmp_path):
    # Setup directories
    gc_dir = tmp_path / "roms" / "gamecube"
    gc_dir.mkdir(parents=True)

    iso_file = gc_dir / "game.iso"
    iso_file.touch()

    # Mock metadata
    mock_gc_meta.get_metadata.return_value = {
        "game_id": "GM4E01",
        "internal_name": "Mario Kart Internal",
    }

    def list_files(d):
        if d.name == "gamecube":
            return [iso_file]
        return []

    args = MagicMock()
    args.dry_run = False
    args.cancel_event.is_set.return_value = False

    # Patch the global db instance
    with patch("emumanager.gamecube.database.db.get_title") as mock_get_title:
        mock_get_title.return_value = "Mario Kart Double Dash!!"

        res = worker_dolphin_organize(tmp_path, args, lambda x: None, list_files)

        assert "Renamed: 1" in res

        # Check if file was renamed using DB title
        expected_path = gc_dir / "Mario Kart Double Dash!! [GM4E01].iso"
        assert expected_path.exists()
        assert not iso_file.exists()


@patch("emumanager.workers.dolphin.gc_meta")
@patch("emumanager.workers.dolphin.wii_meta")
def test_worker_dolphin_organize_direct_path(mock_wii_meta, mock_gc_meta, tmp_path):
    # Setup directory directly as gamecube folder (no roms/gamecube)
    gc_dir = tmp_path / "my_gamecube_collection"
    gc_dir.mkdir()

    iso_file = gc_dir / "game.iso"
    # Write GC Magic to file
    with open(iso_file, "wb") as f:
        f.write(b"\x00" * 0x1C)
        f.write(b"\xc2\x33\x9f\x3d")
        f.write(b"\x00" * 4)

    # Mock metadata
    mock_gc_meta.get_metadata.return_value = {
        "game_id": "GM4E01",
        "internal_name": "Mario Kart Internal",
    }

    def list_files(d):
        # list_files_fn is called with target_dir.
        # If logic works, target_dir should be gc_dir (fallback)
        if d == gc_dir:
            return [iso_file]
        return []

    args = MagicMock()
    args.dry_run = False
    args.cancel_event.is_set.return_value = False

    with patch("emumanager.gamecube.database.db.get_title") as mock_get_title:
        mock_get_title.return_value = "Mario Kart Double Dash!!"

        # Pass gc_dir as base_path
        res = worker_dolphin_organize(gc_dir, args, lambda x: None, list_files)

        assert "Renamed: 1" in res
        expected_path = gc_dir / "Mario Kart Double Dash!! [GM4E01].iso"
        assert expected_path.exists()
