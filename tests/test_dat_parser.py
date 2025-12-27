from emumanager.verification.dat_parser import DatDb, RomInfo, parse_dat_file


def test_dat_db_add_lookup():
    db = DatDb()
    rom = RomInfo(
        game_name="Test Game",
        rom_name="test.iso",
        size=1000,
        crc="12345678",
        md5="abcdef",
        sha1="1234567890abcdef",
    )

    db.add_rom(rom)

    # Lookup by CRC
    match = db.lookup(crc="12345678")
    assert match is not None
    assert match.game_name == "Test Game"

    # Lookup by MD5
    match = db.lookup(md5="abcdef")
    assert match is not None

    # Lookup by SHA1
    match = db.lookup(sha1="1234567890abcdef")
    assert match is not None

    # Lookup non-existent
    assert db.lookup(crc="00000000") is None


def test_dat_db_case_insensitive():
    db = DatDb()
    rom = RomInfo(game_name="Test Game", rom_name="test.iso", size=1000, crc="ABCDEF12")
    db.add_rom(rom)

    match = db.lookup(crc="abcdef12")
    assert match is not None


def test_parse_dat_file(tmp_path):
    dat_content = """<?xml version="1.0"?>
<datafile>
    <header>
        <name>Nintendo - GameCube</name>
        <version>20231223</version>
    </header>
    <game name="Super Mario Sunshine">
        <rom name="Super Mario Sunshine (USA).iso" size="1459978240" crc="B429E728"
             md5="0c6d2f5d0b0c4c9c7b0b0c4c9c7b0b0c"
             sha1="1234567890123456789012345678901234567890"/>
    </game>
</datafile>
"""
    dat_file = tmp_path / "test.dat"
    dat_file.write_text(dat_content)

    db = parse_dat_file(dat_file)

    assert db.name == "Nintendo - GameCube"
    assert db.version == "20231223"

    match = db.lookup(crc="B429E728")
    assert match is not None
    assert match.game_name == "Super Mario Sunshine"
    assert match.size == 1459978240
