"""Testes para Advanced Deduplication."""

import tempfile
from pathlib import Path

import pytest

from emumanager.library import LibraryDB, LibraryEntry
from emumanager.deduplication import AdvancedDeduplication, AdvancedDuplicateGroup


@pytest.fixture
def temp_db():
    """Cria um banco de dados temporário."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = LibraryDB(db_path)
        yield db


@pytest.fixture
def sample_entries():
    """Entradas de exemplo para testes."""
    return [
        # Duplicados exatos (mesmo hash)
        LibraryEntry(
            path="/roms/ps2/Final Fantasy X (USA).iso",
            system="ps2",
            size=4_000_000_000,
            mtime=1234567890,
            status="VERIFIED",
            sha1="abc123",
        ),
        LibraryEntry(
            path="/roms/ps2/backups/Final Fantasy X (USA) copy.iso",
            system="ps2",
            size=4_000_000_000,
            mtime=1234567891,
            status="VERIFIED",
            sha1="abc123",
        ),
        # Cross-region
        LibraryEntry(
            path="/roms/ps2/Final Fantasy X (USA).iso",
            system="ps2",
            size=4_000_000_000,
            mtime=1234567890,
            status="VERIFIED",
            sha1="abc123",
            match_name="Final Fantasy X",
        ),
        LibraryEntry(
            path="/roms/ps2/Final Fantasy X (Europe).iso",
            system="ps2",
            size=4_050_000_000,  # 5% diferente
            mtime=1234567891,
            status="VERIFIED",
            sha1="def456",
            match_name="Final Fantasy X",
        ),
        LibraryEntry(
            path="/roms/ps2/Final Fantasy X (Japan).iso",
            system="ps2",
            size=3_950_000_000,  # 5% diferente
            mtime=1234567892,
            status="VERIFIED",
            sha1="ghi789",
            match_name="Final Fantasy X",
        ),
        # Versões diferentes
        LibraryEntry(
            path="/roms/gba/Pokemon Emerald (USA) (v1.0).gba",
            system="gba",
            size=16_000_000,
            mtime=1234567890,
            status="VERIFIED",
            sha1="poke1",
            match_name="Pokemon Emerald",
        ),
        LibraryEntry(
            path="/roms/gba/Pokemon Emerald (USA) (v1.1).gba",
            system="gba",
            size=16_000_000,
            mtime=1234567891,
            status="VERIFIED",
            sha1="poke2",
            match_name="Pokemon Emerald",
        ),
        # Fuzzy matching
        LibraryEntry(
            path="/roms/ps1/Crash Bandicoot - Warped.bin",
            system="ps1",
            size=500_000_000,
            mtime=1234567890,
            status="VERIFIED",
            sha1="crash1",
            match_name="Crash Bandicoot Warped",
        ),
        LibraryEntry(
            path="/roms/ps1/Crash Bandicoot 3 - Warped.bin",
            system="ps1",
            size=505_000_000,  # Ligeiramente diferente
            mtime=1234567891,
            status="VERIFIED",
            sha1="crash2",
            match_name="Crash Bandicoot 3 Warped",
        ),
    ]


def test_advanced_deduplication_init(temp_db):
    """Testa inicialização do AdvancedDeduplication."""
    dedup = AdvancedDeduplication(temp_db)
    
    assert dedup.db == temp_db
    assert dedup.fuzzy_threshold == 0.85
    assert 'USA' in dedup.region_tags
    assert dedup.region_priority['World'] == 10


def test_find_exact_duplicates(temp_db, sample_entries):
    """Testa detecção de duplicados exatos."""
    # Adicionar entries com mesmo hash
    for entry in sample_entries[:2]:  # Primeiro par: mesmo sha1
        temp_db.update_entry(entry)
    
    dedup = AdvancedDeduplication(temp_db)
    exact_dups = dedup._find_exact_duplicates()
    
    assert len(exact_dups) > 0
    assert exact_dups[0].duplicate_type == 'exact'
    assert exact_dups[0].similarity_score == 1.0


def test_find_cross_region_duplicates(temp_db, sample_entries):
    """Testa detecção de duplicados cross-region."""
    # Adicionar entries cross-region
    for entry in sample_entries[2:5]:  # Final Fantasy X USA/Europe/Japan
        temp_db.update_entry(entry)
    
    dedup = AdvancedDeduplication(temp_db)
    cross_region = dedup._find_cross_region_duplicates()
    
    assert len(cross_region) > 0
    assert cross_region[0].duplicate_type == 'cross_region'
    assert cross_region[0].count >= 2


def test_find_version_duplicates(temp_db, sample_entries):
    """Testa detecção de diferentes versões."""
    # Adicionar entries com diferentes versões
    for entry in sample_entries[5:7]:  # Pokemon v1.0 e v1.1
        temp_db.update_entry(entry)
    
    dedup = AdvancedDeduplication(temp_db)
    versions = dedup._find_version_duplicates()
    
    assert len(versions) > 0
    assert versions[0].duplicate_type == 'version'


def test_select_best_version_prefers_verified(temp_db):
    """Testa que a seleção prefere status VERIFIED."""
    entries = [
        LibraryEntry(
            path="/roms/game1.iso",
            system="ps2",
            size=1000,
            mtime=1.0,
            status="UNKNOWN",
        ),
        LibraryEntry(
            path="/roms/game2.iso",
            system="ps2",
            size=1000,
            mtime=1.0,
            status="VERIFIED",
        ),
    ]
    
    dedup = AdvancedDeduplication(temp_db)
    best = dedup._select_best_version(entries)
    
    assert "game2" in best


def test_select_best_version_prefers_usa(temp_db):
    """Testa que a seleção prefere região USA."""
    entries = [
        LibraryEntry(
            path="/roms/Game (Japan).iso",
            system="ps2",
            size=1000,
            mtime=1.0,
            status="VERIFIED",
        ),
        LibraryEntry(
            path="/roms/Game (USA).iso",
            system="ps2",
            size=1000,
            mtime=1.0,
            status="VERIFIED",
        ),
    ]
    
    dedup = AdvancedDeduplication(temp_db)
    best = dedup._select_best_version(entries)
    
    # USA tem prioridade maior que Japan
    assert "USA" in best or best == "/roms/Game (USA).iso"


def test_remove_region_tags(temp_db):
    """Testa remoção de tags de região."""
    dedup = AdvancedDeduplication(temp_db)
    
    assert dedup._remove_region_tags("Game (USA)") == "Game"
    assert dedup._remove_region_tags("Game [Europe]") == "Game"
    assert dedup._remove_region_tags("Game (USA) (Europe)") == "Game"


def test_remove_version_tags(temp_db):
    """Testa remoção de tags de versão."""
    dedup = AdvancedDeduplication(temp_db)
    
    assert dedup._remove_version_tags("Game (v1.0)") == "Game"
    assert dedup._remove_version_tags("Game Rev 1") == "Game"
    assert dedup._remove_version_tags("Game v1.2") == "Game"


def test_extract_region(temp_db):
    """Testa extração de região."""
    dedup = AdvancedDeduplication(temp_db)
    
    assert dedup._extract_region("/roms/Game (USA).iso") == "USA"
    assert dedup._extract_region("/roms/Game [Europe].iso") == "Europe"
    assert dedup._extract_region("/roms/Game (Japan).iso") == "Japan"


def test_extract_version_info(temp_db):
    """Testa extração de versão."""
    dedup = AdvancedDeduplication(temp_db)
    
    assert dedup._extract_version_info("/roms/Game (v1.0).iso") == "v1.0"
    assert dedup._extract_version_info("/roms/Game Rev 2.iso") == "Rev 2"
    assert dedup._extract_version_info("/roms/Game v3.5.iso") == "v3.5"


def test_are_similar_sizes(temp_db):
    """Testa comparação de tamanhos."""
    dedup = AdvancedDeduplication(temp_db)
    
    # Tamanhos similares (dentro de 10%)
    similar = [
        LibraryEntry(path="a", system="s", size=1000, mtime=1.0),
        LibraryEntry(path="b", system="s", size=1090, mtime=1.0),  # 9%
    ]
    assert dedup._are_similar_sizes(similar) is True
    
    # Tamanhos diferentes (mais de 10%)
    different = [
        LibraryEntry(path="a", system="s", size=1000, mtime=1.0),
        LibraryEntry(path="b", system="s", size=1200, mtime=1.0),  # 20%
    ]
    assert dedup._are_similar_sizes(different) is False


def test_calculate_similarity(temp_db):
    """Testa cálculo de similaridade."""
    dedup = AdvancedDeduplication(temp_db)
    
    # Strings idênticas
    assert dedup._calculate_similarity("test", "test") == 1.0
    
    # Strings similares
    sim = dedup._calculate_similarity("Final Fantasy X", "Final Fantasy 10")
    assert 0.7 < sim < 1.0
    
    # Strings diferentes
    sim = dedup._calculate_similarity("Mario", "Zelda")
    assert sim < 0.5


def test_get_statistics(temp_db, sample_entries):
    """Testa geração de estatísticas."""
    # Adicionar várias entries
    for entry in sample_entries:
        temp_db.update_entry(entry)
    
    dedup = AdvancedDeduplication(temp_db)
    stats = dedup.get_statistics()
    
    assert 'total_groups' in stats
    assert 'total_wasted_bytes' in stats
    assert 'total_wasted_gb' in stats
    assert 'by_type' in stats
    assert isinstance(stats['total_groups'], int)
    assert isinstance(stats['total_wasted_gb'], float)


def test_recommendation_reason(temp_db):
    """Testa geração de razão da recomendação."""
    group = AdvancedDuplicateGroup(
        key="test",
        kind="exact",
        entries=[
            LibraryEntry(
                path="/roms/Game (USA).iso",
                system="ps2",
                size=1000,
                mtime=1.0,
                status="VERIFIED",
            ),
        ],
        recommended_keep="/roms/Game (USA).iso",
    )
    
    reason = group.get_recommendation_reason()
    assert "Verified" in reason or "Preferred region" in reason


def test_find_all_duplicates_integration(temp_db, sample_entries):
    """Teste de integração: find_all_duplicates."""
    for entry in sample_entries:
        temp_db.update_entry(entry)
    
    dedup = AdvancedDeduplication(temp_db)
    all_dups = dedup.find_all_duplicates()
    
    # Deve encontrar vários tipos de duplicados
    assert len(all_dups) > 0
    
    # Verificar que cada grupo tem recommended_keep
    for group in all_dups:
        assert group.recommended_keep is not None
        assert group.duplicate_type in ['exact', 'cross_region', 'version', 'fuzzy']
