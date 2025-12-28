#!/usr/bin/env python3
"""
Script to generate a mock ROM collection for development and testing.
Usage: python3 scripts/create_mock_roms.py [target_dir]
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure we can import from the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from emumanager import architect

def create_dummy_file(path: Path, size_bytes: int = 1024):
    """Create a dummy file with random content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(os.urandom(size_bytes))

def create_text_file(path: Path, content: str = "Mock file"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def main():
    parser = argparse.ArgumentParser(description="Create mock ROMs for testing")
    parser.add_argument("target_dir", nargs="?", default="./mock_library", help="Target directory")
    args = parser.parse_args()

    base = Path(args.target_dir).resolve()
    print(f"Creating mock library at: {base}")

    # 1. Initialize structure using the actual architect module
    print("Initializing structure...")
    architect.main([str(base)])

    roms = base / "roms"
    
    # 2. Create Switch Mock Files
    print("Creating Switch mocks...")
    switch_dir = roms / "switch"
    # Valid files
    create_dummy_file(switch_dir / "Super Mario Odyssey [0100000000010000][v0].nsp")
    create_dummy_file(switch_dir / "The Legend of Zelda BOTW [01007EF00011E000][v0].xci")
    create_dummy_file(switch_dir / "Celeste [0100AC5003292000][v0].nsz")
    # Unorganized files
    create_dummy_file(switch_dir / "Unorganized_Game.nsp")
    # Junk
    create_text_file(switch_dir / "info.txt", "Some info")
    create_text_file(switch_dir / "website.url", "[InternetShortcut]\nURL=http://google.com")
    # Keys (needed for tools)
    create_text_file(base / "keys.txt", "prod.keys mock content")

    # 3. Create PS2 Mock Files
    print("Creating PS2 mocks...")
    ps2_dir = roms / "ps2"
    create_dummy_file(ps2_dir / "God of War (USA).iso")
    create_dummy_file(ps2_dir / "Metal Gear Solid 3 (Europe).iso")
    create_dummy_file(ps2_dir / "Shadow of the Colossus.chd")
    # File with serial in name
    create_dummy_file(ps2_dir / "Final Fantasy X (SLUS-20312).iso")

    # 4. Create GameCube/Wii Mock Files
    print("Creating GameCube/Wii mocks...")
    gc_dir = roms / "gamecube"
    create_dummy_file(gc_dir / "Super Smash Bros Melee.iso")
    create_dummy_file(gc_dir / "Metroid Prime.rvz")
    
    wii_dir = roms / "wii"
    create_dummy_file(wii_dir / "Wii Sports.wbfs")
    create_dummy_file(wii_dir / "Mario Kart Wii.iso")

    # 5. Create Retro Mocks
    print("Creating Retro mocks...")
    create_dummy_file(roms / "snes" / "Super Mario World.sfc")
    create_dummy_file(roms / "nes" / "Super Mario Bros.nes")
    create_dummy_file(roms / "gba" / "Pokemon Ruby.gba")
    create_dummy_file(roms / "n64" / "Super Mario 64.z64")

    # 6. Create PS3 Mocks
    print("Creating PS3 mocks...")
    ps3_dir = roms / "ps3"
    create_dummy_file(ps3_dir / "The Last of Us.iso")
    create_dummy_file(ps3_dir / "Uncharted 2.pkg")
    # Folder format
    (ps3_dir / "God of War III [BCUS98111]").mkdir(parents=True, exist_ok=True)
    create_dummy_file(ps3_dir / "God of War III [BCUS98111]" / "PS3_GAME" / "PARAM.SFO")

    # 7. Create BIOS mocks
    print("Creating BIOS mocks...")
    bios_dir = base / "bios"
    create_dummy_file(bios_dir / "scph1001.bin")
    create_dummy_file(bios_dir / "bios7.bin")
    create_dummy_file(bios_dir / "bios9.bin")

    print("\nMock library created successfully!")
    print(f"Run the GUI and open: {base}")

if __name__ == "__main__":
    main()
