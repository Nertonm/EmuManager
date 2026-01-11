from __future__ import annotations
from pathlib import Path
from typing import Any
from . import metadata
from ..common.system import SystemProvider

class N3DSProvider(SystemProvider):
    @property
    def system_id(self) -> str: return "3ds"
    @property
    def display_name(self) -> str: return "Nintendo 3DS"
    def get_supported_extensions(self) -> set[str]: return {".3ds", ".cia", ".3dz", ".cci"}
    def extract_metadata(self, path: Path) -> dict[str, Any]:
        meta = metadata.get_metadata(path)
        return {"serial": meta.get("serial"), "title": path.stem, "system": self.system_id}
    def get_preferred_compression(self) -> str | None: return None
    def validate_file(self, path: Path) -> bool: return path.suffix.lower() in self.get_supported_extensions()
    
    def get_ideal_filename(self, path: Path, metadata: dict[str, Any]) -> str:
        from ..common.system import default_ideal_filename
        return default_ideal_filename(path, metadata)

    def get_technical_info(self) -> dict[str, str]:
        return {
            "wiki": "https://citra-emu.org/wiki/dumping-game-cartridges/",
            "bios": "Não (exceto para Menu Home).",
            "formats": ".3ds, .cia (Instaláveis)",
            "notes": "Citra roda melhor ROMs 'Decrypted'. Arquivos CIA devem ser instalados no emulador."
        }

    def needs_conversion(self, path: Path) -> bool:
        return False