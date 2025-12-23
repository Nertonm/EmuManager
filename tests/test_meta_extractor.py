from pathlib import Path
from unittest.mock import patch

from emumanager.switch.meta_extractor import get_metadata_info


class DummyRes:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_get_metadata_direct_parse():
    # Simulate run_cmd that returns stdout with Name and Title ID
    def run_cmd(cmd, *, filebase=None, timeout=None):
        return DummyRes(stdout="Name: Test Game\nTitle ID: 0100ABCDEF000011\nDisplay Version: 2.0")

    info = get_metadata_info(
        Path("/tmp/test.nsp"),
        run_cmd=run_cmd,
        tool_metadata=Path("/usr/bin/nstool"),
        is_nstool=True,
        keys_path=None,
        tool_nsz=None,
        roms_dir=Path("."),
        cmd_timeout=30,
        parse_tool_output=lambda s: {"name": "Test Game", "id": "0100ABCDEF000011", "ver": "2.0", "langs": "En"},
        parse_languages=lambda s: "",
        detect_languages_from_filename=lambda n: "",
        determine_type=lambda tid, txt: "Base",
    )
    assert info is not None
    assert info["name"] == "Test Game"
    assert info["id"] == "0100ABCDEF000011"


def test_get_metadata_filename_fallback():
    # Tool returns nothing; fallback to filename parsing
    def run_cmd(cmd, *, filebase=None, timeout=None):
        return DummyRes(stdout="")

    info = get_metadata_info(
        Path("Some Game [0100ABCDEF000011].nsp"),
        run_cmd=run_cmd,
        tool_metadata=Path("/usr/bin/nstool"),
        is_nstool=True,
        keys_path=None,
        tool_nsz=None,
        roms_dir=Path("."),
        cmd_timeout=30,
        parse_tool_output=lambda s: {},
        parse_languages=lambda s: "",
        detect_languages_from_filename=lambda n: "",
        determine_type=lambda tid, txt: "Base",
    )
    assert info is not None
    assert info["id"] == "0100ABCDEF000011"
    assert "Some Game" in info["name"]


def test_get_metadata_native_fallback():
    # Tool returns nothing
    def run_cmd(cmd, *, filebase=None, timeout=None):
        return DummyRes(stdout="")

    with patch("emumanager.switch.meta_extractor.SwitchPFS0Parser") as MockParser:
        instance = MockParser.return_value
        instance.get_title_id.return_value = "0100123456789000"

        info = get_metadata_info(
            Path("Unknown Game.nsp"),
            run_cmd=run_cmd,
            tool_metadata=Path("/usr/bin/nstool"),
            is_nstool=True,
            keys_path=None,
            tool_nsz=None,
            roms_dir=Path("."),
            cmd_timeout=30,
            parse_tool_output=lambda s: {},
            parse_languages=lambda s: "",
            detect_languages_from_filename=lambda n: "",
            determine_type=lambda tid, txt: "Base",
        )

        assert info is not None
        assert info["id"] == "0100123456789000"
        # Name logic: split by [ID], strip brackets.
        # If ID is not in filename, name_part = filepath.name.split(f"[{tid}]")[0] -> filepath.name
        # Then re.sub(REGEX_BRACKETS, "", name_part) -> "Unknown Game.nsp" (minus brackets if any)
        # Wait, split returns list. If separator not found, returns [original_string].
        # So name_part will be "Unknown Game.nsp".
        # Then strip() -> "Unknown Game.nsp".
        # So name should be "Unknown Game.nsp".
        assert info["name"] == "Unknown Game.nsp"
