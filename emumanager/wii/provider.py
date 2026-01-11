from __future__ import annotations
from pathlib import Path
from typing import Any
from . import metadata
from ..common.system import SystemProvider

class WiiProvider(SystemProvider):
    @property
    def system_id(self) -> str: return "wii"
    @property
    def display_name(self) -> str: return "Wii"
    def get_supported_extensions(self) -> set[str]: return {".iso", ".wbfs", ".rvz"}
    
    def extract_metadata(self, path: Path) -> dict[str, Any]:
        meta = metadata.get_metadata(path)
        return {"serial": meta.get("game_id"), "title": meta.get("internal_name") or path.stem, "system": self.system_id}
    
    def get_preferred_compression(self) -> str | None: return "rvz"
    def validate_file(self, path: Path) -> bool: return path.suffix.lower() in self.get_supported_extensions()
    
    def get_ideal_filename(self, path: Path, metadata: dict[str, Any]) -> str:
        from ..common.system import default_ideal_filename
        return default_ideal_filename(path, metadata)

    def get_technical_info(self) -> dict[str, str]:
        return {
            "wiki": "https://br.dolphin-emu.org/",
            "bios": "Não.",
            "formats": ".rvz (Dolphin), .wbfs (Consola Real)",
            "notes": "RVZ é recomendado para emulação."
        }

    def needs_conversion(self, path: Path) -> bool:
        return path.suffix.lower() in {".iso", ".wbfs"}