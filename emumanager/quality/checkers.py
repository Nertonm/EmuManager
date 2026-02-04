"""Health Checkers - Sistema-specific ROM validation."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Optional

from .controller import QualityIssue, RomQuality, IssueType


class BaseHealthChecker:
    """Checker base para sistemas."""
    
    def check(self, path: Path, quality: RomQuality) -> None:
        """Executa verificações específicas do sistema."""
        raise NotImplementedError


class PS2HealthChecker(BaseHealthChecker):
    """Health checker para PS2 ISOs."""
    
    def check(self, path: Path, quality: RomQuality) -> None:
        quality.checks_performed.append("PS2 ISO structure")
        
        # PS2 ISOs são baseados em ISO9660
        try:
            with open(path, 'rb') as f:
                # Verificar Volume Descriptor ISO9660
                f.seek(0x8000)  # Setor 16
                descriptor = f.read(6)
                
                if descriptor[1:6] != b'CD001':
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.INVALID_HEADER,
                        severity='critical',
                        description="ISO9660 descriptor inválido",
                        location="0x8000",
                        recommendation="Arquivo pode estar corrompido ou não ser uma ISO válida"
                    ))
                    quality.score -= 50
                    return
                
                # Verificar SYSTEM.CNF (marca de PS2)
                # Simplificado - em implementação completa, ler filesystem
                f.seek(0)
                sample = f.read(1024 * 1024)  # Primeiro MB
                
                if b'SYSTEM.CNF' not in sample and b'BOOT2' not in sample:
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.SUSPICIOUS_SIZE,
                        severity='medium',
                        description="Markers de PS2 não encontrados no início da ISO",
                        recommendation="Verificar se é realmente uma ISO de PS2"
                    ))
                    quality.score -= 20
                
                # Verificar tamanho (PS2 ISOs são geralmente 700MB-8.5GB)
                size = path.stat().st_size
                if size < 100 * 1024 * 1024:  # < 100MB
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.SUSPICIOUS_SIZE,
                        severity='high',
                        description=f"ISO muito pequena para PS2: {size/(1024**2):.1f} MB"
                    ))
                    quality.score -= 30
                elif size > 9 * 1024 * 1024 * 1024:  # > 9GB
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.SUSPICIOUS_SIZE,
                        severity='medium',
                        description=f"ISO muito grande para PS2: {size/(1024**3):.1f} GB"
                    ))
                    quality.score -= 10
                
        except Exception as e:
            quality.issues.append(QualityIssue(
                issue_type=IssueType.HEADER_CORRUPTION,
                severity='high',
                description=f"Erro ao ler estrutura ISO: {str(e)}"
            ))
            quality.score -= 30


class PSXHealthChecker(BaseHealthChecker):
    """Health checker para PSX BIN/CUE."""
    
    def check(self, path: Path, quality: RomQuality) -> None:
        quality.checks_performed.append("PSX disc structure")
        
        ext = path.suffix.lower()
        
        if ext == '.cue':
            # Verificar arquivo CUE
            self._check_cue(path, quality)
        elif ext == '.bin':
            # Verificar BIN
            self._check_bin(path, quality)
        elif ext == '.iso':
            # PSX ISO
            self._check_psx_iso(path, quality)
    
    def _check_cue(self, path: Path, quality: RomQuality) -> None:
        """Verifica arquivo .cue."""
        try:
            content = path.read_text(encoding='utf-8', errors='ignore')
            
            # Verificar referências a arquivos BIN
            if 'FILE' not in content or '.bin' not in content.lower():
                quality.issues.append(QualityIssue(
                    issue_type=IssueType.INVALID_HEADER,
                    severity='high',
                    description="CUE não referencia arquivo BIN",
                    recommendation="Arquivo CUE pode estar corrompido"
                ))
                quality.score -= 30
            
            # Verificar se BIN existe
            for line in content.split('\n'):
                if 'FILE' in line and '.bin' in line.lower():
                    bin_name = line.split('"')[1] if '"' in line else None
                    if bin_name:
                        bin_path = path.parent / bin_name
                        if not bin_path.exists():
                            quality.issues.append(QualityIssue(
                                issue_type=IssueType.MISSING_SECTIONS,
                                severity='critical',
                                description=f"Arquivo BIN não encontrado: {bin_name}",
                                recommendation="Dump incompleto"
                            ))
                            quality.score -= 50
        except Exception as e:
            quality.issues.append(QualityIssue(
                issue_type=IssueType.HEADER_CORRUPTION,
                severity='medium',
                description=f"Erro ao ler CUE: {str(e)}"
            ))
            quality.score -= 20
    
    def _check_bin(self, path: Path, quality: RomQuality) -> None:
        """Verifica arquivo .bin."""
        size = path.stat().st_size
        
        # PSX BIN deve ser múltiplo de 2352 (RAW sector)
        if size % 2352 != 0:
            quality.issues.append(QualityIssue(
                issue_type=IssueType.SUSPICIOUS_SIZE,
                severity='medium',
                description="BIN não é múltiplo de 2352 bytes (setor RAW)",
                recommendation="Pode ser dump cooked ou corrompido"
            ))
            quality.score -= 15
        
        # Tamanho típico: 700MB (CD-ROM)
        if size < 50 * 1024 * 1024:  # < 50MB
            quality.issues.append(QualityIssue(
                issue_type=IssueType.SUSPICIOUS_SIZE,
                severity='high',
                description=f"BIN muito pequeno: {size/(1024**2):.1f} MB"
            ))
            quality.score -= 30
    
    def _check_psx_iso(self, path: Path, quality: RomQuality) -> None:
        """Verifica PSX ISO."""
        try:
            with open(path, 'rb') as f:
                # PSX license string em setor específico
                f.seek(0x9340)  # Offset típico
                license_data = f.read(100)
                
                if b'Licensed by Sony' not in license_data:
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.METADATA_MISSING,
                        severity='low',
                        description="Sony license string não encontrada",
                        recommendation="Pode ser dump não oficial ou cooked"
                    ))
                    quality.score -= 10
        except Exception:
            pass  # Não crítico


class GBAHealthChecker(BaseHealthChecker):
    """Health checker para Game Boy Advance."""
    
    def check(self, path: Path, quality: RomQuality) -> None:
        quality.checks_performed.append("GBA header validation")
        
        try:
            with open(path, 'rb') as f:
                # Ler header completo (192 bytes)
                header = f.read(192)
                
                if len(header) < 192:
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.TRUNCATED_FILE,
                        severity='critical',
                        description="ROM truncada - header incompleto"
                    ))
                    quality.score = 0
                    return
                
                # Entry point (4 bytes) @ 0x00
                entry_point = header[0:4]
                # Deve começar com branch instruction (B ou BL)
                if entry_point[3] not in [0xEA, 0xEB]:  # B/BL opcodes
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.INVALID_HEADER,
                        severity='high',
                        description="Entry point inválido",
                        location="0x00-0x03",
                        recommendation="Header pode estar corrompido"
                    ))
                    quality.score -= 30
                
                # Nintendo logo (156 bytes) @ 0x04
                nintendo_logo = header[4:160]
                # Verificar se não é tudo zeros
                if nintendo_logo == b'\x00' * 156:
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.INVALID_HEADER,
                        severity='critical',
                        description="Nintendo logo ausente",
                        location="0x04-0x9F"
                    ))
                    quality.score -= 40
                
                # Game title (12 bytes) @ 0xA0
                title = header[160:172].rstrip(b'\x00')
                if len(title) == 0:
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.METADATA_MISSING,
                        severity='low',
                        description="Título do jogo ausente"
                    ))
                    quality.score -= 5
                
                # Header checksum @ 0xBD
                header_checksum = header[189]
                # Calcular checksum do header
                calculated = self._calculate_gba_checksum(header[160:189])
                
                if calculated != header_checksum:
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.INVALID_CHECKSUM,
                        severity='high',
                        description=f"Header checksum inválido (esperado {calculated:02X}, encontrado {header_checksum:02X})",
                        location="0xBD",
                        recommendation="Header corrompido ou ROM modificada"
                    ))
                    quality.score -= 25
                
                # Verificar tamanho (GBA ROMs: 4MB-32MB típico)
                size = path.stat().st_size
                if size < 1024 * 1024:  # < 1MB
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.SUSPICIOUS_SIZE,
                        severity='medium',
                        description=f"ROM muito pequena: {size/(1024**2):.2f} MB"
                    ))
                    quality.score -= 15
                elif size > 64 * 1024 * 1024:  # > 64MB
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.SUSPICIOUS_SIZE,
                        severity='low',
                        description=f"ROM muito grande para GBA: {size/(1024**2):.1f} MB"
                    ))
                    quality.score -= 10
                
        except Exception as e:
            quality.issues.append(QualityIssue(
                issue_type=IssueType.HEADER_CORRUPTION,
                severity='high',
                description=f"Erro ao ler header: {str(e)}"
            ))
            quality.score -= 30
    
    @staticmethod
    def _calculate_gba_checksum(header_data: bytes) -> int:
        """Calcula checksum do header GBA."""
        checksum = 0
        for byte in header_data:
            checksum = (checksum - byte) & 0xFF
        return (checksum - 0x19) & 0xFF


class SwitchHealthChecker(BaseHealthChecker):
    """Health checker para Nintendo Switch."""
    
    def check(self, path: Path, quality: RomQuality) -> None:
        quality.checks_performed.append("Switch format validation")
        
        ext = path.suffix.lower()
        
        if ext in ['.nsp', '.nsz']:
            self._check_nsp(path, quality)
        elif ext in ['.xci', '.xcz']:
            self._check_xci(path, quality)
    
    def _check_nsp(self, path: Path, quality: RomQuality) -> None:
        """Verifica NSP/NSZ."""
        try:
            with open(path, 'rb') as f:
                # NSP é basicamente um PFS0 (Package FileSystem)
                magic = f.read(4)
                
                if magic != b'PFS0':
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.INVALID_HEADER,
                        severity='critical',
                        description="Magic number PFS0 não encontrado",
                        location="0x00"
                    ))
                    quality.score -= 50
                    return
                
                # Ler número de arquivos
                num_files = struct.unpack('<I', f.read(4))[0]
                
                if num_files == 0:
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.SUSPICIOUS_SIZE,
                        severity='critical',
                        description="NSP não contém arquivos"
                    ))
                    quality.score -= 40
                elif num_files > 1000:  # Suspeito
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.HEADER_CORRUPTION,
                        severity='high',
                        description=f"Número de arquivos suspeito: {num_files}"
                    ))
                    quality.score -= 30
                
        except Exception as e:
            quality.issues.append(QualityIssue(
                issue_type=IssueType.HEADER_CORRUPTION,
                severity='high',
                description=f"Erro ao ler NSP: {str(e)}"
            ))
            quality.score -= 30
    
    def _check_xci(self, path: Path, quality: RomQuality) -> None:
        """Verifica XCI/XCZ."""
        try:
            with open(path, 'rb') as f:
                # XCI header
                magic = f.read(4)
                
                if magic != b'HEAD':
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.INVALID_HEADER,
                        severity='critical',
                        description="Magic number HEAD não encontrado",
                        location="0x100"
                    ))
                    quality.score -= 50
        except Exception as e:
            quality.issues.append(QualityIssue(
                issue_type=IssueType.HEADER_CORRUPTION,
                severity='high',
                description=f"Erro ao ler XCI: {str(e)}"
            ))
            quality.score -= 30


class GameCubeHealthChecker(BaseHealthChecker):
    """Health checker para GameCube."""
    
    def check(self, path: Path, quality: RomQuality) -> None:
        quality.checks_performed.append("GameCube ISO validation")
        
        try:
            with open(path, 'rb') as f:
                # GameCube boot.bin header
                header = f.read(0x2000)
                
                if len(header) < 0x2000:
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.TRUNCATED_FILE,
                        severity='critical',
                        description="ISO truncada"
                    ))
                    quality.score = 0
                    return
                
                # Disc ID (6 bytes) @ 0x00
                disc_id = header[0:6].decode('ascii', errors='ignore')
                
                # GameCube IDs começam com G
                if not disc_id.startswith('G'):
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.INVALID_HEADER,
                        severity='high',
                        description=f"Disc ID inválido: {disc_id}",
                        location="0x00",
                        recommendation="Pode não ser uma ISO de GameCube"
                    ))
                    quality.score -= 30
                
                # Game title @ 0x20
                title = header[0x20:0x40].rstrip(b'\x00').decode('ascii', errors='ignore')
                
                if len(title) == 0:
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.METADATA_MISSING,
                        severity='low',
                        description="Título ausente"
                    ))
                    quality.score -= 5
                
                # Verificar tamanho (1.4GB típico)
                size = path.stat().st_size
                if size < 100 * 1024 * 1024:  # < 100MB
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.SUSPICIOUS_SIZE,
                        severity='high',
                        description=f"ISO muito pequena: {size/(1024**2):.1f} MB"
                    ))
                    quality.score -= 30
                
        except Exception as e:
            quality.issues.append(QualityIssue(
                issue_type=IssueType.HEADER_CORRUPTION,
                severity='high',
                description=f"Erro ao ler ISO: {str(e)}"
            ))
            quality.score -= 30


def get_checker_for_system(system: str) -> Optional[BaseHealthChecker]:
    """Factory para obter checker específico do sistema."""
    checkers = {
        'ps2': PS2HealthChecker(),
        'psx': PSXHealthChecker(),
        'ps1': PSXHealthChecker(),
        'gba': GBAHealthChecker(),
        'switch': SwitchHealthChecker(),
        'gamecube': GameCubeHealthChecker(),
        'gc': GameCubeHealthChecker(),
    }
    
    return checkers.get(system.lower())
