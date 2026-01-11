from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Any
from emumanager.logging_cfg import get_logger

class MultiDiscManager:
    """Motor de deteção e agrupamento de jogos multi-disco."""

    # Regex para capturar padrões: (Disc 1), [CD2], Part 3, Disk A, etc.
    DISC_PATTERN = re.compile(
        r"(.*?)\s*[\(\[]?(?:Disc|CD|Part|Side|Disk)\s*([0-9A-Z])[\) \]]?.*", 
        re.IGNORECASE
    )

    def __init__(self):
        self.logger = get_logger("core.multidisc")

    def group_discs(self, files: list[Path]) -> dict[str, list[Path]]:
        """Agrupa ficheiros por título base, detetando discos."""
        groups: dict[str, list[Path]] = {}
        
        for f in files:
            # Ignorar ficheiros que já são m3u
            if f.suffix.lower() == ".m3u": continue
            
            match = self.DISC_PATTERN.match(f.stem)
            if match:
                base_title = match.group(1).strip()
                groups.setdefault(base_title, []).append(f)
        
        # Filtrar apenas grupos que tenham realmente mais de um disco
        return {name: sorted(discs) for name, discs in groups.items() if len(discs) > 1}

    def create_m3u(self, base_title: str, discs: list[Path], target_dir: Path, hide_discs: bool = True) -> Path:
        """Gera o ficheiro .m3u e opcionalmente oculta os discos originais."""
        m3u_path = target_dir / f"{base_title}.m3u"
        
        # Definir diretoria de isolamento se solicitado
        subfolder = Path(".discs")
        storage_dir = target_dir / subfolder
        
        lines = []
        for disc_path in discs:
            if hide_discs:
                storage_dir.mkdir(exist_ok=True)
                new_disc_path = storage_dir / disc_path.name
                # Mover físico (atómico se no mesmo FS)
                disc_path.replace(new_disc_path)
                lines.append(f"{subfolder}/{disc_path.name}")
            else:
                lines.append(disc_path.name)

        m3u_path.write_text("\n".join(lines), encoding="utf-8")
        self.logger.info(f"Playlist M3U gerada: {m3u_path.name} ({len(discs)} discos)")
        return m3u_path
