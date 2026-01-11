import pytest
from pathlib import Path
from emumanager.core.session import Session
from emumanager.core.orchestrator import Orchestrator
from emumanager.library import LibraryDB, LibraryEntry

@pytest.fixture
def clean_orch(tmp_path):
    base = tmp_path / "test_env"
    base.mkdir()
    orch = Orchestrator(Session(base))
    orch.initialize_library()
    return orch

def test_quarantine_edge_cases(clean_orch):
    """Valida se a quarentena lida corretamente com ficheiros fantasmas."""
    db = clean_orch.db
    # Criar entrada na DB de ficheiro que não existe no disco
    phantom_path = clean_orch.session.base_path / "roms" / "ps2" / "ghost.iso"
    db.update_entry(LibraryEntry(
        path=str(phantom_path.resolve()),
        system="ps2",
        size=100,
        mtime=1.0,
        status="CORRUPT"
    ))
    
    # Executar quarentena - não deve crashar
    stats = clean_orch.quarantine_corrupt_files(dry_run=False)
    assert stats["quarantined"] == 0 # Nada foi movido porque não existia no disco

def test_deduplication_preference(clean_orch):
    """Garante que o motor prefere formatos comprimidos (CHD > ISO)."""
    ps2_dir = clean_orch.session.base_path / "roms" / "ps2"
    iso_file = ps2_dir / "game.iso"
    chd_file = ps2_dir / "game.chd"
    
    iso_file.write_bytes(b"same data")
    chd_file.write_bytes(b"same data")
    
    db = clean_orch.db
    # Simular mesmo SHA1 para ambos
    common_hash = "sha1_123"
    db.update_entry(LibraryEntry(path=str(iso_file.resolve()), system="ps2", size=100, mtime=1.0, sha1=common_hash))
    db.update_entry(LibraryEntry(path=str(chd_file.resolve()), system="ps2", size=50, mtime=1.0, sha1=common_hash))
    
    stats = clean_orch.cleanup_duplicates(dry_run=False)
    
    assert stats["removed"] == 1
    assert chd_file.exists()
    assert not iso_file.exists() # ISO deve ter sido removida por ser menos eficiente

def test_switch_hierarchy_routing(clean_orch):
    """Valida se o roteamento Base/Update/DLC no Switch está correto."""
    switch_dir = clean_orch.session.base_path / "roms" / "switch"
    update_file = switch_dir / "patch.nsp"
    update_file.write_bytes(b"nsp data")
    
    db = clean_orch.db
    # 0100000000010800 -> Sufixo 800 indica Update
    meta = {"title": "Zelda", "serial": "0100000000010800", "version": 1, "category": "Updates"}
    db.update_entry(LibraryEntry(
        path=str(update_file.resolve()),
        system="switch",
        size=100,
        mtime=1.0,
        dat_name="0100000000010800",
        extra_metadata=meta
    ))
    
    clean_orch.organize_names(dry_run=False)
    
    expected_path = switch_dir / "Updates" / "Zelda" / "Zelda [0100000000010800] [v1].nsp"
    assert expected_path.exists()

def test_technical_guide_persistence(clean_orch):
    """Garante que guias técnicos são regenerados com info correta."""
    ps2_guide = clean_orch.session.roms_path / "ps2" / "_INFO_TECNICA.txt"
    assert "https://pcsx2.net" in ps2_guide.read_text()
    assert ".chd (Recomendado)" in ps2_guide.read_text()
