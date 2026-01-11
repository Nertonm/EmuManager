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
    def validate_file(self, path: Path) -> bool: return path.suffix.lower() in self.get_supported_extensions()
    
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