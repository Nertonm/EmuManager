from __future__ import annotations

from pathlib import Path
from typing import Any
from . import metadata, database
from ..common.system import SystemProvider


class PS2Provider(SystemProvider):
    @property
    def system_id(self) -> str:
        return "ps2"

    @property
    def display_name(self) -> str:
        return "PlayStation 2"

    def get_supported_extensions(self) -> set[str]:
        return {".iso", ".bin", ".cso", ".chd", ".gz"}

    def extract_metadata(self, path: Path) -> dict[str, Any]:
        serial = metadata.get_ps2_serial(path)
        title = database.db.get_title(serial) if serial else None
        return {
            "serial": serial,
            "title": title or path.stem,
            "system": self.system_id
        }

    def get_preferred_compression(self) -> str | None:
        return "chd"

    def validate_file(self, path: Path) -> bool:
        # Verificação básica por extensão; no futuro pode checar magic bytes
        return path.suffix.lower() in self.get_supported_extensions()

    def get_ideal_filename(self, path: Path, metadata: dict[str, Any]) -> str:
        from ..common.system import default_ideal_filename
        return default_ideal_filename(path, metadata)

    def get_technical_info(self) -> dict[str, str]:
        return {
            "wiki": "https://pcsx2.net/docs/usage/setup/",
            "bios": "Requer BIOS (scph10000.bin ou mais recente).",
            "formats": ".chd (Recomendado), .iso, .cso",
            "notes": "Converta ISOs para .CHD para economizar até 50% de espaço sem perda de qualidade."
        }

    def needs_conversion(self, path: Path) -> bool:
        return path.suffix.lower() in {".iso", ".bin"}



