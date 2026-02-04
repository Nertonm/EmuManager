from __future__ import annotations
from pathlib import Path
from typing import Any
from . import metadata, database
from ..common.system import SystemProvider

class PS3Provider(SystemProvider):
    @property
    def system_id(self) -> str: return "ps3"
    @property
    def display_name(self) -> str: return "PlayStation 3"
    def get_supported_extensions(self) -> set[str]: return {".iso", ".pkg"}
    def extract_metadata(self, path: Path) -> dict[str, Any]:
        meta = metadata.get_metadata(path)
        serial = meta.get("serial")
        title = database.db.get_title(serial) if serial else meta.get("title")
        return {"serial": serial, "title": title or path.stem, "system": self.system_id}
    def get_preferred_compression(self) -> str | None: return "iso"
    def validate_file(self, path: Path) -> bool:
        """Valida arquivo PS3 por extensão, magic bytes e estrutura JB."""
        ext = path.suffix.lower()
        
        # Pastas JB (Jailbreak): devem ter PARAM.SFO
        if path.is_dir():
            param_sfo = path / "PARAM.SFO"
            ps3_game = path / "PS3_GAME" / "PARAM.SFO"
            return param_sfo.exists() or ps3_game.exists()
        
        if ext not in self.get_supported_extensions():
            return False
        
        try:
            with open(path, 'rb') as f:
                header = f.read(16)
                
                # ISO: Verificar "CD001" no setor 16
                if ext == '.iso':
                    f.seek(0x8000)
                    iso_header = f.read(6)
                    if iso_header[1:6] == b'CD001':
                        return True
                
                # PKG: Magic "\x7FPKG"
                if ext == '.pkg' and header[:4] == b'\x7fPKG':
                    return True
                    
        except Exception:
            pass
        
        return True

    def get_ideal_filename(self, path: Path, metadata: dict[str, Any]) -> str:
        from ..common.system import default_ideal_filename
        return default_ideal_filename(path, metadata)

    def get_technical_info(self) -> dict[str, str]:
        return {
            "wiki": "https://rpcs3.net/quickstart",
            "bios": "Sim (Instalar PS3UPDAT.PUP no emulador).",
            "formats": ".iso (Disco), .pkg (Digital)",
            "notes": "Jogos de disco podem ser ISO ou Pasta JB."
        }

    def needs_conversion(self, path: Path) -> bool:
        return False
