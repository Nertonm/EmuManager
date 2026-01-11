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
        is_jb = path.is_dir() and ((path / "PARAM.SFO").exists() or (path / "PS3_GAME" / "PARAM.SFO").exists())
        return path.suffix.lower() in self.get_supported_extensions() or is_jb

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
