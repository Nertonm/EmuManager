from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable, Any


@runtime_checkable
class SystemProvider(Protocol):
    """Contrato obrigatório para qualquer sistema (PS2, Switch, etc.)."""

    @property
    def system_id(self) -> str:
        """ID único (ex: 'ps2', 'switch')."""
        ...

    @property
    def display_name(self) -> str:
        """Nome legível (ex: 'PlayStation 2')."""
        ...

    def get_supported_extensions(self) -> set[str]:
        """Lista de extensões suportadas (ex: {'.iso', '.chd'})."""
        ...

    def extract_metadata(self, path: Path) -> dict[str, Any]:
        """Lê cabeçalhos/metadados específicos do ficheiro.
        Deve retornar pelo menos: {'serial': str, 'title': str}
        """
        ...

    def get_preferred_compression(self) -> str | None:
        """Formato de compressão ideal (ex: 'chd', 'rvz', 'nsz')."""
        ...

    def validate_file(self, path: Path) -> bool:
        """Verificação rápida se o ficheiro pertence realmente a este sistema."""
        ...

    def get_ideal_filename(self, path: Path, metadata: dict[str, Any]) -> str:
        """Sugere o nome de ficheiro ideal baseado nos metadados."""
        ...

    def get_technical_info(self) -> dict[str, str]:
        """Retorna informações técnicas: BIOS, Formatos, Wiki, etc."""
        ...

    def needs_conversion(self, path: Path) -> bool:
        """Verifica se o ficheiro deve ser convertido para o formato ideal."""
        ...




def default_ideal_filename(path: Path, metadata: dict[str, Any]) -> str:
    """Implementação padrão: 'Título [Serial].ext'."""
    title = metadata.get("title")
    serial = metadata.get("serial")
    
    if title and serial:
        return f"{title} [{serial}]{path.suffix}"
    if title:
        return f"{title}{path.suffix}"
    return path.name


