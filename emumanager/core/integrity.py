from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional, Any
from datetime import datetime

from emumanager.core.models import IntegrityEvent
from emumanager.library import LibraryDB
from emumanager.logging_cfg import get_logger


class IntegrityManager:
    """
    Gere a sanidade do acervo, isolamento de ameaças e auditoria de erros.
    Funciona como um Service Layer desacoplado.
    """

    def __init__(self, base_path: Path, db: LibraryDB):
        self.base_path = base_path
        self.db = db
        self.quarantine_dir = base_path / "_QUARANTINE"
        self.logger = get_logger("core.integrity")
        self._subscribers: list[Callable[[IntegrityEvent], None]] = []

    def subscribe(self, callback: Callable[[IntegrityEvent], None]):
        """Permite que a UI subscreva eventos de integridade."""
        self._subscribers.append(callback)

    def _emit(self, event: IntegrityEvent):
        self.logger.warning(f"Integridade: {event.issue_type} em {event.path.name} ({event.severity})")
        for sub in self._subscribers:
            try:
                sub(event)
            except Exception:
                pass

    def quarantine_file(self, path: Path, system: str, issue: str, details: str):
        """Isola fisicamente um ficheiro suspeito ou corrompido."""
        if not path.exists():
            return None

        # Obter entrada original para preservar metadados
        old_path_str = str(path.resolve())
        entry = self.db.get_entry(old_path_str)

        dest_dir = self.quarantine_dir / system
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / path.name

        try:
            # Movimentação física
            path.replace(dest_path)
            
            # Sincronização de Base de Dados
            if entry:
                self.db.remove_entry(old_path_str)
                entry.path = str(dest_path.resolve())
                entry.status = "QUARANTINED"
                entry.match_name = f"Issue: {issue}"
                self.db.update_entry(entry)
            
            self.db.log_action(str(dest_path), "QUARANTINE", f"{issue}: {details}")

            # Emissão do evento
            self._emit(IntegrityEvent(
                path=dest_path,
                system=system,
                issue_type="Corruption" if "corrupt" in issue.lower() else "Virus",
                severity="High",
                details=details
            ))
            return dest_path
        except Exception as e:
            self.logger.error(f"Falha ao isolar ficheiro {path.name}: {e}")
            return None

    def restore_file(self, quarantined_path: Path, target_dir: Path) -> bool:
        """Restaura um ficheiro da quarentena para o acervo ativo."""
        if not quarantined_path.exists():
            return False

        old_path_str = str(quarantined_path.resolve())
        entry = self.db.get_entry(old_path_str)
        
        dest_path = target_dir / quarantined_path.name
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            quarantined_path.replace(dest_path)
            
            if entry:
                self.db.remove_entry(old_path_str)
                entry.path = str(dest_path.resolve())
                entry.status = "UNKNOWN"
                self.db.update_entry(entry)
                
            self.db.log_action(str(dest_path), "RESTORE", "Ficheiro restaurado manualmente pelo utilizador.")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao restaurar ficheiro: {e}")
            return False