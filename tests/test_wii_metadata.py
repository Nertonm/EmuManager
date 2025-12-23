from emumanager.wii.metadata import get_wii_serial

def test_get_wii_serial_iso(tmp_path):
    iso_file = tmp_path / "game.iso"
    # RMGE01 (Super Mario Galaxy)
    iso_file.write_bytes(b"RMGE01" + b"\x00" * 100)
    
    serial = get_wii_serial(iso_file)
    assert serial == "RMGE01"

def test_get_wii_serial_short_file(tmp_path):
    iso_file = tmp_path / "short.iso"
    iso_file.write_bytes(b"RMG")
    
    serial = get_wii_serial(iso_file)
    assert serial is None

def test_get_wii_serial_invalid_chars(tmp_path):
    iso_file = tmp_path / "invalid.iso"
    iso_file.write_bytes(b"RMG\x0001")
    
    serial = get_wii_serial(iso_file)
    assert serial is None
