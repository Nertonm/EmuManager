from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

from emumanager.library import LibraryEntry
from emumanager.verification import dat_parser

METADATA_RETRIES = 3
METADATA_RETRY_DELAY = 0.5


class ScannerEntriesMixin:
    def _load_dat(self, system_name: str) -> Optional[Any]:
        if not self.dat_manager:
            return None

        dat_path = self.dat_manager.find_dat_for_system(system_name)
        if not dat_path:
            return None

        try:
            dat_db = dat_parser.parse_dat_file(dat_path)
            self.logger.info("DAT carregado para %s: %s", system_name, dat_path.name)
            return dat_db
        except Exception as exc:
            self.logger.warning("Erro ao carregar DAT para %s: %s", system_name, exc)
            return None

    def _process_file(
        self,
        file_path: Path,
        system_name: str,
        provider: Any,
        dat_db: Optional[Any],
        deep_scan: bool,
        stats: dict,
        found_paths: set[str],
        existing_entries: dict,
    ):
        abs_path = str(file_path.resolve())
        found_paths.add(abs_path)

        stat = file_path.stat()
        entry = existing_entries.get(abs_path)
        needs_hashing = self._check_needs_hashing(file_path, stat, entry, deep_scan)
        metadata = self._extract_provider_metadata(file_path, provider)
        hashes, match_info = self._handle_verification(
            file_path,
            entry,
            dat_db,
            needs_hashing,
            metadata,
            system_name,
        )

        status = match_info.get("status", entry.status if entry else "UNKNOWN")
        match_name = match_info.get(
            "match_name",
            entry.match_name if entry else metadata.get("title"),
        )
        dat_name = match_info.get(
            "dat_name",
            entry.dat_name if entry else metadata.get("serial"),
        )

        self.db.update_entry(
            LibraryEntry(
                path=abs_path,
                system=system_name,
                size=stat.st_size,
                mtime=stat.st_mtime,
                status=status,
                crc32=hashes.get("crc32"),
                md5=hashes.get("md5"),
                sha1=hashes.get("sha1"),
                match_name=match_name,
                dat_name=dat_name,
                extra_metadata=metadata,
            )
        )
        stats["added" if not entry else "updated"] += 1

    def _check_needs_hashing(
        self,
        path: Path,
        stat: Any,
        entry: Optional[LibraryEntry],
        deep_scan: bool,
    ) -> bool:
        del path
        if deep_scan or not entry:
            return True
        return entry.size != stat.st_size or abs(entry.mtime - stat.st_mtime) >= 1.0

    def _extract_provider_metadata(self, path: Path, provider: Any) -> dict:
        if not provider:
            return {}

        for attempt in range(METADATA_RETRIES):
            try:
                return provider.extract_metadata(path)
            except Exception as exc:
                if attempt < METADATA_RETRIES - 1:
                    self.logger.debug(
                        "Tentativa %s/%s ao extrair metadados de %s: %s",
                        attempt + 1,
                        METADATA_RETRIES,
                        path.name,
                        exc,
                    )
                    time.sleep(METADATA_RETRY_DELAY)
                else:
                    self.logger.warning(
                        "Erro extração metadados após %s tentativas para %s: %s",
                        METADATA_RETRIES,
                        path.name,
                        exc,
                    )
                    return {}

    def _build_entry(self, path: Path, system: str, metadata: dict) -> LibraryEntry:
        stat = path.stat()
        return LibraryEntry(
            path=str(path.resolve()),
            system=system,
            size=stat.st_size,
            mtime=stat.st_mtime,
            status="KNOWN" if metadata.get("serial") else "UNKNOWN",
            match_name=metadata.get("title"),
            dat_name=metadata.get("serial"),
            extra_metadata=metadata,
        )
