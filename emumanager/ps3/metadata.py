from pathlib import Path
import re
from emumanager.common.sfo import SfoParser

# Regex for PS3 Serial: 4 letters + optional separator + 5 digits (e.g. BLUS12345, BLUS-12345)
SERIAL_RE = re.compile(r"([A-Z]{4})[_-]?(\d{5})")

def _parse_sfo_file(sfo_path: Path) -> dict:
    meta = {}
    try:
        with open(sfo_path, "rb") as f:
            data = f.read()
            parser = SfoParser(data)
            if parser.get("TITLE_ID"):
                meta["serial"] = parser.get("TITLE_ID")
            if parser.get("TITLE"):
                meta["title"] = parser.get("TITLE")
            if parser.get("VERSION"):
                meta["version"] = parser.get("VERSION")
    except Exception:
        pass
    return meta

def _scan_for_sfo(file_path: Path, max_size: int = 10 * 1024 * 1024) -> dict:
    """
    Scans a binary file (ISO/PKG) for the PARAM.SFO header and extracts metadata.
    Scans up to max_size bytes (default 10MB).
    """
    meta = {}
    magic = b"\x00PSF\x01\x01\x00\x00"
    
    try:
        with open(file_path, "rb") as f:
            # Read the beginning of the file
            data = f.read(max_size)
            idx = data.find(magic)
            
            if idx != -1:
                # SFO found. Take 4KB slice which is usually enough for SFO
                sfo_data = data[idx:idx+4096]
                parser = SfoParser(sfo_data)
                
                if parser.get("TITLE_ID"):
                    meta["serial"] = parser.get("TITLE_ID")
                if parser.get("TITLE"):
                    meta["title"] = parser.get("TITLE")
                if parser.get("VERSION"):
                    meta["version"] = parser.get("VERSION")
    except Exception:
        pass
        
    return meta

def get_metadata(path: Path) -> dict:
    """
    Extracts metadata from a PS3 game (folder or file).
    Returns dict with keys: serial, title, version.
    """
    meta = {}
    
    # 1. Try parsing PARAM.SFO if it's a folder
    if path.is_dir():
        sfo_path = path / "PARAM.SFO"
        if not sfo_path.exists():
            sfo_path = path / "PS3_GAME" / "PARAM.SFO"
        
        if sfo_path.exists():
            meta = _parse_sfo_file(sfo_path)
            
    # 2. If it's a file (ISO/PKG), scan for SFO
    elif path.is_file() and path.suffix.lower() in (".iso", ".pkg", ".bin"):
        meta = _scan_for_sfo(path)

    # 3. If no serial found, try filename regex
    if not meta.get("serial"):
        match = SERIAL_RE.search(path.name)
        if match:
            # Combine parts to form serial without separator if needed, or just take the whole match and clean it later
            # Group 1 is letters, Group 2 is digits
            meta["serial"] = f"{match.group(1)}{match.group(2)}"
            
    # Clean up serial
    if meta.get("serial"):
        meta["serial"] = meta["serial"].replace("-", "").strip()
        
    return meta
