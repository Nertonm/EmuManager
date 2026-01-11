from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Optional


class Session:
    """Gere o estado atual do EmuManager de forma agnóstica à UI."""

    def __init__(self, base_path: Path | str | None = None):
        self._lock = threading.Lock()
        self._base_path: Optional[Path] = None
        self._selected_system: Optional[str] = None
        self._context: dict[str, Any] = {}
        
        if base_path:
            self.base_path = Path(base_path)

    @property
    def base_path(self) -> Path:
        if self._base_path is None:
            raise ValueError("Base path não configurado na sessão.")
        return self._base_path

    @base_path.setter
    def base_path(self, path: Path):
        resolved = Path(path).expanduser().resolve()
        with self._lock:
            self._base_path = resolved

    @property
    def roms_path(self) -> Path:
        path = self.base_path
        return path if path.name == "roms" else path / "roms"

    @property
    def selected_system(self) -> Optional[str]:
        return self._selected_system

    @selected_system.setter
    def selected_system(self, system: str | None):
        with self._lock:
            self._selected_system = system

    def set_context(self, key: str, value: Any):
        with self._lock:
            self._context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        return self._context.get(key, default)