from __future__ import annotations
from pathlib import Path
from typing import Any
from . import metadata
from ..common.system import SystemProvider

class GameCubeProvider(SystemProvider):
    @property
    def system_id(self) -> str: return "dolphin"
    @property
    def display_name(self) -> str: return "Dolphin (GC/Wii)"
    def get_supported_extensions(self) -> set[str]: return {".iso", ".gcm", ".rvz", ".wbfs"}
    
    def extract_metadata(self, path: Path) -> dict[str, Any]:
        meta = metadata.get_metadata(path)
        return {"serial": meta.get("game_id"), "title": meta.get("internal_name") or path.stem, "system": self.system_id, "platform": "GameCube"}
    
    def get_preferred_compression(self) -> str | None: return "rvz"
    
    def validate_file(self, path: Path) -> bool:
        """Valida arquivo GameCube por extensão e magic bytes."""
        ext = path.suffix.lower()
        if ext not in self.get_supported_extensions():
            return False
        
        # Validação por magic bytes
        try:
            with open(path, 'rb') as f:
                header = f.read(32)
                
                # GameCube ISO: Magic bytes no offset 0x1C (Game ID)
                if ext in {'.iso', '.gcm'}:
                    # GameCube ISOs têm Game ID nos primeiros bytes
                    # Formato: GXXE01 (6 bytes ASCII)
                    game_id = header[:6]
                    if game_id and all(32 <= b < 127 for b in game_id):
                        return True
                
                # RVZ: Magic "RVZ\x01"
                if ext == '.rvz' and header[:3] == b'RVZ':
                    return True
                    
        except Exception:
            # Se falhar leitura, aceitar baseado em extensão
            return True
        
        return False
    
    def get_ideal_filename(self, path: Path, metadata: dict[str, Any]) -> str:
        from ..common.system import default_ideal_filename
        return default_ideal_filename(path, metadata)

    def get_technical_info(self) -> dict[str, str]:
        return {
            "wiki": "https://br.dolphin-emu.org/docs/guides/ripping-games/",
            "bios": "Não.",
            "formats": ".rvz (Recomendado), .iso, .gcm (GC), .wbfs (Wii)",
            "notes": "GameCube e Wii unificados. RVZ é o formato ideal para ambos."
        }

    def needs_conversion(self, path: Path) -> bool:
        return path.suffix.lower() in {".iso", ".gcm"}