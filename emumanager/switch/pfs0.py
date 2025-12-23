from __future__ import annotations
from pathlib import Path
from typing import Optional
import struct
import logging

logger = logging.getLogger(__name__)

class SwitchPFS0Parser:
    """
    Simple parser for PFS0 (NSP) files to extract metadata from Tickets.
    This allows getting Title ID without external tools like nstool/hactool
    if a Ticket (.tik) is present.
    """
    
    def __init__(self, filepath: Path):
        self.filepath = filepath

    def get_title_id(self) -> Optional[str]:
        if not self.filepath.exists():
            return None
            
        try:
            with open(self.filepath, "rb") as f:
                # Check Magic
                magic = f.read(4)
                if magic != b"PFS0":
                    return None
                
                # Read header
                num_files = struct.unpack("<I", f.read(4))[0]
                string_table_size = struct.unpack("<I", f.read(4))[0]
                f.read(4) # Reserved
                
                # Read file entries
                # Each entry is 24 bytes: offset (8), size (8), name_offset (4), reserved (4)
                entries = []
                for _ in range(num_files):
                    data = f.read(24)
                    offset = struct.unpack("<Q", data[0:8])[0]
                    size = struct.unpack("<Q", data[8:16])[0]
                    name_offset = struct.unpack("<I", data[16:20])[0]
                    entries.append({"offset": offset, "size": size, "name_offset": name_offset})
                
                # Read string table
                string_table = f.read(string_table_size)
                
                # Find .tik file
                tik_entry = None
                for entry in entries:
                    name_start = entry["name_offset"]
                    # Find null terminator
                    name_end = string_table.find(b"\x00", name_start)
                    name = string_table[name_start:name_end].decode("utf-8")
                    
                    if name.endswith(".tik"):
                        tik_entry = entry
                        break
                
                if not tik_entry:
                    return None
                
                # Calculate absolute offset of the ticket file
                # Header size = 16 + (24 * num_files) + string_table_size
                header_size = 16 + (24 * num_files) + string_table_size
                tik_abs_offset = header_size + tik_entry["offset"]
                
                # Seek to Ticket
                f.seek(tik_abs_offset)
                
                # Read Ticket
                # Title ID is usually at offset 0x2A0 in the ticket structure?
                # Let's check Ticket structure (v2/XS)
                # 0x000: Signature Type (4)
                # 0x004: Signature (256)
                # 0x104: ...
                # 0x2A0: Rights ID (16 bytes)
                # The Rights ID is usually Title ID (8 bytes) + Key Generation (8 bytes) ?
                # Actually, Rights ID = Title ID (8 bytes) + Key Gen (1 byte) + Reserved (7 bytes)
                # OR Title ID (8 bytes) + 8 bytes zeros.
                
                # Let's try reading at 0x2A0 relative to ticket start
                # But we need to be careful about ticket format (Common vs Personalized)
                # Standard Common Ticket size is usually 0x2C0 or larger.
                
                # Let's read a chunk and look for the Title ID pattern?
                # No, let's rely on the Rights ID offset.
                
                # Seek to Rights ID
                f.seek(tik_abs_offset + 0x2A0)
                rights_id = f.read(16)
                
                # Extract first 8 bytes as Title ID
                tid_bytes = rights_id[:8]
                title_id = tid_bytes.hex().upper()
                
                return title_id
                
        except Exception as e:
            logger.debug(f"Error parsing PFS0 {self.filepath}: {e}")
            return None
