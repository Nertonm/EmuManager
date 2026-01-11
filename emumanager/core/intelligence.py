from __future__ import annotations

import difflib
from typing import Iterable, Optional

class MatchEngine:
    """Motor de Inteligência NLP para correspondência de títulos."""

    @staticmethod
    def calculate_similarity(a: str, b: str) -> int:
        """Calcula o score de similaridade (0-100) entre duas strings."""
        def normalize(s: str) -> str:
            import re
            s = s.lower()
            s = re.sub(r'\(.*?\)', '', s)
            s = re.sub(r'\[.*?\]', '', s)
            return re.sub(r'[^a-z0-9]', '', s)

        norm_a = normalize(a)
        norm_b = normalize(b)
        if not norm_a or not norm_b: return 0
        
        ratio = difflib.SequenceMatcher(None, norm_a, norm_b).ratio()
        return int(ratio * 100)

    def find_best_match(self, target: str, candidates: Iterable[str]) -> tuple[Optional[str], int]:
        """Encontra a melhor correspondência numa lista de candidatos."""
        best_name = None
        best_score = 0
        target_lower = target.lower()
        
        for cand in candidates:
            if cand.lower()[:3] != target_lower[:3] and len(target) > 5:
                continue
            score = self.calculate_similarity(target, cand)
            if score > best_score:
                best_score = score
                best_name = cand
                if best_score == 100: break
                
        return best_name, best_score