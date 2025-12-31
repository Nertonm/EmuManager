from emumanager.workers import ps2 as ps2_module


def test_strip_serial_simple():
    assert ps2_module._strip_serial_tokens("Game Title [SLUS-20946]") == "Game Title"


def test_strip_serial_no_brackets():
    assert (
        ps2_module._strip_serial_tokens("Game Title SLUS-20946")
        == "Game Title SLUS-20946"
    )


def test_strip_serial_variations():
    assert ps2_module._strip_serial_tokens("Foo [SLUS20946]") == "Foo"
    assert ps2_module._strip_serial_tokens("Bar [SLUS-20946.02]") == "Bar"
    assert ps2_module._strip_serial_tokens("Baz[SLUS20946_02]") == "Baz"


def test_strip_serial_multiple_tokens():
    s = "Game [SLUS-12345] Extra [OTHER-1]"
    # Only strips tokens matching the pattern; OTHER-1 won't match and will remain
    assert ps2_module._strip_serial_tokens(s) == "Game Extra [OTHER-1]"
