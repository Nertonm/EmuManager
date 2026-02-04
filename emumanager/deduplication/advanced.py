"""Advanced Deduplication - Fuzzy matching, cross-region, version analysis.

Este módulo implementa detecção avançada de duplicados que vai além de simples
comparação de hash, incluindo fuzzy matching de nomes, detecção cross-region e
análise de versões.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from emumanager.library import LibraryDB, LibraryEntry, DuplicateGroup, normalize_game_name


@dataclass
class AdvancedDuplicateGroup(DuplicateGroup):
    """Grupo de duplicados com informações avançadas."""
    
    similarity_score: float = 0.0  # 0.0-1.0
    duplicate_type: str = "unknown"  # 'exact', 'cross_region', 'version', 'fuzzy'
    recommended_keep: Optional[str] = None  # Path do arquivo recomendado para manter
    space_savings: int = 0  # Bytes que podem ser economizados
    
    def get_recommendation_reason(self) -> str:
        """Retorna razão da recomendação."""
        if not self.recommended_keep:
            return "No recommendation"
        
        reasons = []
        for entry in self.entries:
            if entry.path == self.recommended_keep:
                # Análise da melhor versão
                if entry.status == "VERIFIED":
                    reasons.append("Verified by DAT")
                if "(USA)" in entry.path or "(World)" in entry.path:
                    reasons.append("Preferred region")
                if "Rev" in entry.path or "v1." in entry.path:
                    latest_ver = self._extract_version(entry.path)
                    reasons.append(f"Latest version ({latest_ver})")
                if entry.size == max(e.size for e in self.entries):
                    reasons.append("Largest file")
                break
        
        return " | ".join(reasons) if reasons else "Manual review needed"
    
    @staticmethod
    def _extract_version(path: str) -> str:
        """Extrai versão do nome do arquivo."""
        # Procura por padrões: v1.2, Rev 1, (v1.0)
        patterns = [
            r'v(\d+\.?\d*)',
            r'Rev\s*(\d+)',
            r'\(v(\d+\.?\d*)\)',
        ]
        for pattern in patterns:
            match = re.search(pattern, path, re.IGNORECASE)
            if match:
                return match.group(1)
        return "unknown"


class AdvancedDeduplication:
    """Sistema avançado de detecção de duplicados."""
    
    def __init__(self, db: LibraryDB):
        self.db = db
        
        # Configurações de threshold
        self.fuzzy_threshold = 0.85  # 85% similaridade
        self.size_variance_threshold = 0.05  # 5% diferença de tamanho
        
        # Region tags comuns
        self.region_tags = {
            'USA', 'Europe', 'Japan', 'World', 'Asia', 'Korea',
            'Australia', 'Brazil', 'China', 'France', 'Germany',
            'Italy', 'Spain', 'UK', 'U', 'E', 'J', 'W', 'A'
        }
        
        # Region priority (maior = melhor)
        self.region_priority = {
            'World': 10, 'USA': 9, 'Europe': 8, 'Japan': 7,
            'U': 9, 'E': 8, 'J': 7, 'W': 10,
            'Asia': 6, 'Australia': 5, 'Brazil': 4
        }
    
    def find_all_duplicates(self) -> list[AdvancedDuplicateGroup]:
        """Encontra todos os tipos de duplicados."""
        results = []
        
        # 1. Duplicados exatos (hash)
        results.extend(self._find_exact_duplicates())
        
        # 2. Cross-region duplicates
        results.extend(self._find_cross_region_duplicates())
        
        # 3. Version duplicates
        results.extend(self._find_version_duplicates())
        
        # 4. Fuzzy name duplicates
        results.extend(self._find_fuzzy_duplicates())
        
        return results
    
    def _find_exact_duplicates(self) -> list[AdvancedDuplicateGroup]:
        """Encontra duplicados por hash (já implementado na LibraryDB)."""
        basic_groups = self.db.find_duplicates_by_hash(prefer=("sha1", "sha256", "md5"))
        
        results = []
        for group in basic_groups:
            # Converter para AdvancedDuplicateGroup
            adv_group = AdvancedDuplicateGroup(
                key=group.key,
                kind=group.kind,
                entries=group.entries,
                similarity_score=1.0,
                duplicate_type='exact',
                space_savings=group.wasted_bytes
            )
            
            # Recomendar qual manter
            adv_group.recommended_keep = self._select_best_version(adv_group.entries)
            results.append(adv_group)
        
        return results
    
    def _find_cross_region_duplicates(self) -> list[AdvancedDuplicateGroup]:
        """Encontra mesmo jogo em diferentes regiões."""
        entries = self.db.get_all_entries()
        
        # Agrupar por nome base (sem region tags)
        by_base_name = {}
        for entry in entries:
            base_name = self._remove_region_tags(entry.match_name or Path(entry.path).name)
            base_name = normalize_game_name(base_name)
            
            if base_name:
                by_base_name.setdefault(base_name, []).append(entry)
        
        results = []
        for base_name, group_entries in by_base_name.items():
            if len(group_entries) <= 1:
                continue
            
            # Verificar se são realmente cross-region (tamanho similar)
            if not self._are_similar_sizes(group_entries):
                continue
            
            # Verificar se têm diferentes region tags
            regions = set()
            for entry in group_entries:
                region = self._extract_region(entry.path)
                if region:
                    regions.add(region)
            
            if len(regions) > 1:  # Múltiplas regiões
                adv_group = AdvancedDuplicateGroup(
                    key=base_name,
                    kind="cross_region",
                    entries=group_entries,
                    similarity_score=0.95,
                    duplicate_type='cross_region',
                    space_savings=sum(e.size for e in group_entries[1:])
                )
                adv_group.recommended_keep = self._select_best_version(group_entries)
                results.append(adv_group)
        
        return results
    
    def _find_version_duplicates(self) -> list[AdvancedDuplicateGroup]:
        """Encontra diferentes versões do mesmo jogo."""
        entries = self.db.get_all_entries()
        
        # Agrupar por nome base (sem versão)
        by_base_name = {}
        for entry in entries:
            base_name = self._remove_version_tags(entry.match_name or Path(entry.path).name)
            base_name = normalize_game_name(base_name)
            
            if base_name:
                by_base_name.setdefault(base_name, []).append(entry)
        
        results = []
        for base_name, group_entries in by_base_name.items():
            if len(group_entries) <= 1:
                continue
            
            # Verificar se têm diferentes versões
            versions = set()
            for entry in group_entries:
                version = self._extract_version_info(entry.path)
                if version:
                    versions.add(version)
            
            if len(versions) > 1:  # Múltiplas versões
                adv_group = AdvancedDuplicateGroup(
                    key=base_name,
                    kind="version",
                    entries=group_entries,
                    similarity_score=0.90,
                    duplicate_type='version',
                    space_savings=sum(e.size for e in group_entries[1:])
                )
                adv_group.recommended_keep = self._select_best_version(group_entries)
                results.append(adv_group)
        
        return results
    
    def _find_fuzzy_duplicates(self) -> list[AdvancedDuplicateGroup]:
        """Encontra duplicados por fuzzy matching de nome."""
        entries = self.db.get_all_entries()
        
        # Normalizar todos os nomes
        normalized = []
        for entry in entries:
            name = normalize_game_name(entry.match_name or Path(entry.path).name)
            if name:
                normalized.append((name, entry))
        
        # Comparar todos com todos (otimizado)
        results = []
        processed = set()
        
        for i, (name1, entry1) in enumerate(normalized):
            if entry1.path in processed:
                continue
            
            matches = [entry1]
            
            for name2, entry2 in normalized[i+1:]:
                if entry2.path in processed:
                    continue
                
                # Fuzzy matching
                similarity = self._calculate_similarity(name1, name2)
                
                if similarity >= self.fuzzy_threshold:
                    # Verificar tamanho similar
                    if self._are_similar_sizes([entry1, entry2]):
                        matches.append(entry2)
                        processed.add(entry2.path)
            
            if len(matches) > 1:
                processed.add(entry1.path)
                
                adv_group = AdvancedDuplicateGroup(
                    key=name1,
                    kind="fuzzy",
                    entries=matches,
                    similarity_score=self.fuzzy_threshold,
                    duplicate_type='fuzzy',
                    space_savings=sum(e.size for e in matches[1:])
                )
                adv_group.recommended_keep = self._select_best_version(matches)
                results.append(adv_group)
        
        return results
    
    def _select_best_version(self, entries: list[LibraryEntry]) -> str:
        """Seleciona a melhor versão para manter."""
        if not entries:
            return ""
        
        # Scoring system
        scores = []
        for entry in entries:
            score = 0
            
            # 1. Status verificado vale mais
            if entry.status == "VERIFIED":
                score += 100
            
            # 2. Região preferida
            region = self._extract_region(entry.path)
            score += self.region_priority.get(region, 0) * 10
            
            # 3. Versão mais recente
            version = self._extract_version_info(entry.path)
            if version:
                # Extrair número da versão
                try:
                    ver_num = float(re.search(r'(\d+\.?\d*)', version).group(1))
                    score += ver_num * 5
                except (AttributeError, ValueError):
                    pass
            
            # 4. Tamanho (maior geralmente = mais completo)
            score += entry.size / (1024 * 1024 * 100)  # Normalize por 100MB
            
            scores.append((score, entry.path))
        
        # Retornar o com maior score
        scores.sort(reverse=True)
        return scores[0][1]
    
    def _remove_region_tags(self, name: str) -> str:
        """Remove tags de região do nome."""
        # Remove (USA), (Europe), etc
        name = re.sub(r'\([^)]*(?:' + '|'.join(self.region_tags) + r')[^)]*\)', '', name, flags=re.IGNORECASE)
        # Remove [USA], [Europe], etc
        name = re.sub(r'\[[^\]]*(?:' + '|'.join(self.region_tags) + r')[^\]]*\]', '', name, flags=re.IGNORECASE)
        return name.strip()
    
    def _remove_version_tags(self, name: str) -> str:
        """Remove tags de versão do nome."""
        # Remove (v1.0), Rev 1, etc
        patterns = [
            r'\(v\d+\.?\d*\)',
            r'Rev\s*\d+',
            r'\[v\d+\.?\d*\]',
            r'v\d+\.?\d*',
        ]
        for pattern in patterns:
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)
        return name.strip()
    
    def _extract_region(self, path: str) -> Optional[str]:
        """Extrai região do path."""
        # Procura por tags de região completas em parênteses ou colchetes
        import re
        match = re.search(r'[\(\[]([^\)\]]*(?:' + '|'.join(self.region_tags) + r')[^\)\]]*)[\ )\]]', path, re.IGNORECASE)
        if match:
            # Extrair a tag de região exata do grupo encontrado
            group = match.group(1)
            for region in sorted(self.region_tags, key=len, reverse=True):  # Mais longas primeiro
                if region in group:
                    return region
        return None
    
    def _extract_version_info(self, path: str) -> Optional[str]:
        """Extrai informação de versão do path."""
        patterns = [
            r'(v\d+\.?\d*)',
            r'(Rev\s*\d+)',
            r'\((v\d+\.?\d*)\)',
        ]
        for pattern in patterns:
            match = re.search(pattern, path, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _are_similar_sizes(self, entries: list[LibraryEntry]) -> bool:
        """Verifica se os tamanhos são similares (dentro de 10%)."""
        if len(entries) < 2:
            return True
        
        sizes = [e.size for e in entries]
        max_size = max(sizes)
        min_size = min(sizes)
        
        # Calcular diferença percentual entre maior e menor
        if max_size == 0:
            return True
        
        variance = (max_size - min_size) / max_size
        return variance <= 0.10  # 10% threshold
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calcula similaridade entre duas strings."""
        return SequenceMatcher(None, str1, str2).ratio()
    
    def get_statistics(self) -> dict:
        """Retorna estatísticas de duplicados."""
        all_duplicates = self.find_all_duplicates()
        
        total_duplicates = len(all_duplicates)
        total_wasted_space = sum(g.space_savings for g in all_duplicates)
        
        by_type = {}
        for group in all_duplicates:
            by_type.setdefault(group.duplicate_type, []).append(group)
        
        return {
            'total_groups': total_duplicates,
            'total_wasted_bytes': total_wasted_space,
            'total_wasted_gb': total_wasted_space / (1024**3),
            'by_type': {
                dtype: {
                    'count': len(groups),
                    'wasted_bytes': sum(g.space_savings for g in groups)
                }
                for dtype, groups in by_type.items()
            }
        }
