from emumanager.switch.cli import (
    determine_region,
    determine_type,
    get_base_id,
    get_file_hash,
    get_metadata,
    parse_languages,
    sanitize_name,
)


def test_sanitize_name_basic():
    assert sanitize_name("Game Title [1234567890ABCDEF]") == "Game Title"
    assert sanitize_name("CoolGame (nsw2u)") == "CoolGame"
    # long name truncation
    long = "A" * 200
    assert len(sanitize_name(long)) <= 120


def test_parse_languages():
    out = "Languages: English, Japanese, French"
    assert parse_languages(out) in ("[En,Fr,Ja]", "[En,Ja,Fr]")


def test_determine_region_from_filename_and_langs():
    assert determine_region("SomeGame USA v1", "") in ("(USA)", "(World)")
    assert determine_region("Title (JPN) - Demo", "") == "(JPN)"
    assert determine_region("Title", "[Ja]") == "(JPN)"


def test_determine_type():
    assert determine_type("0100ABCDEF000000", None) in ("Base", "DLC", "UPD")


def test_get_base_id():
    assert get_base_id("0100ABCDEF000000") is not None


def test_get_file_hash_fallback(tmp_path):
    p = tmp_path / "small.bin"
    p.write_bytes(b"hello")
    h = get_file_hash(p)
    assert isinstance(h, str)
    assert len(h) > 0


def test_get_metadata_fallback_from_filename(tmp_path):
    p = tmp_path / "Cool Game [0100ABCDEF000000].nsp"
    p.write_bytes(b"x")
    meta = get_metadata(
        p,
        tool_metadata=None,
        is_nstool=False,
        keys_path=None,
        roms_dir=tmp_path,
        tool_nsz=None,
        cmd_timeout=None,
    )
    assert meta is not None
    assert meta["id"] == "0100ABCDEF000000"


def test_safe_move_creates_unique(tmp_path):
    src = tmp_path / "test.nsp"
    src.write_bytes(b"one")
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    dest = dest_dir / "test.nsp"
    # create existing file with different content to force collision rename
    dest.write_bytes(b"different")

    # import a minimal args shim
    class A:
        pass

    import logging

    import emumanager.switch.cli as so

    so.args = A()
    so.args.dry_run = False
    so.args.dup_check = "fast"
    moved = so.safe_move(src, dest, args=so.args, logger=logging.getLogger("test"))
    assert moved is True
    # ensure a file with _COPY exists
    copies = list(dest_dir.glob("test*_COPY_*"))
    assert len(copies) >= 1


def test_get_metadata_nsz_decompression_fallback(monkeypatch, tmp_path):
    """Simulate a case where initial metadata tool returns incomplete data for
    a .nsz file. The code should attempt decompression (nsz) into a tempdir
    and then run the metadata tool on the decompressed file."""
    import types

    import emumanager.switch.cli as so

    # Prepare a fake .nsz file
    nsf = tmp_path / "Some Game [0100ABCDEF000001].nsz"
    nsf.write_bytes(b"fake")

    # Ensure module globals indicate tools available
    tool_nsz = tmp_path / "nsz"
    tool_metadata = tmp_path / "meta"
    is_nstool = True
    keys_path = tmp_path / "prod.keys"

    # Create a controlled extraction dir that our monkeypatched TempDir yields
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()

    # Monkeypatch TemporaryDirectory to a context manager yielding extract_dir
    class DummyTemp:
        def __init__(self, *a, **k):
            self.name = str(extract_dir)

        def __enter__(self):
            return self.name

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(so.tempfile, "TemporaryDirectory", DummyTemp)

    # Prepare subprocess.run side effects
    def fake_run(cmd, capture_output=False, text=False, check=False, **kwargs):
        cmd_str = " ".join(map(str, cmd))
        # First call: metadata tool on .nsz -> returns stdout without Title ID
        if str(tool_metadata) in cmd_str and str(nsf) in cmd_str:
            return types.SimpleNamespace(stdout="Name: \n", stderr="", returncode=0)
        # nsz decompression call -> create an extracted .nsp inside extract_dir
        if str(tool_nsz) in cmd_str and "-D" in cmd_str:
            out_file = extract_dir / "Some Game [0100ABCDEF000001].nsp"
            out_file.write_bytes(b"extracted")
            return types.SimpleNamespace(stdout="decompressed", stderr="", returncode=0)
        # metadata tool on decompressed file -> return full metadata
        if str(tool_metadata) in cmd_str and str(extract_dir) in cmd_str:
            return types.SimpleNamespace(
                stdout="Name: Some Game\nTitle ID: 0100ABCDEF000001\n"
                "Display Version: 1.0",
                stderr="",
                returncode=0,
            )
        # default fallback
        return types.SimpleNamespace(stdout="", stderr="", returncode=1)

    monkeypatch.setattr(so.subprocess, "run", fake_run)

    meta = so.get_metadata(
        nsf,
        tool_metadata=tool_metadata,
        is_nstool=is_nstool,
        keys_path=keys_path,
        roms_dir=tmp_path,
        tool_nsz=tool_nsz,
        cmd_timeout=None,
    )
    assert meta is not None
    assert meta["id"] == "0100ABCDEF000001"
    assert "Some Game" in (meta["name"] or "")
