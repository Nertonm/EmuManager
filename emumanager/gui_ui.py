# -*- coding: utf-8 -*-
from __future__ import annotations

from .gui_ui_extra_tabs import MainWindowUIExtraTabsMixin
from .gui_ui_library import MainWindowUILibraryMixin
from .gui_ui_qt import MainWindowUIQtMixin
from .gui_ui_shell import MainWindowUIShellMixin
from .gui_ui_shared import MainWindowUISharedMixin
from .gui_ui_theme import MainWindowUIThemeMixin
from .gui_ui_tools import MainWindowUIToolsMixin


class MainWindowUI(
    MainWindowUIShellMixin,
    MainWindowUIQtMixin,
    MainWindowUIThemeMixin,
    MainWindowUISharedMixin,
    MainWindowUILibraryMixin,
    MainWindowUIToolsMixin,
    MainWindowUIExtraTabsMixin,
):
    """Stable facade for UI shell, Qt compatibility and theme helpers."""

    pass
