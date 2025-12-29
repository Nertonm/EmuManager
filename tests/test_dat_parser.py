import pytest
from pathlib import Path
from emumanager.verification.dat_parser import parse_dat_file, DatDb, RomInfo

# Sample XML DAT content
XML_DAT_CONTENT = """<?xml version="1.0"?>
<datafile>
    <header>
        <name>Nintendo - GameCube</name>
        <version>20231224</version>
    </header>
    <game name="Luigi's Mansion (USA)">
        <rom name="Luigi's Mansion (USA).iso" size="1459978240" crc="12345678" md5="aabbccddeeff00112233445566778899" sha1="11223344556677889900aabbccddeeff00112233"/>
    </game>
    <game name="Super Mario Sunshine (USA)">
        <rom name="Super Mario Sunshine (USA).iso" size="1459978240" crc="87654321" md5="99887766554433221100ffeeddccbbaa" sha1="33221100ffeeddccbbaa00998877665544332211"/>
    </game>
</datafile>
"""

# Sample ClrMamePro DAT content
CLRMAMEPRO_DAT_CONTENT = """
clrmamepro (
	name "Nintendo - GameCube"
	version "20231224"
)

game (
	name "Luigi's Mansion (USA)"
	rom ( name "Luigi's Mansion (USA).iso" size 1459978240 crc 12345678 md5 aabbccddeeff00112233445566778899 sha1 11223344556677889900aabbccddeeff00112233 )
)

game (
	name "Super Mario Sunshine (USA)"
	rom ( name "Super Mario Sunshine (USA).iso" size 1459978240 crc 87654321 md5 99887766554433221100ffeeddccbbaa sha1 33221100ffeeddccbbaa00998877665544332211 )
)
"""

def test_dat_db_add_and_lookup():
    db = DatDb()
    rom = RomInfo(
        game_name="Test Game",
        rom_name="test.iso",
        size=1000,
        crc="12345678",
        md5="aabbcc",
        sha1="112233"
    )
    db.add_rom(rom)

    # Test lookups
    assert len(db.lookup(crc="12345678")) == 1
    assert len(db.lookup(md5="aabbcc")) == 1
    assert len(db.lookup(sha1="112233")) == 1
    
    # Test case insensitivity
    assert len(db.lookup(crc="12345678".upper())) == 1
    
    # Test not found
    assert len(db.lookup(crc="00000000")) == 0

    # Test object identity
    found = db.lookup(crc="12345678")[0]
    assert found.game_name == "Test Game"

@pytest.mark.parametrize("dat_content, expected_name", [
    (XML_DAT_CONTENT, "Nintendo - GameCube"),
    (CLRMAMEPRO_DAT_CONTENT, "Nintendo - GameCube")
])
def test_parse_dat_file(tmp_path, dat_content, expected_name):
    d = tmp_path / "temp.dat"
    d.write_text(dat_content, encoding="utf-8")
    
    db = parse_dat_file(d)
    
    assert db.name == expected_name
    assert db.version == "20231224"
    
    # Check if games were parsed
    luigi = db.lookup(crc="12345678")
    assert len(luigi) == 1
    assert luigi[0].game_name == "Luigi's Mansion (USA)"
    assert luigi[0].size == 1459978240
    
    mario = db.lookup(crc="87654321")
    assert len(mario) == 1
    assert mario[0].game_name == "Super Mario Sunshine (USA)"

def test_parse_invalid_file(tmp_path):
    d = tmp_path / "invalid.dat"
    d.write_text("Not a valid DAT file", encoding="utf-8")
    
    # Should probably return empty DB or raise error depending on implementation
    # Based on code reading, _parse_clrmamepro might try to parse it but find nothing
    db = parse_dat_file(d)
    assert isinstance(db, DatDb)
    assert len(db.crc_index) == 0

def test_dat_db_deduplication():
    db = DatDb()
    rom = RomInfo(
        game_name="Test",
        rom_name="test.iso",
        size=100,
        crc="1111",
        md5="2222",
        sha1="3333"
    )
    db.add_rom(rom)
    
    # Lookup with multiple hashes should return the same object once
    results = db.lookup(crc="1111", md5="2222")
    assert len(results) == 1
    assert results[0] is rom