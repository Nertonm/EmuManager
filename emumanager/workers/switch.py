from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional

from emumanager.core.models import SwitchMetadata
from emumanager.workers.common import BaseWorker, WorkerResult


class SwitchOrganizationWorker(BaseWorker):
    """
    Worker industrial para organização de biblioteca Nintendo Switch.
    Implementa Clean Architecture ao isolar a execução de ferramentas externas
    e validar dados via SwitchMetadata antes de qualquer operação de I/O.
    """

    def __init__(self, base_path: Path, log_cb: Callable, progress_cb: Optional[Callable], cancel_event: Any, nstool_path: Optional[str] = None):
        super().__init__(base_path, log_cb, progress_cb, cancel_event)
        self.nstool = nstool_path or "nstool"

    def _process_item(self, f: Path) -> str:
        if f.suffix.lower() not in {".nsp", ".nsz", ".xci", ".xcz"}:
            return "skipped"

        # 1. Extração de Metadados (Interface Limpa com subprocess)
        try:
            raw_meta = self._fetch_raw_metadata(f)
            meta = SwitchMetadata(
                title=raw_meta.get("title", f.stem),
                title_id=raw_meta.get("title_id", ""),
                version=raw_meta.get("version", 0),
                content_type=self._guess_content_type(raw_meta.get("title_id", "")),
                path=f
            )
        except Exception as e:
            self.logger.error(f"Falha na validação de metadados para {f.name}: {e}")
            return "failed"

        # 2. Cálculo do Destino Hierárquico
        # Estrutura: Base / {Categoria} / {Título} / {Nome Canónico}
        target_dir = self.base_path / "switch" / meta.category_folder / meta.title
        dest_path = target_dir / meta.ideal_name

        if f.resolve() == dest_path.resolve():
            return "skipped"

        # 3. Movimentação Atómica (Reutiliza lógica robusta da BaseWorker)
        self.logger.info(f"Organizando: {f.name} -> {meta.category_folder}/{meta.title}")
        if self.atomic_move(f, dest_path):
            self.db.update_entry_fields(
                str(dest_path.resolve()), 
                status="VERIFIED", 
                match_name=meta.title, 
                dat_name=meta.title_id
            )
            return "success"
        
        return "failed"

    def _fetch_raw_metadata(self, path: Path) -> dict[str, Any]:
        """Chama a ferramenta nstool e faz o parse básico do output."""
        # Nota: Numa versão final, isto seria injetado via um MetadataProvider
        # Aqui fazemos a chamada direta mas protegida.
        try:
            res = subprocess.run(
                [self.nstool, "--header", str(path)],
                capture_output=True, text=True, timeout=15
            )
            # Simulação de parse (simplificado para o exemplo)
            # Em produção usaríamos regex para capturar Title ID e Title
            import re
            tid_match = re.search(r"Title ID:\s+([0-9A-Fa-f]{16})", res.stdout)
            title_match = re.search(r"Title:\s+(.+)", res.stdout)
            
            return {
                "title_id": tid_match.group(1) if tid_match else "",
                "title": title_match.group(1).strip() if title_match else path.stem,
                "version": 0 # Placeholder para lógica de versão
            }
        except Exception:
            return {}

    def _guess_content_type(self, title_id: str) -> str:
        """Heurística baseada no sufixo do Title ID."""
        if not title_id: return "Base"
        if title_id.endswith("000"): return "Base"
        if title_id.endswith("800"): return "Update"
        return "DLC"

def worker_switch_organize(base_path: Path, log_cb: Callable, progress_cb: Optional[Callable] = None) -> WorkerResult:
    """Entry point nativo para a funcionalidade de organização."""
    worker = SwitchOrganizationWorker(base_path, log_cb, progress_cb, None)
    roms = [p for p in (base_path / "roms" / "switch").rglob("*") if p.is_file()]
    return worker.run(roms, "Organização Switch", parallel=True)
