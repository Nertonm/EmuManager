from pathlib import Path
import shutil
import hashlib
from emumanager.core.session import Session
from emumanager.core.orchestrator import Orchestrator
from emumanager.library import LibraryDB, LibraryEntry

def setup():
    base = Path("test_dedupe_lib").resolve()
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True) # Criar diretoria antes de inicializar managers
    
    # 1. Inicializar estrutura
    orch = Orchestrator(Session(base))
    orch.initialize_library()
    
    # 2. Criar ficheiros duplicados (mesmo conteúdo)
    ps2_dir = base / "roms" / "ps2"
    file1 = ps2_dir / "Tekken 4 (Original).iso"
    file2 = ps2_dir / "Tekken 4 (Backup).iso"
    
    content = b"DUMMY ISO DATA" * 1000
    file1.write_bytes(content)
    file2.write_bytes(content)
    
    sha1 = hashlib.sha1(content).hexdigest()
    
    # 3. Forçar entrada na DB com o mesmo hash para o teste
    db = LibraryDB(base / "library.db")
    for f in [file1, file2]:
        db.update_entry(LibraryEntry(
            path=str(f.resolve()),
            system="ps2",
            size=len(content),
            mtime=f.stat().st_mtime,
            sha1=sha1,
            status="KNOWN"
        ))
    
    print(f"Cenário de teste criado em: {base}")
    print(f"Ficheiros: {file1.name} e {file2.name}")
    print(f"Hash comum: {sha1}")

if __name__ == "__main__":
    setup()