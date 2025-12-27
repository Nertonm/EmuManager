"""Simple PySide6 GUI for EmuManager.

This module is intentionally lazy about importing PySide6 so the package can be
imported in environments without the GUI dependency. Call `main()` to run the
application; if PySide6 is not installed a clear RuntimeError is raised.
"""

from __future__ import annotations

from importlib import import_module

try:
    # Normal package import when used as module: `python -m emumanager.gui`
    from . import manager
except Exception:
    # Allow running the file directly (e.g. `python emumanager/gui.py`) by
    # ensuring the project root is on sys.path and then using absolute
    # imports. This mirrors the pattern used in `interface.py`.
    import sys
    from pathlib import Path as _P

    _ROOT = _P(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    from emumanager import manager


def _ensure_qt() -> None:
    # Prefer PyQt6 but accept PySide6 as a fallback. Import locally to avoid
    # hard dependency at package import time.
    try:
        import_module("PyQt6")
        return
    except Exception:
        try:
            import_module("PySide6")
            return
        except Exception as e:  # pragma: no cover - dependency check
            raise RuntimeError(
                "PyQt6 (preferred) or PySide6 is required for the GUI. "
                "Install 'pyqt6' or 'pyside6'."
            ) from e


def _run_app():
    # Import inside function to keep module import cheap. Prefer PyQt6.
    try:
        QtWidgets = import_module("PyQt6.QtWidgets")
    except Exception:
        QtWidgets = import_module("PySide6.QtWidgets")

    # Create the application and a MainWindow from the extracted component
    try:
        from .gui_main import MainWindowBase
    except Exception:
        # When run as script (not as a package) fall back to absolute import
        from emumanager.gui_main import MainWindowBase

    app = QtWidgets.QApplication([])

    # Check for headless mode (used by smoke tests)
    import sys

    if "--headless" in sys.argv:
        # Just instantiate the window to verify no crashes, then exit
        win_comp = MainWindowBase(QtWidgets, manager)
        return 0

    win_comp = MainWindowBase(QtWidgets, manager)
    win_comp.show()
    return app.exec()


def main() -> int:
    # Check for Qt availability and run
    _ensure_qt()
    try:
        return _run_app() or 0
    except Exception as e:
        print("GUI error:", e)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
