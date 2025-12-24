from pathlib import Path
import re
from typing import Optional

# Regex for 3DS Product Code: 
# Starts with CTR, KTR, or TWL (DSi)
# Format: XXX-X-XXXX (e.g. CTR-P-AGME)
SERIAL_RE = re.compile(r"((?:CTR|KTR|TWL)-[A-Z0-9]-[A-Z0-9]{4})")

def get_metadata(path: Path) -> dict:
    """
    Extracts metadata from a 3DS game (.3ds, .cia, .3dz).
    Returns dict with keys: serial, title.
    """
    meta = {}
    
    if not path.is_file():
        return meta
        
    suffix = path.suffix.lower()
    if suffix not in (".3ds", ".cia", ".3dz", ".cci"):
        return meta
        
    try:
        with open(path, "rb") as f:
            # Read the first 1MB. The header and NCCH should be within this range.
            # For .3ds, the NCCH header starts at 0x4000 usually? 
            # Actually, let's just scan for the product code pattern.
            # It's usually reliable enough for this purpose.
            data = f.read(1024 * 1024) 
            
            # Search for the pattern
            # We decode to latin1 to search as string, or search bytes
            # Product codes are ASCII.
            
            # Try to find matches
            text = data.decode("latin-1", errors="ignore")
            matches = SERIAL_RE.findall(text)
            
            if matches:
                # Pick the first one that looks valid
                # Sometimes there are multiple, usually the first one is the game code.
                meta["serial"] = matches[0]
                
    except Exception:
        pass
        
    return meta
