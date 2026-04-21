from __future__ import annotations

import logging


class MainWindowUIQtMixin:
    def _get_icon(self, qt, name: str):
        """Return a QIcon for a given QStyle StandardPixmap name, with fallbacks."""
        try:
            style = qt.QApplication.style()
            try:
                attr = getattr(qt.QStyle.StandardPixmap, name)
                return style.standardIcon(attr)
            except Exception:
                try:
                    attr = getattr(qt.QStyle, name)
                    return style.standardIcon(attr)
                except Exception:
                    return None
        except Exception:
            return None

    def _resolve_qt_namespaces(self):
        """Resolve Qt namespace for enums and common classes across PyQt/PySide."""
        self._qt_enum = None
        self._q_size = None
        try:
            from PyQt6.QtCore import QSize as _q_size
            from PyQt6.QtCore import Qt as _qt_enum

            self._qt_enum = _qt_enum
            self._q_size = _q_size
        except ImportError:
            try:
                from PySide6.QtCore import QSize as _q_size  # type: ignore
                from PySide6.QtCore import Qt as _qt_enum  # type: ignore

                self._qt_enum = _qt_enum
                self._q_size = _q_size
            except ImportError:
                logging.debug("Could not resolve Qt namespaces for enums.")
