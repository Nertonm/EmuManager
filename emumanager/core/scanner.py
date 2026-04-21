from __future__ import annotations

from typing import Any

from emumanager.library import LibraryDB
from emumanager.logging_cfg import get_logger
from emumanager.core.intelligence import MatchEngine
from emumanager.metadata_providers.retroachievements import RetroAchievementsProvider
from emumanager.core.scanner_discovery import ScannerDiscoveryMixin
from emumanager.core.scanner_entries import ScannerEntriesMixin
from emumanager.core.scanner_verification import ScannerVerificationMixin


class Scanner(
    ScannerDiscoveryMixin,
    ScannerEntriesMixin,
    ScannerVerificationMixin,
):
    """Discover, catalog and verify ROM files for the active library."""

    def __init__(self, db: LibraryDB, dat_manager: Any = None):
        self.db = db
        self.dat_manager = dat_manager
        self.intelligence = MatchEngine()
        self.ra_provider = RetroAchievementsProvider()
        self.logger = get_logger("core.scanner")
