import pytest
from pathlib import Path
from emumanager.verification.dat_manager import find_dat_for_system

def test_find_dat_for_system(tmp_path):
    dats_root = tmp_path / "dats"
    ni_dir = dats_root / "no-intro"
    rd_dir = dats_root / "redump"
    ni_dir.mkdir(parents=True)
    rd_dir.mkdir(parents=True)
    
    # Create dummy DATs
    (ni_dir / "Nintendo - Nintendo Entertainment System (20220101).dat").touch()
    (ni_dir / "Nintendo - Game Boy.dat").touch()
    (rd_dir / "Sony - PlayStation 2 (20230505).dat").touch()
    
    # Test NES (No-Intro)
    found = find_dat_for_system(dats_root, "nes")
    assert found is not None
    assert "Nintendo Entertainment System" in found.name
    
    # Test PS2 (Redump)
    found = find_dat_for_system(dats_root, "ps2")
    assert found is not None
    assert "PlayStation 2" in found.name
    
    # Test Unknown
    found = find_dat_for_system(dats_root, "unknown_sys")
    assert found is None
    
    # Test System with no DAT
    found = find_dat_for_system(dats_root, "xbox") # We didn't create xbox dat
    assert found is None

def test_find_dat_preference(tmp_path):
    dats_root = tmp_path / "dats"
    ni_dir = dats_root / "no-intro"
    ni_dir.mkdir(parents=True)
    
    # Create two versions
    (ni_dir / "Nintendo - Nintendo Entertainment System (20210101).dat").touch()
    (ni_dir / "Nintendo - Nintendo Entertainment System (20220101).dat").touch()
    
    found = find_dat_for_system(dats_root, "nes")
    assert "20220101" in found.name # Should pick the "newer" one (lexicographically last)
