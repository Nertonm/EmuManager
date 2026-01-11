from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass

@dataclass(slots=True)
class BiosStatus:
    system: str
    filename: str
    description: str
    exists: bool

class BiosChecker:
    """Verifica fisicamente a presença de ficheiros de sistema cruciais."""

    REQUIREMENTS = [
        ("Switch", "prod.keys", "Chaves de desencriptação", "switch"),
        ("Switch", "title.keys", "Chaves de títulos", "switch"),
        ("PS1", "scph5501.bin", "BIOS Recomendada PS1", "ps1"),
        ("PS2", "scph10000.bin", "BIOS Base PS2", "ps2"),
        ("PS2", "rom1.bin", "ROM de sistema PS2", "ps2"),
        ("Dreamcast", "dc_boot.bin", "Bootloader DC", "dc"),
        ("Saturn", "sega_101.bin", "BIOS Japonesa Saturn", "saturn"),
        ("Neo-Geo", "neogeo.zip", "ROM de sistema Arcade", "neogeo"),
    ]

    def __init__(self, bios_root: Path):
        self.bios_root = bios_root

    def check_all(self) -> list[BiosStatus]:
        results = []
        for system, fname, desc, subfolder in self.REQUIREMENTS:
            path = self.bios_root / subfolder / fname
            # Fallback para busca direta se não estiver na subpasta
            if not path.exists():
                path = self.bios_root / fname
                
            results.append(BiosStatus(
                system=system,
                filename=fname,
                description=desc,
                exists=path.exists()
            ))
        return results
