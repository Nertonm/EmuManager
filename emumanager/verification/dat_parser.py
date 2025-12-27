import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class RomInfo:
    game_name: str
    rom_name: str
    size: int
    crc: Optional[str] = None
    md5: Optional[str] = None
    sha1: Optional[str] = None


class DatDb:
    def __init__(self):
        self.crc_index: Dict[str, List[RomInfo]] = {}
        self.md5_index: Dict[str, RomInfo] = {}
        self.sha1_index: Dict[str, RomInfo] = {}
        self.name: str = ""
        self.version: str = ""

    def add_rom(self, rom: RomInfo):
        if rom.crc:
            crc = rom.crc.lower()
            if crc not in self.crc_index:
                self.crc_index[crc] = []
            self.crc_index[crc].append(rom)

        if rom.md5:
            self.md5_index[rom.md5.lower()] = rom

        if rom.sha1:
            self.sha1_index[rom.sha1.lower()] = rom

    def lookup(
        self, crc: str = None, md5: str = None, sha1: str = None
    ) -> Optional[RomInfo]:
        # Try SHA1 first (most unique)
        if sha1:
            res = self.sha1_index.get(sha1.lower())
            if res:
                return res

        # Try MD5
        if md5:
            res = self.md5_index.get(md5.lower())
            if res:
                return res

        # Try CRC (might have collisions, return first match or refine)
        if crc:
            matches = self.crc_index.get(crc.lower())
            if matches:
                # If we have multiple matches for CRC but no other hash provided,
                # we can't distinguish. Return the first one.
                # If we had other hashes but they didn't match (e.g. sha1 mismatch),
                # then we shouldn't be here if we checked them above.
                # But if the user ONLY provided CRC, we return the first match.
                return matches[0]

        return None


def parse_dat_file(dat_path: Path) -> DatDb:
    db = DatDb()
    try:
        tree = ET.parse(dat_path)
        root = tree.getroot()

        # Parse Header
        header = root.find("header")
        if header is not None:
            name_elem = header.find("name")
            if name_elem is not None:
                db.name = name_elem.text or ""
            version_elem = header.find("version")
            if version_elem is not None:
                db.version = version_elem.text or ""

        # Parse Games
        for game in root.findall("game"):
            game_name = game.get("name", "Unknown")

            for rom in game.findall("rom"):
                rom_name = rom.get("name", "Unknown")
                size_str = rom.get("size", "0")
                try:
                    size = int(size_str)
                except ValueError:
                    size = 0

                crc = rom.get("crc")
                md5 = rom.get("md5")
                sha1 = rom.get("sha1")

                info = RomInfo(
                    game_name=game_name,
                    rom_name=rom_name,
                    size=size,
                    crc=crc,
                    md5=md5,
                    sha1=sha1,
                )
                db.add_rom(info)

    except Exception:
        pass

    return db
