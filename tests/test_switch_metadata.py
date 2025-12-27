from emumanager.switch import metadata


def test_parse_languages_empty():
    assert metadata.parse_languages(None) == ""
    assert metadata.parse_languages("") == ""


def test_parse_languages_common():
    out = "Languages: English, Japanese, Portuguese"
    assert metadata.parse_languages(out) in (
        "[En,Ja,Pt]",
        "[En,Ja,PtBR]",
    ) or metadata.parse_languages(out).startswith("[")


def test_detect_languages_from_filename():
    res = metadata.detect_languages_from_filename("Game Title [EN PTBR].nsp")
    # order may vary depending on token scanning; accept either ordering
    assert res in ("[En,PtBR]", "[PtBR,En]")
    assert metadata.detect_languages_from_filename("SomeGame_JA.xci") == "[Ja]"
    assert metadata.detect_languages_from_filename("NoLangHere.nsp") == ""


def test_get_base_id_and_sanitize():
    tid = "0100ABCDEF000011"
    base = metadata.get_base_id(tid)
    assert isinstance(base, str) and len(base) == 16

    name = "Game Name [0100ABCDEF000011] (v1.2) [hbg]"
    s = metadata.sanitize_name(name)
    assert "hbg" not in s.lower()
    assert "0100ABCDEF000011" not in s


def test_determine_type_and_region():
    assert metadata.determine_type(None, "This is an update patch") == "UPD"
    assert metadata.determine_type("0100ABCDEF000011", None) in ("Base", "DLC")
    assert metadata.determine_region("SomeGame [JPN].nsp", None) == "(JPN)"
    assert metadata.determine_region("SomeGame_EN.nsp", "En") == "(World)"
