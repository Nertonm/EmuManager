from emumanager.common.formatting import human_readable_size


def test_human_readable_size_small():
    assert human_readable_size(123) == "123 B"


def test_human_readable_size_kilobyte():
    assert human_readable_size(2048) == "2.0 KB"


def test_human_readable_size_megabyte():
    assert human_readable_size(5_242_880) == "5.0 MB"


def test_human_readable_size_zero():
    assert human_readable_size(0) == "0 B"


def test_human_readable_size_negative():
    # negative values convert to int and then formatted; behavior: show negative bytes
    assert human_readable_size(-1) == "-1 B"


def test_human_readable_size_non_int():
    # non-integer input returns string representation
    assert human_readable_size("not-a-number") == "not-a-number"
