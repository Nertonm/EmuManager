from __future__ import annotations

from pathlib import Path
from typing import Any
from . import metadata
from ..common.system import SystemProvider


class SwitchProvider(SystemProvider):
    @property
    def system_id(self) -> str:
        return "switch"

    @property
    def display_name(self) -> str:
        return "Nintendo Switch"

    def get_supported_extensions(self) -> set[str]:
        return {".nsp", ".nsz", ".xci", ".xcz"}

    def extract_metadata(self, path: Path) -> dict[str, Any]:
        meta = metadata.get_metadata_minimal(path)
        
        title_id = meta.get("title_id", "0000000000000000")
        is_update = title_id.endswith("800") or meta.get("type") == "Update"
        is_dlc = int(title_id[-3:], 16) > 0x800 if not is_update else False
        
        category = "Base Games"
        if is_update: category = "Updates"
        elif is_dlc: category = "DLCs"

        return {
            "serial": title_id,
            "title": meta.get("title") or path.stem,
            "system": self.system_id,
            "version": meta.get("version", "0"),
            "category": category,
            "type": meta.get("type", "Unknown")
        }

    def get_ideal_filename(self, path: Path, metadata: dict[str, Any]) -> str:
        title = metadata.get("title", path.stem)
        serial = metadata.get("serial", "")
        ver = metadata.get("version", "0")
        category = metadata.get("category", "Base Games")
        
        filename = f"{title} [{serial}]"
        if ver and ver != "0":
            filename += f" [v{ver}]"
        filename += path.suffix

        return str(Path(category) / title / filename)

    def get_technical_info(self) -> dict[str, str]:
        return {
            "wiki": "https://yuzu-emu.org/help/quickstart/",
            "bios": "CRÍTICO: Requer prod.keys, title.keys e Firmware instalado.",
            "formats": ".nsz (Recomendado), .nsp, .xcz, .xci",
            "notes": "Mantenha os ficheiros NSZ para compressão eficiente."
        }

    def get_preferred_compression(self) -> str | None:
        return "nsz"

    def validate_file(self, path: Path) -> bool:
        return path.suffix.lower() in self.get_supported_extensions()

    def needs_conversion(self, path: Path) -> bool:
        return path.suffix.lower() in {".nsp", ".xci"}
