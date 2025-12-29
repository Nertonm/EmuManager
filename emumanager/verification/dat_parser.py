import re
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
    dat_name: Optional[str] = None


class DatDb:
    def __init__(self):
        self.crc_index: Dict[str, List[RomInfo]] = {}
        self.md5_index: Dict[str, List[RomInfo]] = {}
        self.sha1_index: Dict[str, List[RomInfo]] = {}
        self.name: str = ""
        self.version: str = ""

    def add_rom(self, rom: RomInfo):
        if rom.crc:
            crc = rom.crc.lower()
            if crc not in self.crc_index:
                self.crc_index[crc] = []
            self.crc_index[crc].append(rom)

        if rom.md5:
            md5 = rom.md5.lower()
            if md5 not in self.md5_index:
                self.md5_index[md5] = []
            self.md5_index[md5].append(rom)

        if rom.sha1:
            sha1 = rom.sha1.lower()
            if sha1 not in self.sha1_index:
                self.sha1_index[sha1] = []
            self.sha1_index[sha1].append(rom)

    def lookup(
        self, crc: str = None, md5: str = None, sha1: str = None
    ) -> List[RomInfo]:
        # Return all matches
        matches = []
        if sha1:
            matches.extend(self.sha1_index.get(sha1.lower(), []))
        elif md5:
            matches.extend(self.md5_index.get(md5.lower(), []))
        elif crc:
            matches.extend(self.crc_index.get(crc.lower(), []))
        
        # Deduplicate by object identity
        return list({id(r): r for r in matches}.values())


def parse_dat_file(dat_path: Path) -> DatDb:
    # Check for XML signature
    try:
        with open(dat_path, "rb") as f:
            head = f.read(512)
        if b"<?xml" in head or b"<datafile>" in head:
            return _parse_xml_dat(dat_path)
    except Exception:
        pass
    
    # Fallback to ClrMamePro
    return _parse_clrmamepro(dat_path)


def _parse_xml_dat(dat_path: Path) -> DatDb:
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
                    dat_name=db.name,
                )
                db.add_rom(info)

    except Exception:
        pass

    return db


def _parse_clrmamepro(dat_path: Path) -> DatDb:
    db = DatDb()
    try:
        content = dat_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return db

    # Extract header info (clrmamepro block)
    header_match = re.search(r'clrmamepro\s*\((.*?)\)', content, re.DOTALL)
    if header_match:
        header_content = header_match.group(1)
        name_match = re.search(r'name\s+"([^"]+)"', header_content)
        if name_match:
            db.name = name_match.group(1)
        version_match = re.search(r'version\s+"([^"]+)"', header_content)
        if version_match:
            db.version = version_match.group(1)

    # Iterate over "game (" occurrences
    iterator = re.finditer(r'game\s*\(', content)
    for match in iterator:
        start = match.end()
        depth = 1
        end = start
        while depth > 0 and end < len(content):
            if content[end] == '(':
                depth += 1
            elif content[end] == ')':
                depth -= 1
            end += 1
            
        if depth == 0:
            game_block = content[start:end-1]
            _parse_game_block(db, game_block)
            
    return db


def _parse_game_block(db, block_content):
    # Extract game name
    name_match = re.search(r'name\s+"([^"]+)"', block_content)
    game_name = name_match.group(1) if name_match else "Unknown"
    
    # Find roms
    rom_iter = re.finditer(r'rom\s*\(', block_content)
    for match in rom_iter:
        start = match.end()
        depth = 1
        end = start
        while depth > 0 and end < len(block_content):
            if block_content[end] == '(':
                depth += 1
            elif block_content[end] == ')':
                depth -= 1
            end += 1
            
        if depth == 0:
            rom_content = block_content[start:end-1]
            _parse_rom(db, game_name, rom_content)


def _parse_rom(db, game_name, rom_content):
    name_match = re.search(r'name\s+"([^"]+)"', rom_content)
    rom_name = name_match.group(1) if name_match else "Unknown"
    
    size_match = re.search(r'size\s+(\d+)', rom_content)
    size = int(size_match.group(1)) if size_match else 0
    
    crc_match = re.search(r'crc\s+([0-9A-Fa-f]+)', rom_content)
    crc = crc_match.group(1) if crc_match else None
    
    md5_match = re.search(r'md5\s+([0-9A-Fa-f]+)', rom_content)
    md5 = md5_match.group(1) if md5_match else None
    
    sha1_match = re.search(r'sha1\s+([0-9A-Fa-f]+)', rom_content)
    sha1 = sha1_match.group(1) if sha1_match else None
    
    info = RomInfo(
        game_name=game_name,
        rom_name=rom_name,
        size=size,
        crc=crc,
        md5=md5,
        sha1=sha1,
        dat_name=db.name
    )
    db.add_rom(info)


def merge_dbs(target: DatDb, source: DatDb):
    """Merge source DatDb into target DatDb."""
    for crc, roms in source.crc_index.items():
        if crc not in target.crc_index:
            target.crc_index[crc] = []
        target.crc_index[crc].extend(roms)

    for md5, roms in source.md5_index.items():
        if md5 not in target.md5_index:
            target.md5_index[md5] = []
        target.md5_index[md5].extend(roms)

    for sha1, roms in source.sha1_index.items():
        if sha1 not in target.sha1_index:
            target.sha1_index[sha1] = []
        target.sha1_index[sha1].extend(roms)
