from __future__ import annotations
from pathlib import Path
from typing import Any
from . import metadata
from ..common.system import SystemProvider

class WiiProvider(SystemProvider):
    @property
    def system_id(self) -> str: return "dolphin"
    @property
    def display_name(self) -> str: return "Dolphin (GC/Wii)"
    def get_supported_extensions(self) -> set[str]: return {".iso", ".wbfs", ".rvz", ".gcm"}
    
    def extract_metadata(self, path: Path) -> dict[str, Any]:
        meta = metadata.get_metadata(path)
        return {"serial": meta.get("game_id"), "title": meta.get("internal_name") or path.stem, "system": self.system_id, "platform": "Wii"}
    
    def get_preferred_compression(self) -> str | None: return "rvz"
    def validate_file(self, path: Path) -> bool:
        """Valida arquivo Wii por extensão e magic bytes."""
        ext = path.suffix.lower()
        if ext not in self.get_supported_extensions():
            return False
        
        try:
            with open(path, 'rb') as f:
                header = f.read(32)
                
                # Wii ISO: Game ID nos primeiros 6 bytes (ASCII)
                if ext == '.iso':
                    game_id = header[:6]
                    if game_id and all(32 <= b < 127 for b in game_id):
                        return True
                
                # WBFS: Magic "WBFS"
                if ext == '.wbfs' and header[:4] == b'WBFS':
                    return True
                
                # RVZ: Magic "RVZ\x01"
                if ext == '.rvz' and header[:3] == b'RVZ':
                    return True
                    
        except Exception:
            pass
        
        return True
    
    def get_ideal_filename(self, path: Path, metadata: dict[str, Any]) -> str:
        from ..common.system import default_ideal_filename
        return default_ideal_filename(path, metadata)

    def get_technical_info(self) -> dict[str, str]:
        return {
            "wiki": "https://br.dolphin-emu.org/",
            "bios": "Não.",
            "formats": ".rvz (Recomendado), .wbfs (Wii), .gcm/.iso (GC/Wii)",
            "notes": "GameCube e Wii unificados sob Dolphin. RVZ é recomendado para ambos."
        }

    def needs_conversion(self, path: Path) -> bool:
        return path.suffix.lower() in {".iso", ".wbfs", ".gcm"}
        return path.suffix.lower() in {".iso", ".wbfs"}