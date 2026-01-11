from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from datetime import datetime


@dataclass(slots=True)
class SwitchMetadata:
    """Modelo de dados validado para jogos de Nintendo Switch."""
    title: str
    title_id: str
    version: int
    content_type: Literal["Base", "Update", "DLC"]
    path: Path

    def __post_init__(self):
        # Validação Rigorosa de Title ID (16 caracteres hexadecimais)
        if not re.fullmatch(r"[0-9A-Fa-f]{16}", self.title_id):
            raise ValueError(f"Title ID inválido: {self.title_id}")
        
        # Validação de Versão
        if self.version < 0:
            raise ValueError("A versão não pode ser negativa.")

    @property
    def category_folder(self) -> str:
        """Define a subpasta baseada no tipo de conteúdo."""
        mapping = {
            "Base": "Base Games",
            "Update": "Updates",
            "DLC": "DLCs"
        }
        return mapping.get(self.content_type, "Unknown")

    @property
    def ideal_name(self) -> str:
        """Gera o nome de ficheiro canónico."""
        return f"{self.title} [{self.title_id}] [v{self.version}]{self.path.suffix}"


@dataclass(slots=True)
class IntegrityEvent:
    """Representa um incidente de integridade detetado no acervo."""
    path: Path
    system: str
    issue_type: Literal["Corruption", "Virus", "Missing", "Mismatch"]
    severity: Literal["Low", "Medium", "High", "Critical"]
    details: str
    timestamp: datetime = field(default_factory=datetime.now)