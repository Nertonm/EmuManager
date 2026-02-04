from __future__ import annotations
from pathlib import Path
from typing import Any
from . import metadata, database
from ..common.system import SystemProvider

class PSPProvider(SystemProvider):
    @property
    def system_id(self) -> str: return "psp"
    @property
    def display_name(self) -> str: return "PlayStation Portable"
    def get_supported_extensions(self) -> set[str]: return {".iso", ".cso", ".pbp"}
    def extract_metadata(self, path: Path) -> dict[str, Any]:
        meta = metadata.get_metadata(path)
        serial = meta.get("serial")
        title = database.db.get_title(serial) if serial else meta.get("title")
        return {"serial": serial, "title": title or path.stem, "system": self.system_id}
    def get_preferred_compression(self) -> str | None: return "cso"
    def validate_file(self, path: Path) -> bool:
        """Valida arquivo PSP por extensão e magic bytes."""
        ext = path.suffix.lower()
        if ext not in self.get_supported_extensions():
            return False
        
        try:
            with open(path, 'rb') as f:
                header = f.read(16)
                
                # ISO: Verificar "CD001" no setor 16 (UMD usa ISO 9660)
                if ext == '.iso':
                    f.seek(0x8000)
                    iso_header = f.read(6)
                    if iso_header[1:6] == b'CD001':
                        return True
                
                # CSO: Magic "CISO"
                if ext == '.cso' and header[:4] == b'CISO':
                    return True
                
                # PBP: Magic "\x00PBP"
                if ext == '.pbp' and header[1:4] == b'PBP':
                    return True
                    
        except Exception:
            pass
        
        return True
    
    def get_ideal_filename(self, path: Path, metadata: dict[str, Any]) -> str:
        from ..common.system import default_ideal_filename
        return default_ideal_filename(path, metadata)

    def get_technical_info(self) -> dict[str, str]:
        return {
            "wiki": "https://www.ppsspp.org/",
            "bios": "Não.",
            "formats": ".cso (Recomendado), .iso",
            "notes": "Jogos mini/PSN são pastas com EBOOT.PBP."
        }

    def needs_conversion(self, path: Path) -> bool:
        return path.suffix.lower() == ".iso"