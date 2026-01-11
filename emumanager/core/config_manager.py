from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from emumanager import config

class ConfigManager:
    """Gere a persistência de configurações do utilizador em formato JSON."""

    def __init__(self, config_file: Path | str = "settings.json"):
        self.config_path = Path(config_file)
        self.values: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Carrega as configurações do disco, fundindo com os defaults."""
        # Defaults Industriais
        self.values = {
            "base_dir": config.BASE_DEFAULT,
            "keys_path": str(Path(config.BASE_DEFAULT) / "bios" / "switch" / "prod.keys"),
            "compression_level": 3,
            "auto_scan_on_startup": True,
            "use_multiprocessing": True,
        }
        
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                    self.values.update(stored)
            except Exception:
                pass

    def save(self) -> bool:
        """Grava as configurações atuais no disco."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.values, f, indent=4, ensure_ascii=False)
            return True
        except Exception:
            return False

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.values[key] = value