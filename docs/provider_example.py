"""Exemplo de integração do sistema de exceções e validação com PS2 Provider.

Este arquivo demonstra como integrar as melhorias estruturais com os providers existentes.
Use como referência para migrar outros providers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Imports das melhorias estruturais
from emumanager.common.exceptions import (
    ProviderError,
    MetadataExtractionError,
    UnsupportedFormatError,
    FileReadError,
    CorruptedFileError,
)
from emumanager.common.validation import (
    validate_path_exists,
    validate_file_extension,
    validate_not_empty,
)


class PS2ProviderEnhanced:
    """Versão melhorada do PS2Provider com validação e exceções robustas.
    
    Esta é uma demonstração de como integrar as melhorias.
    NÃO substitui o provider real ainda - serve como exemplo.
    """
    
    def __init__(self):
        self._system_id = "ps2"
        self._display_name = "PlayStation 2"
        self._supported_extensions = {".iso", ".chd", ".cso"}
    
    @property
    def system_id(self) -> str:
        return self._system_id
    
    @property
    def display_name(self) -> str:
        return self._display_name
    
    def get_supported_extensions(self) -> set[str]:
        """Retorna extensões suportadas."""
        return self._supported_extensions.copy()
    
    def extract_metadata(self, path: Path) -> dict[str, Any]:
        """Extrai metadados de um ficheiro PS2 com validação robusta.
        
        Args:
            path: Caminho para o ficheiro PS2
            
        Returns:
            Dicionário com metadados (serial, title, etc.)
            
        Raises:
            UnsupportedFormatError: Se extensão não suportada
            FileReadError: Se não conseguir ler o ficheiro
            CorruptedFileError: Se ficheiro estiver corrompido
            MetadataExtractionError: Se falhar ao extrair metadados
        """
        # 1. Validar entrada
        try:
            path = validate_path_exists(path, "PS2 ROM path", must_be_file=True)
            validate_file_extension(path, self._supported_extensions)
        except Exception as e:
            # Converter exceções de validação para exceções do provider
            if "extensão" in str(e).lower():
                raise UnsupportedFormatError(
                    self._system_id,
                    path.suffix
                ) from e
            raise FileReadError(str(path), str(e)) from e
        
        # 2. Validar que é realmente um ficheiro PS2
        if not self.validate_file(path):
            raise CorruptedFileError(
                str(path),
                "File does not contain valid PS2 magic bytes"
            )
        
        # 3. Extrair metadados
        try:
            metadata = self._extract_metadata_internal(path)
            
            # 4. Validar metadados extraídos
            if not metadata.get("serial"):
                raise MetadataExtractionError(
                    self._system_id,
                    str(path),
                    "Could not extract game serial"
                )
            
            # 5. Validar formato do serial
            try:
                from emumanager.common.validation import validate_serial_format
                metadata["serial"] = validate_serial_format(metadata["serial"])
            except Exception as e:
                # Serial inválido, mas não falhar - apenas logar
                import logging
                logging.warning(f"Invalid serial format: {metadata['serial']}")
            
            return metadata
            
        except MetadataExtractionError:
            # Re-lançar exceções do provider sem modificar
            raise
        except Exception as e:
            # Outras exceções são envoltas em MetadataExtractionError
            raise MetadataExtractionError(
                self._system_id,
                str(path),
                str(e)
            ) from e
    
    def validate_file(self, path: Path) -> bool:
        """Valida se ficheiro é um PS2 válido.
        
        Args:
            path: Caminho para validar
            
        Returns:
            True se válido, False caso contrário
            
        Note:
            Esta função NÃO lança exceções - retorna bool.
            Use extract_metadata() se precisar de exceções detalhadas.
        """
        try:
            path = validate_path_exists(path, must_be_file=True)
        except Exception:
            return False
        
        # Validar extensão
        if path.suffix.lower() not in self._supported_extensions:
            return False
        
        # Validar magic bytes
        try:
            return self._validate_magic_bytes(path)
        except Exception:
            return False
    
    def _validate_magic_bytes(self, path: Path) -> bool:
        """Valida magic bytes internamente."""
        try:
            with open(path, 'rb') as f:
                # ISO: Verificar CD001 em offset 0x8000
                if path.suffix.lower() == '.iso':
                    f.seek(0x8000)
                    magic = f.read(5)
                    if magic == b'CD001':
                        return True
                
                # CHD: Verificar MComprHD
                elif path.suffix.lower() == '.chd':
                    magic = f.read(8)
                    if magic == b'MComprHD':
                        return True
                
                # CSO: Verificar CISO
                elif path.suffix.lower() == '.cso':
                    magic = f.read(4)
                    if magic == b'CISO':
                        return True
            
            return False
            
        except Exception:
            return False
    
    def _extract_metadata_internal(self, path: Path) -> dict[str, Any]:
        """Implementação interna de extração (placeholder).
        
        Na implementação real, isto chamaria as funções de metadata.py
        """
        # Placeholder - na implementação real, usar funções reais
        return {
            "serial": "SLUS-12345",
            "title": "Example Game",
            "region": "USA",
            "size": path.stat().st_size,
        }
    
    def get_preferred_compression(self) -> str | None:
        """Retorna formato de compressão preferido."""
        return "chd"
    
    def get_ideal_filename(self, path: Path, metadata: dict[str, Any]) -> str:
        """Sugere nome ideal baseado em metadados.
        
        Args:
            path: Caminho original
            metadata: Metadados extraídos
            
        Returns:
            Nome de ficheiro sugerido
        """
        try:
            validate_not_empty(metadata.get("title", ""), "title")
            validate_not_empty(metadata.get("serial", ""), "serial")
            
            title = metadata["title"]
            serial = metadata["serial"]
            ext = path.suffix
            
            # Formato: "Game Title [SLUS-12345].iso"
            return f"{title} [{serial}]{ext}"
            
        except Exception:
            # Se falhar, manter nome original
            return path.name
    
    def get_technical_info(self) -> dict[str, str]:
        """Retorna informações técnicas do sistema."""
        return {
            "System": "PlayStation 2",
            "Manufacturer": "Sony",
            "Year": "2000",
            "CPU": "Emotion Engine @ 294 MHz",
            "RAM": "32 MB",
            "BIOS": "Required (SCPH-xxxxx)",
            "Formats": "ISO, CHD, CSO",
            "Emulator": "PCSX2",
            "Wiki": "https://pcsx2.net/",
        }
    
    def needs_conversion(self, path: Path) -> bool:
        """Verifica se ficheiro deve ser convertido.
        
        Args:
            path: Caminho do ficheiro
            
        Returns:
            True se deve ser convertido para CHD
        """
        try:
            validate_path_exists(path, must_be_file=True)
            
            # ISO e CSO devem ser convertidos para CHD
            ext = path.suffix.lower()
            return ext in {".iso", ".cso"}
            
        except Exception:
            return False


# ============================================================================
# EXEMPLO DE USO
# ============================================================================

def example_usage():
    """Demonstra o uso do provider melhorado."""
    provider = PS2ProviderEnhanced()
    
    # Exemplo 1: Extrair metadados com tratamento robusto
    try:
        rom_path = Path("/path/to/game.iso")
        metadata = provider.extract_metadata(rom_path)
        
        print(f"✅ Metadados extraídos:")
        print(f"   Serial: {metadata['serial']}")
        print(f"   Title: {metadata['title']}")
        
        # Sugerir nome ideal
        ideal_name = provider.get_ideal_filename(rom_path, metadata)
        print(f"   Nome sugerido: {ideal_name}")
        
    except UnsupportedFormatError as e:
        print(f"❌ Formato não suportado: {e}")
        print(f"   Extensões válidas: {', '.join(provider.get_supported_extensions())}")
        
    except CorruptedFileError as e:
        print(f"❌ Ficheiro corrompido: {e}")
        print(f"   Motivo: {e.details.get('reason', 'unknown')}")
        
    except MetadataExtractionError as e:
        print(f"❌ Falha ao extrair metadados: {e}")
        print(f"   Sistema: {e.system}")
        print(f"   Ficheiro: {e.details.get('path')}")
        
    except FileReadError as e:
        print(f"❌ Erro ao ler ficheiro: {e}")
    
    # Exemplo 2: Validação simples (sem exceções)
    if provider.validate_file(rom_path):
        print("✅ Ficheiro PS2 válido")
    else:
        print("❌ Ficheiro PS2 inválido")
    
    # Exemplo 3: Verificar se precisa conversão
    if provider.needs_conversion(rom_path):
        preferred = provider.get_preferred_compression()
        print(f"⚠️  Recomenda-se converter para {preferred.upper()}")


if __name__ == "__main__":
    example_usage()
