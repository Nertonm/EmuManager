from __future__ import annotations

from pathlib import Path
from .system import SystemProvider
from ..ps2.provider import PS2Provider
from ..psx.provider import PSXProvider
from ..switch.provider import SwitchProvider
from ..gamecube.provider import GameCubeProvider
from ..wii.provider import WiiProvider
from ..n3ds.provider import N3DSProvider
from ..psp.provider import PSPProvider
from ..ps3.provider import PS3Provider


class SystemRegistry:
    """Registo central de todos os sistemas suportados."""

    def __init__(self):
        self._providers: dict[str, SystemProvider] = {}
        self._register_defaults()

    def _register_defaults(self):
        providers = [
            PS2Provider(), PSXProvider(), SwitchProvider(),
            GameCubeProvider(), WiiProvider(), N3DSProvider(),
            PSPProvider(), PS3Provider()
        ]
        for p in providers:
            self.register(p)

    def register(self, provider: SystemProvider):
        self._providers[provider.system_id] = provider

    def get_provider(self, system_id: str) -> SystemProvider | None:
        return self._providers.get(system_id)

    def find_provider_for_file(self, path: Path) -> SystemProvider | None:
        """Descobre o provider correto, lidando com colisões via validação de conteúdo."""
        ext = path.suffix.lower()
        candidates = [p for p in self._providers.values() if ext in p.get_supported_extensions()]
        
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
            
        # Resolução de conflitos (.iso pode ser PS2, GC, Wii, etc.)
        for p in candidates:
            try:
                if p.validate_file(path):
                    return p
            except Exception:
                continue
                
        return candidates[0] # Fallback para o primeiro se falhar validação profunda

    def list_systems(self) -> list[str]:
        return sorted(list(self._providers.keys()))

# Singleton
registry = SystemRegistry()