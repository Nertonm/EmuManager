from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from . import metadata, database
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
        """Extrai metadados de ficheiro PSX com validação robusta.
        
        Args:
            path: Caminho para o ficheiro PSX
            
        Returns:
            Dicionário com metadados (serial, title, system)
            
        Raises:
            UnsupportedFormatError: Se extensão não suportada
            FileReadError: Se não conseguir ler o ficheiro
            MetadataExtractionError: Se falhar ao extrair metadados
        """
        # Validar entrada
        try:
            path = validate_path_exists(path, "PSX ROM path", must_be_file=True)
            validate_file_extension(path, self.get_supported_extensions())
        except Exception as e:
            if "extensão" in str(e).lower() or "extension" in str(e).lower():
                raise UnsupportedFormatError(self.system_id, path.suffix) from e
            raise FileReadError(str(path), str(e)) from e
        
        # Extrair metadados
        try:
            src = path
            if path.suffix.lower() == ".cue":
                bin_p = path.with_suffix(".bin")
                if bin_p.exists():
                    src = bin_p

            serial = metadata.get_psx_serial(src)
            title = database.db.get_title(serial) if serial else None
            
            if not serial:
                logger.warning(f"Could not extract serial from {path.name}")
            
            return {
                "serial": serial or "UNKNOWN",
                "title": title or path.stem,
                "system": self.system_id
            }
        except Exception as e:
            raise MetadataExtractionError(
                self.system_id,
                str(path),
                str(e)
            ) from e

    def get_preferred_compression(self) -> str | None:
        return "chd"

    def validate_file(self, path: Path) -> bool:
        """Valida arquivo PSX por extensão e magic bytes."""
        ext = path.suffix.lower()
        if ext not in self.get_supported_extensions():
            return False
        
        # CUE files sempre válidos se bem formados
        if ext == '.cue':
            return True
            
        # Validação por magic bytes
        try:
            with open(path, 'rb') as f:
                header = f.read(16)
                
                # ISO: Verificar "CD001" no setor 16
                if ext == '.iso':
                    f.seek(0x8000)
                    iso_header = f.read(6)
                    if iso_header[1:6] == b'CD001':
                        return True
                
                # CHD: Magic "MComprHD"
                if ext == '.chd' and header[:8] == b'MComprHD':
                    return True
                
                # BIN: Aceitar se > 1MB (disco PSX mínimo)
                if ext in {'.bin', '.img'} and path.stat().st_size > 1024 * 1024:
                    return True
                
                # PBP: Magic "\x00PBP" (PS1 on PSP)
                if ext == '.pbp' and header[1:4] == b'PBP':
                    return True
                    
        except Exception:
            pass
        
        return True  # Aceitar por extensão se magic bytes falhar

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
