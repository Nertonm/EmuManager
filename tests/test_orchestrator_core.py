import pytest
import json
from pathlib import Path
from emumanager.core.session import Session
from emumanager.core.orchestrator import Orchestrator
from emumanager.library import LibraryDB

def test_orchestrator_organize_flow(tmp_path):
    """
    Valida o workflow completo de organização:
    Inicialização -> Scan -> Enriquecimento de Metadados -> Renomeação Canónica.
    """
    # 1. Setup do Ambiente (Biblioteca Temporária)
    base = tmp_path / "test_lib"
    base.mkdir()
    session = Session(base)
    orchestrator = Orchestrator(session)
    orchestrator.initialize_library()
    
    # 2. Criar ficheiro "sujo" para teste (PS2)
    # Colocamos o ficheiro na pasta correta para o scanner o detetar
    ps2_root = base / "roms" / "ps2"
    dirty_file = ps2_root / "SLES_500.03.iso" 
    dirty_file.write_bytes(b"PS2 ISO DUMMY DATA")
    
    # 3. Executar Workflow de Auditoria (Catalogação)
    orchestrator.scan_library()
    
    # Verificar se o scanner catalogou o ficheiro
    db = LibraryDB(base / "library.db")
    abs_path = str(dirty_file.resolve())
    entry = db.get_entry(abs_path)
    assert entry is not None
    
    # Simular o enriquecimento de metadados (como se tivesse vindo de um DAT ou Provider)
    # Forçamos metadados ricos para validar a lógica de renomeação do Orchestrator
    db.update_entry_fields(
        abs_path, 
        match_name="Tekken 4", 
        dat_name="SLES-50003",
        extra_json=json.dumps({"title": "Tekken 4", "serial": "SLES-50003"})
    )
    
    # 4. Executar Workflow de Organização (Fase de Transformação)
    stats = orchestrator.organize_names(dry_run=False)
    
    # 5. Validação de Resultados Físicos
    assert stats["renamed"] == 1
    expected_path = ps2_root / "Tekken 4 [SLES-50003].iso"
    
    assert expected_path.exists()
    assert not dirty_file.exists()
    
    # 6. Validação de Persistência (Sincronização de DB)
    # A entrada antiga deve ter sido removida e a nova inserida com o novo caminho
    new_entry = db.get_entry(str(expected_path.resolve()))
    assert new_entry is not None
    assert new_entry.match_name == "Tekken 4"
    assert new_entry.dat_name == "SLES-50003"
    assert new_entry.system == "ps2"

def test_orchestrator_quarantine_flow(tmp_path):
    """Valida o isolamento físico de ficheiros corrompidos."""
    base = tmp_path / "quarantine_lib"
    base.mkdir()
    orchestrator = Orchestrator(Session(base))
    orchestrator.initialize_library()
    
    # Criar ficheiro marcado como CORRUPT
    sys_root = base / "roms" / "psx"
    corrupt_file = sys_root / "bad_game.bin"
    corrupt_file.write_bytes(b"some bad data")
    
    db = LibraryDB(base / "library.db")
    from emumanager.library import LibraryEntry
    db.update_entry(LibraryEntry(
        path=str(corrupt_file.resolve()),
        system="psx",
        size=13,
        mtime=1234567.0,
        status="CORRUPT"
    ))
    
    # Executar Manutenção
    stats = orchestrator.maintain_integrity(dry_run=False)
    
    # Verificar Quarentena
    assert stats["quarantined"] == 1
    quarantined_path = base / "_QUARANTINE" / "psx" / "bad_game.bin"
    assert quarantined_path.exists()
    assert not corrupt_file.exists()
    
    # Verificar se a DB reflete o novo local na quarentena
    entry = db.get_entry(str(quarantined_path.resolve()))
    assert entry is not None
    assert entry.status == "QUARANTINED"
