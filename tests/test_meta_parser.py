from emumanager.switch.meta_parser import parse_tool_output


def test_parse_basic():
    stdout = """
Name: Super Game Deluxe
Title ID: 0100ABCDEF000011
Display Version: 1.2.3
Includes Japanese and English audio tracks
"""
    parsed = parse_tool_output(stdout)
    assert parsed["name"] == "Super Game Deluxe"
    assert parsed["id"] == "0100ABCDEF000011"
    assert parsed["ver"] == "1.2.3"
    # language detection is heuristic; expect Ja and En to appear
    assert "Ja" in parsed["langs"] and "En" in parsed["langs"]


def test_parse_none():
    parsed = parse_tool_output(None)
    assert parsed["name"] is None
    assert parsed["id"] is None
    assert parsed["ver"] is None
    assert parsed["langs"] == ""


def test_parse_multiple_languages():
    stdout = (
        "Application Name: Some Game\n"
        "Supported Languages: English, Portuguese, Korean\n"
        "Program Id: 0x0100AAAABBBBCCCC\n"
    )
    parsed = parse_tool_output(stdout)
    assert parsed["name"] == "Some Game"
    assert parsed["id"] == "0100AAAABBBBCCCC"
    # expect En and Pt (and Ko)
    assert (
        "En" in parsed["langs"] and "Pt" in parsed["langs"] and "Ko" in parsed["langs"]
    )
