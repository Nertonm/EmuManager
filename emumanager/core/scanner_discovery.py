from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from emumanager.common.registry import registry
from emumanager.common.validation import validate_path_exists
from emumanager.common.exceptions import ValidationError


class ScannerDiscoveryMixin:
    def scan_directory(
        self,
        root: Path,
        progress_cb: Optional[Callable[[float, str], None]] = None,
        cancel_event: Optional[Any] = None,
        deep_scan: bool = False,
    ) -> dict[str, int]:
        try:
            root = validate_path_exists(root, "scan root", must_be_dir=True)
        except Exception as exc:
            raise ValidationError(f"Invalid scan directory: {exc}") from exc

        stats = {"added": 0, "updated": 0, "removed": 0, "skipped": 0, "verified": 0}
        if not root.exists():
            return stats

        existing_entries = {entry.path: entry for entry in self.db.get_all_entries()}
        found_paths: set[str] = set()
        systems = self._get_system_directories(root)
        total_systems = len(systems)

        for index, system_dir in enumerate(systems):
            if cancel_event and cancel_event.is_set():
                break
            if progress_cb and total_systems > 0:
                progress_cb(index / total_systems, f"Scanning {system_dir.name}...")
            self._process_system(
                system_dir,
                deep_scan,
                stats,
                found_paths,
                existing_entries,
                cancel_event,
            )

        self._cleanup_removed_entries(existing_entries, found_paths, stats)
        return stats

    def _get_system_directories(self, root: Path) -> list[Path]:
        return [entry for entry in root.iterdir() if entry.is_dir() and not entry.name.startswith(".")]

    def _process_system(
        self,
        system_dir: Path,
        deep_scan: bool,
        stats: dict,
        found_paths: set[str],
        existing_entries: dict,
        cancel_event: Optional[Any],
    ):
        system_name = system_dir.name
        provider = registry.get_provider(system_name)
        dat_db = self._load_dat(system_name)

        for file_path in system_dir.rglob("*"):
            if cancel_event and cancel_event.is_set():
                break
            if self._is_valid_rom_file(file_path):
                self._process_file(
                    file_path,
                    system_name,
                    provider,
                    dat_db,
                    deep_scan,
                    stats,
                    found_paths,
                    existing_entries,
                )

    def _is_valid_rom_file(self, path: Path) -> bool:
        return path.is_file() and not path.name.startswith(".") and not path.name.startswith("_")

    def _cleanup_removed_entries(
        self,
        existing_entries: dict,
        found_paths: set[str],
        stats: dict,
    ):
        for path in existing_entries:
            if path not in found_paths:
                self.db.remove_entry(path)
                stats["removed"] += 1
