"""
Tipos compartilhados e type aliases para o EmuManager.
Centraliza definições de tipos usados em múltiplos módulos.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


# Type Aliases para Callbacks
ProgressCallback = Callable[[float, str], None]  # (percent, message)
LogCallback = Callable[[str], None]  # (message)


@dataclass
class ProcessedItem:
    """Representa um item processado por um worker."""
    path: Path
    status: str  # 'success', 'failed', 'skipped'
    duration_ms: float
    system: Optional[str] = None
    error_message: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkerResult:
    """Resultado padronizado de execução de workers."""
    task_name: str
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    duration_ms: float = 0
    processed_items: list[ProcessedItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    
    def add_item_result(
        self, 
        path: Path, 
        status: str, 
        duration_ms: float,
        system: Optional[str] = None,
        error: Optional[str] = None
    ):
        """Helper para adicionar resultado de item processado."""
        self.processed_items.append(
            ProcessedItem(
                path=path,
                status=status,
                duration_ms=duration_ms,
                system=system,
                error_message=error
            )
        )
    
    @property
    def total_items(self) -> int:
        return self.success_count + self.failed_count + self.skipped_count
    
    @property
    def success_rate(self) -> float:
        if self.total_items == 0:
            return 0.0
        return self.success_count / self.total_items
    
    def __str__(self) -> str:
        return (
            f"{self.task_name}: "
            f"{self.success_count} OK, "
            f"{self.failed_count} ERR, "
            f"{self.skipped_count} SKIP "
            f"({self.duration_ms:.0f}ms)"
        )


@dataclass
class ScanResult:
    """Resultado específico de operação de scan."""
    files_scanned: int = 0
    files_verified: int = 0
    files_new: int = 0
    files_updated: int = 0
    files_corrupt: int = 0
    duration_ms: float = 0
    systems_found: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.files_scanned,
            "verified": self.files_verified,
            "new": self.files_new,
            "updated": self.files_updated,
            "corrupt": self.files_corrupt,
            "duration_ms": self.duration_ms,
            "systems": self.systems_found
        }


@dataclass
class OrganizationResult:
    """Resultado específico de operação de organização."""
    files_moved: int = 0
    files_renamed: int = 0
    files_skipped: int = 0
    files_errors: int = 0
    duration_ms: float = 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "moved": self.files_moved,
            "renamed": self.files_renamed,
            "skipped": self.files_skipped,
            "errors": self.files_errors,
            "duration_ms": self.duration_ms
        }
