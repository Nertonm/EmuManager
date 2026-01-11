"""GUI robusta baseada no Core Orchestrator."""

from __future__ import annotations

import sys
from pathlib import Path
from importlib import import_module

from .logging_cfg import configure_logging, set_correlation_id
from .manager import get_orchestrator

def _ensure_qt():
    try:
        import_module("PyQt6")
    except ImportError:
        try:
            import_module("PySide6")
        except ImportError:
            raise RuntimeError("Instale 'pyqt6' ou 'pyside6' para usar a GUI.")

def _run_app():
    try:
        from PyQt6 import QtWidgets
    except ImportError:
        from PySide6 import QtWidgets

    from .gui_main import MainWindowBase
    
    app = QtWidgets.QApplication(sys.argv)
    
    # Usar a base padrão
    base_path = Path("Acervo_Games_Ultimate").resolve()
    orchestrator = get_orchestrator(base_path)
    
    # Smoke test: modo headless para CI/CD
    if "--headless" in sys.argv:
        print("Smoke Test: Inicializando MainWindow em modo headless...")
        win = MainWindowBase(QtWidgets, orchestrator)
        print("Sucesso: GUI carregada corretamente com o novo Core.")
        return 0

    win = MainWindowBase(QtWidgets, orchestrator)
    win.show()
    return app.exec()

def main() -> int:
    configure_logging()
    set_correlation_id()
    _ensure_qt()
    try:
        return _run_app() or 0
    except Exception as e:
        print(f"Erro fatal na GUI: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
