from __future__ import annotations

import requests
import hashlib
from pathlib import Path
from typing import Optional, Any

class RetroAchievementsProvider:
    """Cliente para consulta de compatibilidade com RetroAchievements API."""

    API_BASE = "https://retroachievements.org/API/"

    def __init__(self, username: Optional[str] = None, api_key: Optional[str] = None):
        self.username = username
        self.api_key = api_key
        self.session = requests.Session()

    def is_configured(self) -> bool:
        return bool(self.username and self.api_key)

    def get_game_hashes(self, game_id: int) -> list[str]:
        """Obtém a lista de hashes (MD5) suportados para um Game ID."""
        if not self.is_configured(): return []
        
        url = f"{self.API_BASE}API_GetGameHashes.php"
        params = {"z": self.username, "y": self.api_key, "i": game_id}
        
        try:
            resp = self.session.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                # RA devolve um dict onde os valores são os hashes
                return [h.lower() for h in data.get("Results", {}).values()]
        except Exception:
            pass
        return []

    def check_compatibility(self, local_md5: str, game_id: Optional[int]) -> dict[str, Any]:
        """Verifica se o hash local consta na lista oficial do RA."""
        if not game_id or not local_md5:
            return {"compatible": False, "reason": "Sem ID de jogo ou Hash"}
            
        supported_hashes = self.get_game_hashes(game_id)
        if local_md5.lower() in supported_hashes:
            return {"compatible": True, "icon": "🏆"}
        
        return {
            "compatible": False, 
            "icon": "❌", 
            "reason": "Versão/Região incompatível com RA"
        }
