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
        """Extrai metadados de ficheiro PS2 com validação robusta.
        
        Args:
            path: Caminho para o ficheiro PS2
            
        Returns:
            Dicionário com metadados (serial, title, system)
            
        Raises:
            UnsupportedFormatError: Se extensão não suportada
            FileReadError: Se não conseguir ler o ficheiro
            MetadataExtractionError: Se falhar ao extrair metadados
        """
        # Validar entrada
        try:
            path = validate_path_exists(path, "PS2 ROM path", must_be_file=True)
            validate_file_extension(path, self.get_supported_extensions())
        except Exception as e:
            if "extensão" in str(e).lower() or "extension" in str(e).lower():
                raise UnsupportedFormatError(self.system_id, path.suffix) from e
            raise FileReadError(str(path), str(e)) from e
        
        # Validar que é realmente um ficheiro PS2
        if not self.validate_file(path):
            raise CorruptedFileError(
                str(path),
                "File does not contain valid PS2 magic bytes"
            )
        
        # Extrair metadados
        try:
            serial = metadata.get_ps2_serial(path)
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
        """Valida arquivo PS2 por extensão e magic bytes."""
        ext = path.suffix.lower()
        if ext not in self.get_supported_extensions():
            return False
        
        # Validação por magic bytes
        try:
            with open(path, 'rb') as f:
                header = f.read(16)
                
                # ISO: Verificar sector 16 tem "CD001"
                if ext == '.iso' and len(header) >= 5:
                    f.seek(0x8000)  # Sector 16
                    iso_header = f.read(6)
                    if iso_header[1:6] == b'CD001':
                        return True
                
                # CHD: Magic bytes "MComprHD"
                if ext == '.chd' and header[:8] == b'MComprHD':
                    return True
                
                # BIN: Aceitar se tiver tamanho razoável (> 1MB)
                if ext == '.bin' and path.stat().st_size > 1024 * 1024:
                    return True
                    
                # CSO: Magic "CISO"
                if ext == '.cso' and header[:4] == b'CISO':
                    return True
                    
                # Se não conseguiu validar por magic bytes mas extensão é válida
                return ext in {'.iso', '.bin', '.gz'}
                
        except Exception:
            # Se falhar leitura, aceitar baseado em extensão
            return True
        
        return False

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



