from __future__ import annotations

from pathlib import Path

from emumanager.library import LibraryDB, LibraryEntry, normalize_game_name


def _mk_entry(path: str, system: str = "nes", size: int = 1, sha1: str | None = None):
    return LibraryEntry(
        path=path,
        system=system,
        size=size,
        mtime=0.0,
        crc32=None,
        md5=None,
        sha1=sha1,
        sha256=None,
        status="unknown",
        match_name=None,
        dat_name=None,
    )


def test_normalize_game_name_strips_tags_and_extension():
    assert normalize_game_name("Super Mario (USA) [v1.1].nes") == "super mario"
    assert normalize_game_name("Super-Mario_(Europe).zip") == "super mario"


def test_find_duplicates_by_normalized_name_groups_variants(tmp_path: Path):
    db_path = tmp_path / "library.db"
    db = LibraryDB(db_path=db_path)

    db.update_entry(_mk_entry(str(tmp_path / "Super Mario (USA).nes"), size=10))
    db.update_entry(_mk_entry(str(tmp_path / "Super Mario (Europe).nes"), size=11))
    db.update_entry(_mk_entry(str(tmp_path / "Zelda (USA).nes"), size=12))

    groups = db.find_duplicates_by_normalized_name()
    assert len(groups) == 1
    assert groups[0].kind == "name"
    assert groups[0].key == "super mario"
    assert groups[0].count == 2


def test_find_duplicates_by_hash_groups_same_sha1(tmp_path: Path):
    db_path = tmp_path / "library.db"
    db = LibraryDB(db_path=db_path)

    sha1 = "deadbeef"
    db.update_entry(_mk_entry(str(tmp_path / "a.nes"), size=20, sha1=sha1))
    db.update_entry(_mk_entry(str(tmp_path / "b.nes"), size=10, sha1=sha1))
    db.update_entry(_mk_entry(str(tmp_path / "c.nes"), size=5, sha1="other"))

    groups = db.find_duplicates_by_hash(prefer=("sha1",))
    assert len(groups) == 1
    g = groups[0]
    assert g.kind == "sha1"
    assert g.key == sha1
    assert g.count == 2
    # sorted by size desc
    assert Path(g.entries[0].path).name == "a.nes"
    assert Path(g.entries[1].path).name == "b.nes"
