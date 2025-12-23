from pathlib import Path
import re
from emumanager.common.sfo import SfoParser

# Regex for PSP Serial: 4 letters + 5 digits (e.g. ULUS10041)
# Sometimes with dash: ULUS-10041
SERIAL_RE = re.compile(r"([A-Z]{4})[_-]?(\d{5})")

def _scan_for_sfo(file_path: Path, max_size: int = 5 * 1024 * 1024) -> dict:
    """
    Scans a binary file (ISO/CSO) for the PARAM.SFO header and extracts metadata.
    Scans up to max_size bytes (default 5MB).
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
                
                if parser.get("DISC_ID"):
                    meta["serial"] = parser.get("DISC_ID")
                elif parser.get("TITLE_ID"):
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
    Extracts metadata from a PSP game (ISO/CSO/PBP).
    Returns dict with keys: serial, title, version.
    """
    meta = {}
    
    # 1. If it's a file (ISO/CSO/PBP), scan for SFO
    if path.is_file() and path.suffix.lower() in (".iso", ".cso", ".pbp"):
        meta = _scan_for_sfo(path)

    # 2. If no serial found, try filename regex
    if not meta.get("serial"):
        match = SERIAL_RE.search(path.name)
        if match:
            meta["serial"] = f"{match.group(1)}{match.group(2)}"
            
    # Clean up serial
    if meta.get("serial"):
        meta["serial"] = meta["serial"].replace("-", "").strip()
        
    return meta
