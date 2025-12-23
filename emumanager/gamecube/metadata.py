from pathlib import Path
from typing import Optional
import logging
from emumanager.converters.dolphin_converter import DolphinConverter

logger = logging.getLogger(__name__)

def get_metadata(file_path: Path) -> dict:
    """
    Extracts metadata (Game ID, Title, etc.) from a GameCube file.
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
            header = f.read(0x200) # Read enough for header
            if len(header) < 6:
                return {}
            
            if header.startswith(b"RVZ"):
                return {}

            # Game ID at 0x00 (6 bytes)
            try:
                game_id = header[:6].decode("ascii")
                if game_id.isalnum():
                    meta["game_id"] = game_id
            except UnicodeDecodeError:
                pass

            # Internal Name at 0x20 (usually 32 bytes or null terminated)
            # Actually for GC it's at 0x20.
            try:
                # Read up to null byte
                raw_name = header[0x20:0x60]
                name = raw_name.split(b'\x00')[0].decode("utf-8", errors="ignore").strip()
                if name:
                    meta["internal_name"] = name
            except Exception:
                pass
                
    except Exception as e:
        logger.error(f"Error reading GameCube header from {file_path}: {e}")
    
    return meta

def get_gamecube_serial(file_path: Path) -> Optional[str]:
    """
    Extracts the Game ID (Serial) from a GameCube ISO/GCM/RVZ file.
    """
    meta = get_metadata(file_path)
    return meta.get("game_id")
