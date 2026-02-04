"""Testes para Quality Control."""

import tempfile
from pathlib import Path

import pytest

from emumanager.library import LibraryDB, LibraryEntry
from emumanager.quality import (
    QualityController,
    RomQuality,
    QualityLevel,
    QualityIssue,
    IssueType,
    GBAHealthChecker,
)


@pytest.fixture
def temp_db():
    """Cria um banco de dados temporário."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = LibraryDB(db_path)
        yield db


@pytest.fixture
def temp_rom_file():
    """Cria arquivo ROM temporário."""
    with tempfile.TemporaryDirectory() as tmpdir:
        rom_path = Path(tmpdir) / "test.gba"
        yield rom_path


def test_rom_quality_init():
    """Testa inicialização de RomQuality."""
    quality = RomQuality(
        path="/test/rom.gba",
        quality_level=QualityLevel.PERFECT,
        system="gba"
    )
    
    assert quality.path == "/test/rom.gba"
    assert quality.quality_level == QualityLevel.PERFECT
    assert quality.score == 100
    assert quality.system == "gba"


def test_rom_quality_is_playable():
    """Testa verificação de ROM jogável."""
    perfect = RomQuality(path="test", quality_level=QualityLevel.PERFECT, system="gba")
    assert perfect.is_playable is True
    
    good = RomQuality(path="test", quality_level=QualityLevel.GOOD, system="gba")
    assert good.is_playable is True
    
    damaged = RomQuality(path="test", quality_level=QualityLevel.DAMAGED, system="gba")
    assert damaged.is_playable is False
    
    corrupt = RomQuality(path="test", quality_level=QualityLevel.CORRUPT, system="gba")
    assert corrupt.is_playable is False


def test_rom_quality_icon():
    """Testa ícones por nível de qualidade."""
    assert RomQuality(path="t", quality_level=QualityLevel.PERFECT, system="gba").icon == "✓✓"
    assert RomQuality(path="t", quality_level=QualityLevel.GOOD, system="gba").icon == "✓"
    assert RomQuality(path="t", quality_level=QualityLevel.QUESTIONABLE, system="gba").icon == "⚠"
    assert RomQuality(path="t", quality_level=QualityLevel.DAMAGED, system="gba").icon == "✗"
    assert RomQuality(path="t", quality_level=QualityLevel.CORRUPT, system="gba").icon == "✗✗"


def test_rom_quality_color():
    """Testa cores por nível de qualidade."""
    assert RomQuality(path="t", quality_level=QualityLevel.PERFECT, system="gba").color == "green"
    assert RomQuality(path="t", quality_level=QualityLevel.GOOD, system="gba").color == "cyan"
    assert RomQuality(path="t", quality_level=QualityLevel.DAMAGED, system="gba").color == "red"


def test_rom_quality_get_critical_issues():
    """Testa filtragem de issues críticos."""
    quality = RomQuality(path="test", quality_level=QualityLevel.DAMAGED, system="gba")
    
    quality.issues.append(QualityIssue(
        issue_type=IssueType.INVALID_HEADER,
        severity='critical',
        description="Header inválido"
    ))
    quality.issues.append(QualityIssue(
        issue_type=IssueType.METADATA_MISSING,
        severity='low',
        description="Metadata ausente"
    ))
    
    critical = quality.get_critical_issues()
    assert len(critical) == 1
    assert critical[0].severity == 'critical'


def test_rom_quality_get_summary():
    """Testa geração de resumo."""
    perfect = RomQuality(path="t", quality_level=QualityLevel.PERFECT, system="gba")
    assert "perfeita" in perfect.get_summary().lower()
    
    corrupt = RomQuality(path="t", quality_level=QualityLevel.CORRUPT, system="gba")
    assert "corrompida" in corrupt.get_summary().lower()


def test_quality_controller_init(temp_db):
    """Testa inicialização do controller."""
    controller = QualityController(temp_db)
    assert controller.db == temp_db
    assert controller._checkers == {}


def test_quality_controller_check_file_basics(temp_db, temp_rom_file):
    """Testa verificações básicas de arquivo."""
    # Criar ROM vazia
    temp_rom_file.write_bytes(b'')
    
    entry = LibraryEntry(
        path=str(temp_rom_file),
        system="gba",
        size=0,
        mtime=1.0,
        status="UNKNOWN"
    )
    
    controller = QualityController(temp_db)
    quality = controller.analyze_rom(entry)
    
    # Deve detectar arquivo vazio
    assert quality.score < 50
    assert any(i.issue_type == IssueType.ZERO_BYTES for i in quality.issues)


def test_quality_controller_check_zero_bytes(temp_db, temp_rom_file):
    """Testa detecção de arquivo com só zeros."""
    # Criar ROM com 2KB de zeros
    temp_rom_file.write_bytes(b'\x00' * 2048)
    
    entry = LibraryEntry(
        path=str(temp_rom_file),
        system="gba",
        size=2048,
        mtime=1.0,
        status="UNKNOWN"
    )
    
    controller = QualityController(temp_db)
    quality = controller.analyze_rom(entry)
    
    # Deve detectar bytes nulos
    assert any(i.issue_type == IssueType.ZERO_BYTES for i in quality.issues)


def test_quality_controller_determine_quality_level():
    """Testa determinação de nível de qualidade."""
    controller = QualityController(None)
    
    # Perfect: DAT verificado + score alto
    quality = RomQuality(path="t", quality_level=QualityLevel.UNKNOWN, system="gba", score=95, dat_verified=True)
    controller._determine_quality_level(quality)
    assert quality.quality_level == QualityLevel.PERFECT
    
    # Corrupt: issue crítico
    quality2 = RomQuality(path="t", quality_level=QualityLevel.UNKNOWN, system="gba", score=80)
    quality2.issues.append(QualityIssue(
        issue_type=IssueType.INVALID_HEADER,
        severity='critical',
        description="Test"
    ))
    controller._determine_quality_level(quality2)
    assert quality2.quality_level == QualityLevel.CORRUPT
    
    # Damaged: score baixo
    quality3 = RomQuality(path="t", quality_level=QualityLevel.UNKNOWN, system="gba", score=25)
    controller._determine_quality_level(quality3)
    assert quality3.quality_level == QualityLevel.DAMAGED


def test_quality_controller_get_statistics(temp_db):
    """Testa geração de estatísticas."""
    # Adicionar algumas entradas
    entries = [
        LibraryEntry(
            path="/roms/game1.gba",
            system="gba",
            size=1024*1024,
            mtime=1.0,
            status="VERIFIED"
        ),
        LibraryEntry(
            path="/roms/game2.gba",
            system="gba",
            size=1024*1024,
            mtime=1.0,
            status="UNKNOWN"
        ),
    ]
    
    for entry in entries:
        temp_db.update_entry(entry)
    
    controller = QualityController(temp_db)
    stats = controller.get_quality_statistics()
    
    assert 'total' in stats
    assert 'by_level' in stats
    assert 'playable' in stats
    assert 'damaged' in stats
    assert stats['total'] >= 2


def test_gba_checksum_calculation():
    """Testa cálculo de checksum GBA."""
    # Header de exemplo (29 bytes)
    header_data = b'POKEMON_EMEA\x00\x00\x00\x00\x41\x58\x56\x45\x30\x31\x96\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    
    checksum = GBAHealthChecker._calculate_gba_checksum(header_data)
    assert isinstance(checksum, int)
    assert 0 <= checksum <= 255


def test_gba_health_checker_valid_header(temp_rom_file):
    """Testa verificação de header GBA válido."""
    # Criar header GBA básico (192 bytes)
    header = bytearray(192)
    
    # Entry point: B instruction (EA 00 00 xx)
    header[0:4] = b'\x00\x00\x00\xEA'
    
    # Nintendo logo (não pode ser tudo zeros)
    header[4:160] = b'\x24' * 156
    
    # Game title
    header[160:172] = b'TEST GAME\x00\x00\x00'
    
    # Calcular checksum correto
    checksum = GBAHealthChecker._calculate_gba_checksum(header[160:189])
    header[189] = checksum
    
    # Escrever ROM
    temp_rom_file.write_bytes(header + b'\x00' * (1024*1024 - 192))
    
    quality = RomQuality(path=str(temp_rom_file), quality_level=QualityLevel.UNKNOWN, system="gba")
    checker = GBAHealthChecker()
    checker.check(temp_rom_file, quality)
    
    # Não deve ter issues críticos
    critical_issues = [i for i in quality.issues if i.severity == 'critical']
    assert len(critical_issues) == 0


def test_gba_health_checker_invalid_checksum(temp_rom_file):
    """Testa detecção de checksum inválido."""
    # Criar header com checksum errado
    header = bytearray(192)
    header[0:4] = b'\x00\x00\x00\xEA'
    header[4:160] = b'\x24' * 156
    header[160:172] = b'TEST GAME\x00\x00\x00'
    header[189] = 0xFF  # Checksum errado
    
    temp_rom_file.write_bytes(header + b'\x00' * (1024*1024 - 192))
    
    quality = RomQuality(path=str(temp_rom_file), quality_level=QualityLevel.UNKNOWN, system="gba")
    checker = GBAHealthChecker()
    checker.check(temp_rom_file, quality)
    
    # Deve detectar checksum inválido
    assert any(i.issue_type == IssueType.INVALID_CHECKSUM for i in quality.issues)


def test_gba_health_checker_truncated_file(temp_rom_file):
    """Testa detecção de arquivo truncado."""
    # ROM com menos de 192 bytes
    temp_rom_file.write_bytes(b'\x00' * 100)
    
    quality = RomQuality(path=str(temp_rom_file), quality_level=QualityLevel.UNKNOWN, system="gba")
    checker = GBAHealthChecker()
    checker.check(temp_rom_file, quality)
    
    # Deve detectar arquivo truncado
    assert any(i.issue_type == IssueType.TRUNCATED_FILE for i in quality.issues)
    assert quality.score == 0


def test_gba_health_checker_suspicious_size(temp_rom_file):
    """Testa detecção de tamanho suspeito."""
    # ROM muito pequena (500KB)
    header = bytearray(192)
    header[0:4] = b'\x00\x00\x00\xEA'
    header[4:160] = b'\x24' * 156
    
    temp_rom_file.write_bytes(header + b'\x00' * (500*1024 - 192))
    
    quality = RomQuality(path=str(temp_rom_file), quality_level=QualityLevel.UNKNOWN, system="gba")
    checker = GBAHealthChecker()
    checker.check(temp_rom_file, quality)
    
    # Deve detectar tamanho suspeito
    assert any(i.issue_type == IssueType.SUSPICIOUS_SIZE for i in quality.issues)


def test_quality_issue_dataclass():
    """Testa dataclass QualityIssue."""
    issue = QualityIssue(
        issue_type=IssueType.INVALID_HEADER,
        severity='critical',
        description="Teste",
        location="0x00",
        recommendation="Verificar"
    )
    
    assert issue.issue_type == IssueType.INVALID_HEADER
    assert issue.severity == 'critical'
    assert issue.description == "Teste"
    assert issue.location == "0x00"
    assert issue.recommendation == "Verificar"


def test_quality_level_enum():
    """Testa enum QualityLevel."""
    assert QualityLevel.PERFECT.value == "PERFECT"
    assert QualityLevel.GOOD.value == "GOOD"
    assert QualityLevel.CORRUPT.value == "CORRUPT"


def test_issue_type_enum():
    """Testa enum IssueType."""
    assert IssueType.INVALID_HEADER.value == "INVALID_HEADER"
    assert IssueType.INVALID_CHECKSUM.value == "INVALID_CHECKSUM"
    assert IssueType.TRUNCATED_FILE.value == "TRUNCATED_FILE"
