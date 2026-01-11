from __future__ import annotations

from pathlib import Path
from typing import Any
from . import metadata, database
from ..common.system import SystemProvider


class PSXProvider(SystemProvider):
    @property
    def system_id(self) -> str:
        return "psx"

    @property
    def display_name(self) -> str:
        return "PlayStation 1"

    def get_supported_extensions(self) -> set[str]:
        return {".bin", ".cue", ".iso", ".chd", ".img", ".pbp"}

    def extract_metadata(self, path: Path) -> dict[str, Any]:
        src = path
        if path.suffix.lower() == ".cue":
            bin_p = path.with_suffix(".bin")
            if bin_p.exists():
                src = bin_p

        serial = metadata.get_psx_serial(src)
        title = database.db.get_title(serial) if serial else None
        
        return {
            "serial": serial,
            "title": title or path.stem,
            "system": self.system_id
        }

    def get_preferred_compression(self) -> str | None:
        return "chd"

    def validate_file(self, path: Path) -> bool:
        return path.suffix.lower() in self.get_supported_extensions()

    def get_ideal_filename(self, path: Path, metadata: dict[str, Any]) -> str:
        from ..common.system import default_ideal_filename
        return default_ideal_filename(path, metadata)

    def get_technical_info(self) -> dict[str, str]:
        return {
            "wiki": "https://docs.libretro.com/library/beetle_psx_hw/",
            "bios": "Sim (scph5501.bin recomendado).",
            "formats": ".chd (Recomendado), .cue/.bin",
            "notes": "Use CHD para compressão sem perda."
        }

    def needs_conversion(self, path: Path) -> bool:
        return path.suffix.lower() in {".bin", ".iso", ".img"}
