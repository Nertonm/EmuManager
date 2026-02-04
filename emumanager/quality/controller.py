"""Quality Controller - Main quality verification system."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from emumanager.library import LibraryDB, LibraryEntry

logger = logging.getLogger(__name__)


class QualityLevel(Enum):
    """Níveis de qualidade de ROM."""
    PERFECT = "PERFECT"  # ✓ Verificada por DAT, sem problemas
    GOOD = "GOOD"  # ✓ Funcional, pequenos problemas não críticos
    QUESTIONABLE = "QUESTIONABLE"  # ⚠ Problemas detectados, pode funcionar
    DAMAGED = "DAMAGED"  # ✗ Problemas graves, provavelmente corrompida
    CORRUPT = "CORRUPT"  # ✗✗ Definitivamente corrompida
    UNKNOWN = "UNKNOWN"  # ? Não verificada ainda


class IssueType(Enum):
    """Tipos de problemas detectados."""
    # Críticos
    INVALID_HEADER = "INVALID_HEADER"
    INVALID_CHECKSUM = "INVALID_CHECKSUM"
    TRUNCATED_FILE = "TRUNCATED_FILE"
    ZERO_BYTES = "ZERO_BYTES"
    
    # Graves
    HEADER_CORRUPTION = "HEADER_CORRUPTION"
    FILESYSTEM_ERRORS = "FILESYSTEM_ERRORS"
    MISSING_SECTIONS = "MISSING_SECTIONS"
    
    # Moderados
    SUSPICIOUS_SIZE = "SUSPICIOUS_SIZE"
    WEAK_DUMP = "WEAK_DUMP"
    BAD_SECTORS = "BAD_SECTORS"
    
    # Leves
    METADATA_MISSING = "METADATA_MISSING"
    NON_STANDARD_FORMAT = "NON_STANDARD_FORMAT"
    UNVERIFIED = "UNVERIFIED"


@dataclass
class QualityIssue:
    """Representa um problema de qualidade detectado."""
    issue_type: IssueType
    severity: str  # 'critical', 'high', 'medium', 'low'
    description: str
    location: Optional[str] = None  # Offset ou região do arquivo
    recommendation: Optional[str] = None


@dataclass
class RomQuality:
    """Resultado completo da análise de qualidade."""
    path: str
    quality_level: QualityLevel = QualityLevel.UNKNOWN
    score: int = 100  # 0-100
    issues: list[QualityIssue] = field(default_factory=list)
    checks_performed: list[str] = field(default_factory=list)
    dat_verified: bool = False
    system: str = "unknown"
    
    @property
    def is_playable(self) -> bool:
        """ROM é considerada jogável?"""
        return self.quality_level in [
            QualityLevel.PERFECT,
            QualityLevel.GOOD,
            QualityLevel.QUESTIONABLE
        ]
    
    @property
    def icon(self) -> str:
        """Ícone visual para o nível de qualidade."""
        icons = {
            QualityLevel.PERFECT: "✓✓",
            QualityLevel.GOOD: "✓",
            QualityLevel.QUESTIONABLE: "⚠",
            QualityLevel.DAMAGED: "✗",
            QualityLevel.CORRUPT: "✗✗",
            QualityLevel.UNKNOWN: "?",
        }
        return icons.get(self.quality_level, "?")
    
    @property
    def color(self) -> str:
        """Cor para visualização no TUI."""
        colors = {
            QualityLevel.PERFECT: "green",
            QualityLevel.GOOD: "cyan",
            QualityLevel.QUESTIONABLE: "yellow",
            QualityLevel.DAMAGED: "red",
            QualityLevel.CORRUPT: "red",
            QualityLevel.UNKNOWN: "dim",
        }
        return colors.get(self.quality_level, "white")
    
    def get_critical_issues(self) -> list[QualityIssue]:
        """Retorna apenas problemas críticos."""
        return [i for i in self.issues if i.severity == 'critical']
    
    def get_summary(self) -> str:
        """Resumo da qualidade."""
        if self.quality_level == QualityLevel.PERFECT:
            return "ROM perfeita, verificada por DAT"
        elif self.quality_level == QualityLevel.GOOD:
            return f"ROM funcional ({len(self.issues)} avisos menores)"
        elif self.quality_level == QualityLevel.QUESTIONABLE:
            return f"ROM suspeita ({len(self.issues)} problemas)"
        elif self.quality_level == QualityLevel.DAMAGED:
            return f"ROM danificada ({len(self.get_critical_issues())} erros críticos)"
        elif self.quality_level == QualityLevel.CORRUPT:
            return "ROM corrompida - não utilizável"
        else:
            return "ROM não verificada"


class QualityController:
    """Controlador principal de qualidade de ROMs."""
    
    def __init__(self, db: LibraryDB):
        self.db = db
        self._checkers = {}  # Cache de checkers por sistema
    
    def analyze_rom(self, entry: LibraryEntry) -> RomQuality:
        """Analisa qualidade de uma ROM."""
        quality = RomQuality(
            path=entry.path,
            system=entry.system,
            dat_verified=(entry.status == "VERIFIED")
        )
        
        try:
            path_obj = Path(entry.path)
            
            # 1. Verificações básicas
            self._check_file_basics(path_obj, quality)
            
            # 2. Verificação DAT
            if quality.dat_verified:
                quality.score += 20
                quality.checks_performed.append("DAT verification")
            
            # 3. Verificações específicas do sistema
            checker = self._get_checker(entry.system)
            if checker:
                checker.check(path_obj, quality)
            
            # 4. Determinar nível de qualidade final
            self._determine_quality_level(quality)
            
        except Exception as e:
            logger.error(f"Error analyzing {entry.path}: {e}")
            quality.issues.append(QualityIssue(
                issue_type=IssueType.UNVERIFIED,
                severity='high',
                description=f"Erro na análise: {str(e)}"
            ))
            quality.quality_level = QualityLevel.UNKNOWN
        
        return quality
    
    def _check_file_basics(self, path: Path, quality: RomQuality) -> None:
        """Verificações básicas de arquivo."""
        quality.checks_performed.append("file_basics")
        
        # Arquivo existe?
        if not path.exists():
            quality.issues.append(QualityIssue(
                issue_type=IssueType.MISSING_SECTIONS,
                severity='critical',
                description="Arquivo não encontrado"
            ))
            quality.score = 0
            return
        
        # Tamanho zero?
        size = path.stat().st_size
        if size == 0:
            quality.issues.append(QualityIssue(
                issue_type=IssueType.ZERO_BYTES,
                severity='critical',
                description="Arquivo vazio (0 bytes)"
            ))
            quality.score = 0
            return
        
        # Tamanho suspeito (< 1KB para maioria dos sistemas)
        if size < 1024 and quality.system not in ['atari2600', 'nes']:
            quality.issues.append(QualityIssue(
                issue_type=IssueType.SUSPICIOUS_SIZE,
                severity='high',
                description=f"Tamanho muito pequeno: {size} bytes",
                recommendation="Verificar se arquivo está completo"
            ))
            quality.score -= 30
        
        # Verificar se não é só zeros
        try:
            with open(path, 'rb') as f:
                sample = f.read(1024)
                if sample == b'\x00' * len(sample):
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.ZERO_BYTES,
                        severity='critical',
                        description="Arquivo contém apenas bytes nulos",
                        location="primeiros 1KB"
                    ))
                    quality.score -= 50
        except Exception as e:
            logger.warning(f"Could not sample file {path}: {e}")
    
    def _get_checker(self, system: str):
        """Obtém checker específico para o sistema."""
        if system not in self._checkers:
            # Import lazy para evitar dependências circulares
            from .checkers import get_checker_for_system
            self._checkers[system] = get_checker_for_system(system)
        
        return self._checkers[system]
    
    def _determine_quality_level(self, quality: RomQuality) -> None:
        """Determina o nível de qualidade final baseado no score e issues."""
        # Contabilizar severidades
        critical_count = sum(1 for i in quality.issues if i.severity == 'critical')
        high_count = sum(1 for i in quality.issues if i.severity == 'high')
        
        # Regras de decisão
        if critical_count > 0:
            quality.quality_level = QualityLevel.CORRUPT
        elif quality.score < 30:
            quality.quality_level = QualityLevel.DAMAGED
        elif quality.score < 60:
            quality.quality_level = QualityLevel.QUESTIONABLE
        elif quality.score < 90:
            quality.quality_level = QualityLevel.GOOD
        elif quality.dat_verified and quality.score >= 90:
            quality.quality_level = QualityLevel.PERFECT
        elif quality.score >= 90:
            quality.quality_level = QualityLevel.GOOD
        else:
            quality.quality_level = QualityLevel.UNKNOWN
    
    def analyze_library(self, system: Optional[str] = None) -> dict[str, RomQuality]:
        """Analisa todas as ROMs da biblioteca."""
        results = {}
        
        if system:
            entries = self.db.get_entries_by_system(system)
        else:
            entries = self.db.get_all_entries()
        
        for entry in entries:
            quality = self.analyze_rom(entry)
            results[entry.path] = quality
        
        return results
    
    def get_quality_statistics(self, system: Optional[str] = None) -> dict:
        """Estatísticas de qualidade da coleção."""
        results = self.analyze_library(system)
        
        stats = {
            'total': len(results),
            'by_level': {},
            'playable': 0,
            'damaged': 0,
            'average_score': 0,
            'issues_by_type': {},
        }
        
        for quality in results.values():
            # Por nível
            level = quality.quality_level.value
            stats['by_level'][level] = stats['by_level'].get(level, 0) + 1
            
            # Jogáveis vs danificadas
            if quality.is_playable:
                stats['playable'] += 1
            if quality.quality_level in [QualityLevel.DAMAGED, QualityLevel.CORRUPT]:
                stats['damaged'] += 1
            
            # Score médio
            stats['average_score'] += quality.score
            
            # Issues por tipo
            for issue in quality.issues:
                issue_type = issue.issue_type.value
                stats['issues_by_type'][issue_type] = stats['issues_by_type'].get(issue_type, 0) + 1
        
        if stats['total'] > 0:
            stats['average_score'] /= stats['total']
        
        return stats
