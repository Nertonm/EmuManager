from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from . import metadata
from ..common.system import SystemProvider
from ..common.exceptions import (
    ProviderError,
    MetadataExtractionError,
    UnsupportedFormatError,
    FileReadError,
    CorruptedFileError,
)
from ..common.validation import (
    validate_path_exists,
    validate_file_extension,
)

logger = logging.getLogger(__name__)


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
        """Extrai metadados de ficheiro Switch com validação robusta.
        
        Args:
            path: Caminho para o ficheiro Switch
            
        Returns:
            Dicionário com metadados (serial, title, version, category, type)
            
        Raises:
            UnsupportedFormatError: Se extensão não suportada
            FileReadError: Se não conseguir ler o ficheiro
            MetadataExtractionError: Se falhar ao extrair metadados
        """
        # Validar entrada
        try:
            path = validate_path_exists(path, "Switch ROM path", must_be_file=True)
            validate_file_extension(path, self.get_supported_extensions())
        except Exception as e:
            if "extensão" in str(e).lower() or "extension" in str(e).lower():
                raise UnsupportedFormatError(self.system_id, path.suffix) from e
            raise FileReadError(str(path), str(e)) from e
        
        # Validar que é realmente um ficheiro Switch
        if not self.validate_file(path):
            raise CorruptedFileError(
                str(path),
                "File does not contain valid Switch magic bytes"
            )
        
        # Extrair metadados
        try:
            meta = metadata.get_metadata_minimal(path)
            
            title_id = meta.get("title_id", "0000000000000000")
            suffix = title_id[-3:].upper()
            
            is_update = suffix == "800" or meta.get("type") == "Update"
            is_base = suffix == "000" and not is_update
            
            category = "Base Games"
            if is_update:
                category = "Updates"
            elif not is_base:
                category = "DLCs"

            return {
                "serial": title_id,
                "title": meta.get("title") or path.stem,
                "system": self.system_id,
                "version": meta.get("version", "0"),
                "category": category,
                "type": meta.get("type", "Unknown")
            }
        except Exception as e:
            raise MetadataExtractionError(
                self.system_id,
                str(path),
                str(e)
            ) from e

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
        """Valida arquivo Switch por extensão e magic bytes."""
        ext = path.suffix.lower()
        if ext not in self.get_supported_extensions():
            return False
        
        # Validação por magic bytes
        try:
            with open(path, 'rb') as f:
                header = f.read(16)
                
                # NSP/NSZ: Magic "PFS0" (Package FileSystem)
                if ext in {'.nsp', '.nsz'}:
                    if header[:4] == b'PFS0':
                        return True
                    # NSZ pode ter header comprimido
                    if ext == '.nsz':
                        # Aceitar NSZ se tiver tamanho razoável
                        return path.stat().st_size > 1024
                
                # XCI/XCZ: Magic "HEAD" no offset 0x100
                if ext in {'.xci', '.xcz'}:
                    f.seek(0x100)
                    xci_magic = f.read(4)
                    if xci_magic == b'HEAD':
                        return True
                    # XCZ pode ter header comprimido
                    if ext == '.xcz':
                        return path.stat().st_size > 1024
                        
        except Exception:
            # Se falhar leitura, aceitar baseado em extensão
            return True
        
        return False

    def needs_conversion(self, path: Path) -> bool:
        return path.suffix.lower() in {".nsp", ".xci"}
