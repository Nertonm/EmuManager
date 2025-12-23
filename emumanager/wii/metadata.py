from pathlib import Path
from typing import Optional
import logging
from emumanager.converters.dolphin_converter import DolphinConverter

logger = logging.getLogger(__name__)

def get_metadata(file_path: Path) -> dict:
    """
    Extracts metadata (Game ID, Title, etc.) from a Wii file.
    Returns a dict with keys: game_id, internal_name, revision.
    """
    if not file_path.exists():
        return {}

    # Try dolphin-tool first
    try:
        converter = DolphinConverter()
        if converter.check_tool():
            meta = converter.get_metadata(file_path)
            if meta:
                return meta
    except Exception as e:
        logger.debug(f"dolphin-tool metadata extraction failed: {e}")

    # Fallback to binary reading
    meta = {}
    try:
        with open(file_path, "rb") as f:
            header = f.read(0x200 + 0x60) # Read enough for WBFS header + disc header
            
            offset = 0
            if header.startswith(b"WBFS"):
                offset = 512
            
            if len(header) < offset + 6:
                return {}

            # Game ID
            try:
                game_id = header[offset:offset+6].decode("ascii")
                if game_id.isalnum():
                    meta["game_id"] = game_id
            except UnicodeDecodeError:
                pass

            # Internal Name at offset + 0x20
            try:
                raw_name = header[offset+0x20:offset+0x60]
                name = raw_name.split(b'\x00')[0].decode("utf-8", errors="ignore").strip()
                if name:
                    meta["internal_name"] = name
            except Exception:
                pass
                
    except Exception as e:
        logger.error(f"Error reading Wii header from {file_path}: {e}")
    
    return meta

def get_wii_serial(file_path: Path) -> Optional[str]:
    """
    Extracts the Game ID (Serial) from a Wii ISO/WBFS/RVZ file.
    """
    meta = get_metadata(file_path)
    return meta.get("game_id")
