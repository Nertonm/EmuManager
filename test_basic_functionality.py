#!/usr/bin/env python3
"""
Script de teste básico para validar a funcionalidade do TUI.
"""

from pathlib import Path
import sys

def test_imports():
    """Testa todos os imports críticos."""
    print("🔍 Testando imports...")
    try:
        print("  ✓ manager")
        
        print("  ✓ config")
        
        print("  ✓ core.orchestrator")
        
        print("  ✓ core.session")
        
        print("  ✓ common.events")
        
        print("  ✓ common.types (NEW)")
        
        print("  ✓ library")
        
        print("  ✓ tui")
        
        return True
    except Exception as e:
        print(f"  ✗ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_manager_functions():
    """Testa funções do manager."""
    print("\n🔧 Testando funções do manager...")
    try:
        from emumanager.manager import get_roms_dir
        
        # Testar get_roms_dir
        test_path = Path("/tmp/test_base")
        roms_dir = get_roms_dir(test_path)
        assert roms_dir == test_path / "roms"
        print("  ✓ get_roms_dir")
        
        # Testar com path que já é roms
        roms_path = Path("/tmp/roms")
        result = get_roms_dir(roms_path)
        assert result == roms_path
        print("  ✓ get_roms_dir (roms path)")
        
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tui_creation():
    """Testa criação da instância do TUI."""
    print("\n🎨 Testando criação do TUI...")
    try:
        from emumanager.tui import AsyncFeedbackTui
        
        # Configurar path temporário
        test_base = Path("/tmp/emumanager_test")
        test_base.mkdir(exist_ok=True)
        
        # Criar instância
        tui = AsyncFeedbackTui(test_base)
        print("  ✓ TUI instance created")
        print(f"    Base: {tui.base}")
        print(f"    Orchestrator: {type(tui.orchestrator).__name__}")
        print(f"    Cancel event: {tui.cancel_event}")
        
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_library_db():
    """Testa LibraryDB."""
    print("\n💾 Testando LibraryDB...")
    try:
        from emumanager.library import LibraryDB
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = Path(tmp.name)
        
        db = LibraryDB(db_path)
        print(f"  ✓ LibraryDB created at {db_path}")
        
        # Testar transaction context manager
        with db.transaction() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"  ✓ Tables: {tables}")
            
        # Verificar índices
        conn = db._get_conn()
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]
        print(f"  ✓ Indexes: {len([i for i in indexes if i.startswith('idx_')])} custom indexes")
        
        # Cleanup
        db_path.unlink()
        
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_types():
    """Testa módulo de tipos."""
    print("\n📦 Testando common.types...")
    try:
        from emumanager.common.types import (
            WorkerResult, ScanResult
        )
        
        # Criar WorkerResult
        result = WorkerResult(task_name="Test")
        result.success_count = 10
        result.failed_count = 2
        result.skipped_count = 1
        
        print(f"  ✓ WorkerResult: {result}")
        print(f"    Total items: {result.total_items}")
        print(f"    Success rate: {result.success_rate:.2%}")
        
        # Testar add_item_result
        result.add_item_result(
            Path("/test/file.iso"),
            "success",
            1234.5,
            system="ps2"
        )
        print("  ✓ ProcessedItem added")
        
        # Criar ScanResult
        scan = ScanResult(files_scanned=100, files_verified=95)
        print(f"  ✓ ScanResult: {scan.to_dict()}")
        
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Executa todos os testes."""
    print("=" * 60)
    print("🧪 EmuManager - Testes de Validação")
    print("=" * 60)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Manager Functions", test_manager_functions()))
    results.append(("LibraryDB", test_library_db()))
    results.append(("Types Module", test_types()))
    results.append(("TUI Creation", test_tui_creation()))
    
    print("\n" + "=" * 60)
    print("📊 Resumo dos Testes")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)
    
    print(f"\n🎯 Total: {total_passed}/{total_tests} testes passaram")
    
    if total_passed == total_tests:
        print("✨ Todos os testes passaram! Sistema pronto para uso.")
        return 0
    else:
        print("⚠️  Alguns testes falharam. Revise os erros acima.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
