from __future__ import annotations

from .gui_main_library_browser_actions import MainWindowLibraryBrowserActionsMixin
from .gui_main_library_browser_listing import MainWindowLibraryBrowserListingMixin
from .gui_main_library_browser_runtime import MainWindowLibraryBrowserRuntimeMixin


class MainWindowLibraryBrowserMixin(
    MainWindowLibraryBrowserActionsMixin,
    MainWindowLibraryBrowserListingMixin,
    MainWindowLibraryBrowserRuntimeMixin,
):
    """Stable facade for GUI library browsing, actions and runtime helpers."""

    pass
