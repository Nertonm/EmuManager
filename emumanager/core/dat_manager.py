from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

from emumanager.logging_cfg import get_logger
from emumanager.verification.dat_downloader import DatDownloader, SOURCES


class DATManager:
    """Gere o ciclo de vida dos ficheiros DAT (download, organização e consulta)."""

    def __init__(self, dats_root: Path):
        self.dats_root = dats_root
        self.downloader = DatDownloader(dats_root)
        self.logger = get_logger("core.dat_manager")

    def update_all_sources(self, progress_cb: Optional[Callable[[float, str], None]] = None):
        """Atualiza todas as fontes de DATs suportadas (No-Intro e Redump)."""
        self.logger.info("A iniciar atualização global de DATs...")
        
        total_files = 0
        current_file = 0
        
        # 1. Obter lista total de ficheiros para progresso preciso
        all_tasks = {}
        for source in SOURCES:
            files = self.downloader.list_available_dats(source)
            all_tasks[source] = files
            total_files += len(files)

        if total_files == 0:
            self.logger.warning("Nenhum DAT disponível para download.")
            return 0

        # 2. Executar downloads
        success_count = 0
        for source, files in all_tasks.items():
            self.logger.info(f"Fonte: {source} ({len(files)} ficheiros)")
            
            def internal_progress(filename, current, total):
                nonlocal current_file
                current_file += 1
                if progress_cb:
                    percent = current_file / total_files
                    progress_cb(percent, f"Baixando DAT [{source}]: {filename}")

            count = self.downloader.download_all(
                source, 
                max_workers=8, 
                progress_callback=internal_progress
            )
            success_count += count

        self.logger.info(f"Atualização concluída. {success_count} ficheiros DAT sincronizados.")
        return success_count

    def find_dat_for_system(self, system_id: str) -> Optional[Path]:
        """Tenta encontrar o ficheiro DAT mais adequado para um sistema."""
        from emumanager.verification.dat_manager import find_dat_for_system
        return find_dat_for_system(self.dats_root, system_id)
