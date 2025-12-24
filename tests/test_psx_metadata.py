from pathlib import Path
from unittest.mock import patch

from emumanager.psx import metadata


def test_get_psx_serial_not_found(tmp_path):
    f = tmp_path / "dummy.iso"
    f.write_bytes(b"no serial here")
    assert metadata.get_psx_serial(f) is None


def test_get_psx_serial_boot_line(tmp_path):
    f = tmp_path / "game.iso"
    # BOOT = cdrom:\SLUS_005.94;1 -> SLUS-00594
    content = b"padding BOOT = cdrom:\\SLUS_005.94;1 more padding"
    f.write_bytes(content)
    assert metadata.get_psx_serial(f) == "SLUS-00594"


def test_get_psx_serial_raw_serial(tmp_path):
    f = tmp_path / "game.bin"
    content = b"padding SLES-00992 padding"
    f.write_bytes(content)
    assert metadata.get_psx_serial(f) == "SLES-00992"


def test_get_psx_serial_gz(tmp_path):
    import gzip

    f = tmp_path / "game.iso.gz"
    content = b"BOOT = cdrom0:\\SLUS_005.94;1"
    with gzip.open(f, "wb") as gz:
        gz.write(content)
    assert metadata.get_psx_serial(f) == "SLUS-00594"


def test_get_psx_serial_chd(tmp_path):
    f = tmp_path / "game.chd"
    f.write_bytes(b"fake chd header")
    # Patch the CHD reader to avoid needing chdman
    with patch("emumanager.psx.metadata._read_header_chd", return_value=b"BOOT = cdrom:\\SLUS_005.94;1"):
        assert metadata.get_psx_serial(f) == "SLUS-00594"
