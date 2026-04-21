from __future__ import annotations

from .gui_main_library_browser import MainWindowLibraryBrowserMixin
from .gui_main_library_scan import MainWindowLibraryScanMixin
from .gui_main_quarantine import MainWindowQuarantineMixin


class MainWindowLibraryMixin(
    MainWindowLibraryScanMixin,
    MainWindowQuarantineMixin,
    MainWindowLibraryBrowserMixin,
):
    """Stable façade for library-related GUI behavior split across focused mixins."""

    pass
