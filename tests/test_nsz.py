from emumanager.switch import nsz


def test_detect_level_from_stdout_basic():
    out = "nsz: compression level: 3\nSome other info"
    assert nsz.detect_nsz_level_from_stdout(out) == 3


def test_detect_level_flag_style():
    out = "Called with -19 for best compression"
    assert nsz.detect_nsz_level_from_stdout(out) == 19


def test_detect_level_none():
    out = "no useful info here"
    assert nsz.detect_nsz_level_from_stdout(out) is None


def test_parse_verify_output_positive():
    out = "Verify: OK - checksum: OK"
    assert nsz.parse_nsz_verify_output(out) is True


def test_parse_verify_output_negative():
    out = "ERROR: file corrupted"
    assert nsz.parse_nsz_verify_output(out) is False
