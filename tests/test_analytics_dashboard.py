"""Testes para Analytics Dashboard."""

import tempfile
from pathlib import Path

import pytest

from emumanager.library import LibraryDB, LibraryEntry
from emumanager.analytics import AnalyticsDashboard, CollectionAnalytics, SystemStats


@pytest.fixture
def temp_db():
    """Cria um banco de dados temporário."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = LibraryDB(db_path)
        yield db


@pytest.fixture
def sample_collection(temp_db):
    """Popula banco com uma coleção de exemplo."""
    entries = [
        # PS2
        LibraryEntry(
            path="/roms/ps2/Game1.iso",
            system="ps2",
            size=4_000_000_000,  # 4GB
            mtime=1234567890,
            status="VERIFIED",
            dat_name="Game 1",
        ),
        LibraryEntry(
            path="/roms/ps2/Game2.iso",
            system="ps2",
            size=3_500_000_000,  # 3.5GB
            mtime=1234567891,
            status="VERIFIED",
            dat_name="Game 2",
        ),
        LibraryEntry(
            path="/roms/ps2/Game3.iso",
            system="ps2",
            size=4_200_000_000,  # 4.2GB
            mtime=1234567892,
            status="UNKNOWN",
        ),
        # GBA
        LibraryEntry(
            path="/roms/gba/Pokemon.gba",
            system="gba",
            size=16_000_000,  # 16MB
            mtime=1234567890,
            status="VERIFIED",
            dat_name="Pokemon Emerald",
        ),
        LibraryEntry(
            path="/roms/gba/Zelda.gba",
            system="gba",
            size=8_000_000,  # 8MB
            mtime=1234567891,
            status="VERIFIED",
            dat_name="Zelda Minish Cap",
        ),
        # PSX
        LibraryEntry(
            path="/roms/psx/FF7.bin",
            system="psx",
            size=700_000_000,  # 700MB
            mtime=1234567890,
            status="VERIFIED",
            dat_name="Final Fantasy VII",
        ),
    ]
    
    for entry in entries:
        temp_db.update_entry(entry)
    
    return temp_db


def test_system_stats_init():
    """Testa inicialização de SystemStats."""
    stats = SystemStats(system="ps2")
    
    assert stats.system == "ps2"
    assert stats.total_roms == 0
    assert stats.verified_roms == 0
    assert stats.total_size_bytes == 0


def test_system_stats_completion_percent():
    """Testa cálculo de completion percent."""
    stats = SystemStats(
        system="ps2",
        total_roms=10,
        verified_roms=8,
        missing_roms=2,
    )
    
    # 8 verified / (10 + 2) total = 66.66%
    assert 66.0 <= stats.completion_percent <= 67.0


def test_system_stats_verification_percent():
    """Testa cálculo de verification percent."""
    stats = SystemStats(
        system="ps2",
        total_roms=10,
        verified_roms=7,
    )
    
    # 7 / 10 = 70%
    assert stats.verification_percent == 70.0


def test_system_stats_total_size_gb():
    """Testa conversão de bytes para GB."""
    stats = SystemStats(
        system="ps2",
        total_size_bytes=5_000_000_000,  # 5GB
    )
    
    assert 4.6 <= stats.total_size_gb <= 4.7  # ~4.66GB


def test_collection_analytics_init():
    """Testa inicialização de CollectionAnalytics."""
    analytics = CollectionAnalytics()
    
    assert analytics.total_systems == 0
    assert analytics.total_roms == 0
    assert analytics.total_verified == 0
    assert len(analytics.systems) == 0


def test_collection_analytics_overall_completion():
    """Testa cálculo de completion geral."""
    analytics = CollectionAnalytics()
    analytics.systems = {
        "ps2": SystemStats(
            system="ps2",
            total_roms=10,
            verified_roms=8,
            missing_roms=2,
        ),
        "gba": SystemStats(
            system="gba",
            total_roms=5,
            verified_roms=4,
            missing_roms=1,
        ),
    }
    analytics.total_verified = 12
    
    # 12 verified / (10+2+5+1) total = 66.66%
    assert 66.0 <= analytics.overall_completion <= 67.0


def test_collection_analytics_total_size_conversions():
    """Testa conversões de tamanho."""
    analytics = CollectionAnalytics()
    analytics.total_size_bytes = 5_000_000_000_000  # 5TB
    
    assert 4600 <= analytics.total_size_gb <= 4700
    assert 4.5 <= analytics.total_size_tb <= 5.5


def test_collection_analytics_top_systems_by_size():
    """Testa ordenação de sistemas por tamanho."""
    analytics = CollectionAnalytics()
    analytics.systems = {
        "ps2": SystemStats(system="ps2", total_size_bytes=10_000_000_000),
        "gba": SystemStats(system="gba", total_size_bytes=100_000_000),
        "psx": SystemStats(system="psx", total_size_bytes=5_000_000_000),
    }
    
    top = analytics.get_top_systems_by_size(n=2)
    
    assert len(top) == 2
    assert top[0][0] == "ps2"  # Maior
    assert top[1][0] == "psx"  # Segundo maior


def test_collection_analytics_top_formats_by_count():
    """Testa ordenação de formatos por contagem."""
    analytics = CollectionAnalytics()
    analytics.format_breakdown = {
        ".iso": 100,
        ".gba": 50,
        ".bin": 25,
    }
    
    top = analytics.get_top_formats_by_count(n=2)
    
    assert len(top) == 2
    assert top[0] == (".iso", 100)
    assert top[1] == (".gba", 50)


def test_dashboard_init(temp_db):
    """Testa inicialização do dashboard."""
    dashboard = AnalyticsDashboard(temp_db)
    
    assert dashboard.db == temp_db


def test_dashboard_generate_full_report(sample_collection):
    """Testa geração de relatório completo."""
    dashboard = AnalyticsDashboard(sample_collection)
    analytics = dashboard.generate_full_report()
    
    assert analytics.total_systems >= 3  # Pelo menos ps2, gba, psx
    assert analytics.total_roms >= 6
    assert analytics.total_verified >= 5  # 2 ps2 + 2 gba + 1 psx
    assert analytics.total_size_bytes > 0


def test_dashboard_analyze_system(sample_collection):
    """Testa análise de um sistema específico."""
    dashboard = AnalyticsDashboard(sample_collection)
    
    entries = sample_collection.get_entries_by_system("ps2")
    stats = dashboard._analyze_system("ps2", entries)
    
    assert stats.system == "ps2"
    assert stats.total_roms >= 3  # Pelo menos 3
    assert stats.verified_roms >= 2  # Pelo menos 2
    assert stats.total_size_bytes > 0
    assert ".iso" in stats.compression_formats


def test_dashboard_get_storage_breakdown(sample_collection):
    """Testa breakdown de storage."""
    dashboard = AnalyticsDashboard(sample_collection)
    breakdown = dashboard.get_storage_breakdown()
    
    assert 'by_system' in breakdown
    assert 'by_format' in breakdown
    assert 'total_bytes' in breakdown
    assert 'total_gb' in breakdown
    assert 'total_tb' in breakdown
    
    assert "ps2" in breakdown['by_system']
    assert "gba" in breakdown['by_system']
    assert "psx" in breakdown['by_system']
    
    assert breakdown['total_bytes'] > 0
    assert breakdown['total_gb'] > 0


def test_dashboard_get_completion_summary(sample_collection):
    """Testa resumo de completion."""
    dashboard = AnalyticsDashboard(sample_collection)
    summary = dashboard.get_completion_summary()
    
    assert isinstance(summary, dict)
    assert "ps2" in summary
    assert "gba" in summary
    assert "psx" in summary
    
    for system, percent in summary.items():
        assert 0.0 <= percent <= 100.0


def test_dashboard_get_verification_summary(sample_collection):
    """Testa resumo de verificação."""
    dashboard = AnalyticsDashboard(sample_collection)
    summary = dashboard.get_verification_summary()
    
    assert isinstance(summary, dict)
    assert "ps2" in summary
    
    # PS2 deve ter pelo menos 50% verificado
    assert summary["ps2"] >= 50.0


def test_dashboard_generate_text_report(sample_collection):
    """Testa geração de relatório em texto."""
    dashboard = AnalyticsDashboard(sample_collection)
    report = dashboard.generate_text_report()
    
    assert isinstance(report, str)
    assert len(report) > 0
    assert "COLLECTION ANALYTICS REPORT" in report
    assert "OVERVIEW" in report
    assert "BY SYSTEM" in report
    assert "TOP SYSTEMS BY SIZE" in report
    assert "ps2" in report.lower()
    assert "gba" in report.lower()


def test_dashboard_generate_ascii_chart():
    """Testa geração de gráfico ASCII."""
    dashboard = AnalyticsDashboard(None)  # Não precisa de DB
    
    data = {
        "System A": 75.5,
        "System B": 50.0,
        "System C": 25.0,
    }
    
    chart = dashboard.generate_ascii_chart(data, "Test Chart", width=60)
    
    assert isinstance(chart, str)
    assert "Test Chart" in chart
    assert "System A" in chart
    assert "System B" in chart
    assert "System C" in chart
    assert "█" in chart  # Barra


def test_dashboard_generate_ascii_chart_empty():
    """Testa gráfico ASCII com dados vazios."""
    dashboard = AnalyticsDashboard(None)
    chart = dashboard.generate_ascii_chart({}, "Empty", width=60)
    
    assert chart == "No data"


def test_dashboard_integration_formats(sample_collection):
    """Teste de integração: formatos detectados."""
    dashboard = AnalyticsDashboard(sample_collection)
    analytics = dashboard.generate_full_report()
    
    # Verificar que formatos foram detectados
    assert len(analytics.format_breakdown) > 0
    assert ".iso" in analytics.format_breakdown or \
           ".gba" in analytics.format_breakdown or \
           ".bin" in analytics.format_breakdown


def test_dashboard_integration_missing_roms(sample_collection):
    """Teste de integração: missing ROMs."""
    dashboard = AnalyticsDashboard(sample_collection)
    analytics = dashboard.generate_full_report()
    
    # missing_by_system pode estar vazio se não há DATs completos
    assert isinstance(analytics.missing_by_system, dict)


def test_system_stats_edge_case_zero_roms():
    """Testa edge case: sistema sem ROMs."""
    stats = SystemStats(system="empty")
    
    assert stats.completion_percent == 0.0
    assert stats.verification_percent == 0.0
    assert stats.total_size_gb == 0.0


def test_collection_analytics_edge_case_no_systems():
    """Testa edge case: coleção sem sistemas."""
    analytics = CollectionAnalytics()
    
    assert analytics.overall_completion == 0.0
    assert len(analytics.get_top_systems_by_size()) == 0
    assert len(analytics.get_top_formats_by_count()) == 0
