"""Analytics Dashboard - Collection statistics and insights.

Este módulo fornece análises detalhadas da coleção incluindo:
- Completion percentage por sistema
- Missing ROMs report
- Storage breakdown por sistema/formato
- Gráficos e visualizações
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from emumanager.library import LibraryDB, LibraryEntry


@dataclass
class SystemStats:
    """Estatísticas de um sistema."""
    system: str
    total_roms: int = 0
    verified_roms: int = 0
    unverified_roms: int = 0
    missing_roms: int = 0
    total_size_bytes: int = 0
    compression_formats: dict[str, int] = field(default_factory=dict)
    
    @property
    def completion_percent(self) -> float:
        """Percentual de completude."""
        total = self.total_roms + self.missing_roms
        if total == 0:
            return 0.0
        return (self.verified_roms / total) * 100
    
    @property
    def verification_percent(self) -> float:
        """Percentual de ROMs verificadas."""
        if self.total_roms == 0:
            return 0.0
        return (self.verified_roms / self.total_roms) * 100
    
    @property
    def total_size_gb(self) -> float:
        """Tamanho total em GB."""
        return self.total_size_bytes / (1024**3)


@dataclass
class CollectionAnalytics:
    """Análise completa da coleção."""
    total_systems: int = 0
    total_roms: int = 0
    total_verified: int = 0
    total_size_bytes: int = 0
    systems: dict[str, SystemStats] = field(default_factory=dict)
    format_breakdown: dict[str, int] = field(default_factory=dict)
    missing_by_system: dict[str, list[str]] = field(default_factory=dict)
    
    @property
    def overall_completion(self) -> float:
        """Completion geral da coleção."""
        total_possible = sum(
            s.total_roms + s.missing_roms for s in self.systems.values()
        )
        if total_possible == 0:
            return 0.0
        return (self.total_verified / total_possible) * 100
    
    @property
    def total_size_gb(self) -> float:
        """Tamanho total em GB."""
        return self.total_size_bytes / (1024**3)
    
    @property
    def total_size_tb(self) -> float:
        """Tamanho total em TB."""
        return self.total_size_bytes / (1024**4)
    
    def get_top_systems_by_size(self, n: int = 5) -> list[tuple[str, float]]:
        """Retorna top N sistemas por tamanho."""
        items = [
            (sys, stats.total_size_gb)
            for sys, stats in self.systems.items()
        ]
        items.sort(key=lambda x: x[1], reverse=True)
        return items[:n]
    
    def get_top_formats_by_count(self, n: int = 5) -> list[tuple[str, int]]:
        """Retorna top N formatos por contagem."""
        items = list(self.format_breakdown.items())
        items.sort(key=lambda x: x[1], reverse=True)
        return items[:n]


class AnalyticsDashboard:
    """Dashboard de analytics da coleção."""
    
    def __init__(self, db: LibraryDB):
        self.db = db
    
    def generate_full_report(self) -> CollectionAnalytics:
        """Gera relatório completo da coleção."""
        analytics = CollectionAnalytics()
        
        # Obter todas as entradas
        entries = self.db.get_all_entries()
        
        # Processar por sistema
        by_system = defaultdict(list)
        for entry in entries:
            by_system[entry.system].append(entry)
        
        analytics.total_systems = len(by_system)
        analytics.total_roms = len(entries)
        
        # Análise por sistema
        for system, system_entries in by_system.items():
            stats = self._analyze_system(system, system_entries)
            analytics.systems[system] = stats
            analytics.total_verified += stats.verified_roms
            analytics.total_size_bytes += stats.total_size_bytes
            
            # Agregar formatos
            for fmt, count in stats.compression_formats.items():
                analytics.format_breakdown[fmt] = analytics.format_breakdown.get(fmt, 0) + count
        
        # Adicionar missing ROMs
        analytics.missing_by_system = self._find_missing_roms()
        
        return analytics
    
    def _analyze_system(self, system: str, entries: list[LibraryEntry]) -> SystemStats:
        """Analisa um sistema específico."""
        stats = SystemStats(system=system)
        
        stats.total_roms = len(entries)
        
        for entry in entries:
            # Status
            if entry.status == "VERIFIED":
                stats.verified_roms += 1
            else:
                stats.unverified_roms += 1
            
            # Tamanho
            stats.total_size_bytes += entry.size
            
            # Formato (extensão)
            ext = Path(entry.path).suffix.lower()
            if ext:
                stats.compression_formats[ext] = stats.compression_formats.get(ext, 0) + 1
        
        return stats
    
    def _find_missing_roms(self) -> dict[str, list[str]]:
        """Encontra ROMs faltantes baseado em DATs."""
        missing = {}
        
        # Para cada sistema com DAT carregado
        systems = self._get_systems_with_dats()
        
        for system in systems:
            # Obter entradas verificadas
            verified = {
                entry.dat_name for entry in self.db.get_all_entries()
                if entry.system == system and entry.status == "VERIFIED" and entry.dat_name
            }
            
            # Obter todos os games do DAT
            all_games = self._get_dat_games(system)
            missing_games = sorted(set(all_games) - verified)
            
            if missing_games:
                missing[system] = missing_games
        
        return missing
    
    def _get_systems_with_dats(self) -> list[str]:
        """Retorna lista de sistemas que têm DATs carregados."""
        # Implementação simplificada - pode ser melhorada
        # consultando a tabela de DATs se existir
        systems = set()
        for entry in self.db.get_all_entries():
            if entry.dat_name:
                systems.add(entry.system)
        return list(systems)
    
    def _get_dat_games(self, system: str) -> list[str]:
        """Retorna lista de jogos de um DAT."""
        # Esta é uma implementação simplificada
        # O ideal seria ter uma tabela separada para DATs
        # Por enquanto, retornamos apenas os jogos verificados
        games = set()
        for entry in self.db.get_all_entries():
            if entry.system == system and entry.dat_name:
                games.add(entry.dat_name)
        return list(games)
    
    def get_storage_breakdown(self) -> dict[str, dict]:
        """Breakdown detalhado de storage."""
        breakdown = {
            'by_system': {},
            'by_format': {},
            'total_bytes': 0,
            'total_gb': 0,
            'total_tb': 0,
        }
        
        entries = self.db.get_all_entries()
        
        # Por sistema
        by_system = defaultdict(int)
        for entry in entries:
            by_system[entry.system] += entry.size
            breakdown['total_bytes'] += entry.size
        
        breakdown['by_system'] = dict(by_system)
        
        # Por formato
        by_format = defaultdict(int)
        for entry in entries:
            ext = Path(entry.path).suffix.lower()
            if ext:
                by_format[ext] += entry.size
        
        breakdown['by_format'] = dict(by_format)
        
        # Conversões
        breakdown['total_gb'] = breakdown['total_bytes'] / (1024**3)
        breakdown['total_tb'] = breakdown['total_bytes'] / (1024**4)
        
        return breakdown
    
    def get_completion_summary(self) -> dict[str, float]:
        """Resumo de completion por sistema."""
        analytics = self.generate_full_report()
        
        return {
            system: stats.completion_percent
            for system, stats in analytics.systems.items()
        }
    
    def get_verification_summary(self) -> dict[str, float]:
        """Resumo de verificação por sistema."""
        analytics = self.generate_full_report()
        
        return {
            system: stats.verification_percent
            for system, stats in analytics.systems.items()
        }
    
    def generate_text_report(self) -> str:
        """Gera relatório em texto formatado."""
        analytics = self.generate_full_report()
        
        lines = []
        lines.append("=" * 70)
        lines.append("COLLECTION ANALYTICS REPORT")
        lines.append("=" * 70)
        lines.append("")
        
        # Overview
        lines.append("OVERVIEW")
        lines.append("-" * 70)
        lines.append(f"Total Systems: {analytics.total_systems}")
        lines.append(f"Total ROMs: {analytics.total_roms:,}")
        lines.append(f"Verified ROMs: {analytics.total_verified:,}")
        lines.append(f"Overall Completion: {analytics.overall_completion:.1f}%")
        lines.append(f"Total Storage: {analytics.total_size_gb:.2f} GB ({analytics.total_size_tb:.3f} TB)")
        lines.append("")
        
        # Per system
        lines.append("BY SYSTEM")
        lines.append("-" * 70)
        
        for system in sorted(analytics.systems.keys()):
            stats = analytics.systems[system]
            lines.append(f"\n{system}:")
            lines.append(f"  ROMs: {stats.total_roms:,} ({stats.verified_roms:,} verified)")
            lines.append(f"  Completion: {stats.completion_percent:.1f}%")
            lines.append(f"  Verification: {stats.verification_percent:.1f}%")
            lines.append(f"  Storage: {stats.total_size_gb:.2f} GB")
            
            if stats.compression_formats:
                formats = ", ".join(f"{fmt}({cnt})" for fmt, cnt in sorted(stats.compression_formats.items()))
                lines.append(f"  Formats: {formats}")
        
        lines.append("")
        
        # Top systems by size
        lines.append("TOP SYSTEMS BY SIZE")
        lines.append("-" * 70)
        for system, size_gb in analytics.get_top_systems_by_size():
            lines.append(f"{system:20} {size_gb:8.2f} GB")
        
        lines.append("")
        
        # Top formats
        lines.append("TOP FORMATS")
        lines.append("-" * 70)
        for fmt, count in analytics.get_top_formats_by_count():
            lines.append(f"{fmt:15} {count:8,} files")
        
        lines.append("")
        
        # Missing ROMs
        if analytics.missing_by_system:
            lines.append("MISSING ROMS")
            lines.append("-" * 70)
            
            for system in sorted(analytics.missing_by_system.keys()):
                missing = analytics.missing_by_system[system]
                lines.append(f"\n{system}: {len(missing)} missing")
                
                # Mostrar primeiras 10
                for game in missing[:10]:
                    lines.append(f"  - {game}")
                
                if len(missing) > 10:
                    lines.append(f"  ... and {len(missing) - 10} more")
        
        lines.append("")
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def generate_ascii_chart(self, data: dict[str, float], title: str, width: int = 60) -> str:
        """Gera gráfico ASCII simples."""
        if not data:
            return "No data"
        
        lines = []
        lines.append(title)
        lines.append("-" * width)
        
        max_value = max(data.values()) if data else 1
        
        for label, value in sorted(data.items(), key=lambda x: x[1], reverse=True):
            bar_length = int((value / max_value) * (width - 25)) if max_value > 0 else 0
            bar = "█" * bar_length
            lines.append(f"{label:15} {bar} {value:6.1f}%")
        
        return "\n".join(lines)
