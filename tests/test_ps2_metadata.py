from emumanager.ps2 import metadata

def test_get_ps2_serial_not_found(tmp_path):
    f = tmp_path / "dummy.iso"
    f.write_bytes(b"some random data without serial")
    assert metadata.get_ps2_serial(f) is None

def test_get_ps2_serial_found_slus(tmp_path):
    f = tmp_path / "game.iso"
    # SLUS_200.02 -> SLUS-20002
    content = b"some padding " + b"SLUS_200.02" + b" more padding"
    f.write_bytes(content)
    assert metadata.get_ps2_serial(f) == "SLUS-20002"

def test_get_ps2_serial_found_sles(tmp_path):
    f = tmp_path / "game.bin"
    # SLES-50003 -> SLES-50003
    content = b"padding " + b"SLES-50003" + b" padding"
    f.write_bytes(content)
    assert metadata.get_ps2_serial(f) == "SLES-50003"

def test_get_ps2_serial_gz(tmp_path):
    import gzip
    f = tmp_path / "game.iso.gz"
    content = b"padding " + b"SLUS_200.02" + b" padding"
    with gzip.open(f, "wb") as gz:
        gz.write(content)
    
    assert metadata.get_ps2_serial(f) == "SLUS-20002"

def test_get_ps2_serial_boot2(tmp_path):
    f = tmp_path / "system.cnf"
    # BOOT2 = cdrom0:\SLUS_200.02;1
    content = b"BOOT2 = cdrom0:\\SLUS_200.02;1\r\nVER = 1.00\r\nVMODE = NTSC"
    f.write_bytes(content)
    assert metadata.get_ps2_serial(f) == "SLUS-20002"

def test_get_ps2_serial_boot2_forward_slash(tmp_path):
    f = tmp_path / "system.cnf"
    # BOOT2 = cdrom0:/SLUS_200.02;1
    content = b"BOOT2 = cdrom0:/SLUS_200.02;1\r\nVER = 1.00"
    f.write_bytes(content)
    assert metadata.get_ps2_serial(f) == "SLUS-20002"
