#!/usr/bin/env python3
"""
Manager Facade

Este módulo atua como a interface pública simplificada do EmuManager,
delegando a lógica pesada para o pacote 'core'.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .config import BASE_DEFAULT, EXT_TO_SYSTEM
from .core.session import Session
from .core.orchestrator import Orchestrator


def get_orchestrator(base_dir: Path | str) -> Orchestrator:
    """Helper para obter um orquestrador configurado."""
    session = Session(base_dir)
    return Orchestrator(session)


def guess_system_for_file(path: Path) -> Optional[str]:
    """Heurística avançada para detetar o sistema de um ficheiro."""
    from .common.registry import registry
    provider = registry.find_provider_for_file(path)
    if provider and provider.system_id != "unknown":
        return provider.system_id
        
    # Fallback para heurística baseada em nome de pasta/ficheiro se o provider falhar
    path_str = str(path).lower()
    for sys_id in registry.list_systems():
        if sys_id in path_str:
            return sys_id
            
    return None


def cmd_init(base_dir: Path, dry_run: bool = False) -> int:
    orch = get_orchestrator(base_dir)
    orch.initialize_library(dry_run=dry_run)
    return 0


def cmd_list_systems(base_dir: Path) -> list[str]:
    roms = base_dir / "roms" if (base_dir / "roms").is_dir() else base_dir
    if not roms.exists():
        return []
    # Usar set() para eliminar duplicados e depois ordenar
    systems = {p.name for p in roms.iterdir() if p.is_dir() and not p.name.startswith(".")}
    return sorted(list(systems))



def cmd_add_rom(src: Path, base_dir: Path, system: Optional[str] = None, move: bool = False) -> Path:
    orch = get_orchestrator(base_dir)
    return orch.add_rom(src, system=system, move=move)


def cmd_update_dats(base_dir: Path, source: str | None = None) -> int:
    orch = get_orchestrator(base_dir)
    return orch.update_dats()


def cmd_generate_report(base_dir: Path, output_file: str = "report.csv") -> bool:
    orch = get_orchestrator(base_dir)
    return orch.generate_compliance_report(Path(output_file))


def cmd_cleanup_duplicates(base_dir: Path, dry_run: bool = False) -> dict[str, int]:
    orch = get_orchestrator(base_dir)
    return orch.cleanup_duplicates(dry_run=dry_run)