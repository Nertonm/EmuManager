from emumanager.switch import main_helpers as mh


def test_build_new_filename_basic():
    fname = mh.__dict__["build_new_filename"](
        "Cool Game", "0100ABCDEF000020", "v1", ".nsp"
    )
    assert "Cool Game [0100ABCDEF000020]" in fname
    assert fname.endswith(".nsp")


def test_build_new_filename_no_ver():
    fname = mh.__dict__["build_new_filename"]("G", "0100ABCDEF000021", "", ".nsz")
    assert fname == "G [0100ABCDEF000021].nsz"


def test_get_dest_folder_truncation(tmp_path):
    roms = tmp_path
    region = "X" * 300
    dest = mh.__dict__["get_dest_folder"](roms, region)
    assert str(dest).startswith(str(roms))
    # folder name truncated to <=200
    assert len(dest.name) <= 200


def test_make_catalog_entry(tmp_path):
    clean_name = "My Game"
    meta = {
        "id": "0100ABCDEF000022",
        "type": "Base",
        "ver": "v1",
        "langs": "En",
    }
    suffix = ".nsp"
    target = tmp_path / "dest.nsp"
    row = mh.__dict__["make_catalog_entry"](clean_name, meta, suffix, target, "(World)")
    assert row[0] == clean_name
    assert row[1] == meta["id"]
    assert row[6] == suffix
    assert row[7] == str(target)
