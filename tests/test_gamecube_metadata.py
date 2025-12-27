from emumanager.gamecube.metadata import get_gamecube_serial


def test_get_gamecube_serial_iso(tmp_path):
    iso_file = tmp_path / "game.iso"
    # GM4E01 (Mario Kart: Double Dash!!)
    iso_file.write_bytes(b"GM4E01" + b"\x00" * 100)

    serial = get_gamecube_serial(iso_file)
    assert serial == "GM4E01"


def test_get_gamecube_serial_short_file(tmp_path):
    iso_file = tmp_path / "short.iso"
    iso_file.write_bytes(b"GM4")

    serial = get_gamecube_serial(iso_file)
    assert serial is None


def test_get_gamecube_serial_invalid_chars(tmp_path):
    iso_file = tmp_path / "invalid.iso"
    iso_file.write_bytes(b"GM4\x0001")

    serial = get_gamecube_serial(iso_file)
    assert serial is None


def test_get_gamecube_serial_rvz(tmp_path):
    rvz_file = tmp_path / "game.rvz"
    rvz_file.write_bytes(b"RVZ\x01" + b"\x00" * 100)

    serial = get_gamecube_serial(rvz_file)
    assert serial is None
