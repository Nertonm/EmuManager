from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from emumanager.common.formatting import human_readable_size
from emumanager.library import LibraryDB, LibraryEntry
from emumanager.quality import QualityController, QualityLevel, RomQuality

STATUS_PREFIXES = {
    "VERIFIED": "✓",
    "CORRUPT": "✗",
    "ERROR": "⚠",
}
DEFAULT_STATUS_PREFIX = "?"
UNTRACKED_PREFIX = " "
QUALITY_FALLBACK_MARKUP = "[dim]?[/]"


def format_status_prefixed_name(filename: str, status: Optional[str]) -> str:
    """Return a consistent status prefix for ROM lists across interfaces."""
    if not status:
        return f"{UNTRACKED_PREFIX} {filename}"
    return f"{STATUS_PREFIXES.get(status, DEFAULT_STATUS_PREFIX)} {filename}"


def strip_status_prefixed_name(display_name: str) -> str:
    """Remove the UI status prefix used in ROM list views."""
    prefixes = tuple(
        f"{prefix} "
        for prefix in (*STATUS_PREFIXES.values(), DEFAULT_STATUS_PREFIX, UNTRACKED_PREFIX)
    )
    if display_name.startswith(prefixes):
        return display_name[2:]
    return display_name


@dataclass(slots=True)
class DashboardSnapshot:
    systems_count: int
    total_files: int
    total_size_bytes: int
    total_size_label: str
    last_scan_label: Optional[str] = None


@dataclass(slots=True)
class SystemSnapshot:
    system: str
    total: int
    verified: int
    corrupt: int
    unknown: int

    def to_log_message(self) -> str:
        return (
            f"System '{self.system}': {self.total} files - "
            f"{self.verified} verified, {self.corrupt} corrupt, "
            f"{self.unknown} unknown"
        )


@dataclass(slots=True)
class RomBrowserRow:
    filename: str
    path: str
    status: str
    quality_icon: Optional[str] = None
    quality_color: Optional[str] = None
    ra_compatible: bool = False
    entry: Optional[LibraryEntry] = None

    @property
    def display_name(self) -> str:
        return format_status_prefixed_name(self.filename, self.status if self.entry else None)

    @property
    def quality_markup(self) -> str:
        if not self.quality_icon:
            return QUALITY_FALLBACK_MARKUP
        color = self.quality_color or "white"
        return f"[{color}]{self.quality_icon}[/]"


@dataclass(slots=True)
class InspectorIssueSnapshot:
    severity: str
    description: str


@dataclass(slots=True)
class RomInspectionSnapshot:
    entry: LibraryEntry
    title: str
    status: str
    status_style: str
    quality_label: str
    quality_score: str
    quality_summary: str
    dat_name: str
    path: str
    ra_label: str
    metadata_lines: list[str] = field(default_factory=list)
    issues: list[InspectorIssueSnapshot] = field(default_factory=list)


class LibraryInsightsService:
    """Shared read-models for collection, inspector, and dashboard views."""

    def __init__(self, db: LibraryDB):
        self.db = db
        self._quality_controller = QualityController(db)

    def set_database(self, db: LibraryDB) -> None:
        self.db = db
        self._quality_controller = QualityController(db)

    def build_dashboard_snapshot(
        self,
        *,
        systems: Optional[Sequence[str]] = None,
        scan_stats: Optional[dict[str, int]] = None,
    ) -> DashboardSnapshot:
        total_files, total_size_bytes = self._resolve_collection_totals(scan_stats)
        last_scan_label = None
        if scan_stats:
            last_scan_label = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return DashboardSnapshot(
            systems_count=len(list(systems or [])),
            total_files=total_files,
            total_size_bytes=total_size_bytes,
            total_size_label=human_readable_size(total_size_bytes),
            last_scan_label=last_scan_label,
        )

    def build_system_snapshot(self, system: str) -> SystemSnapshot:
        entries = self.db.get_entries_by_system(system)
        return SystemSnapshot(
            system=system,
            total=len(entries),
            verified=sum(1 for entry in entries if entry.status == "VERIFIED"),
            corrupt=sum(1 for entry in entries if entry.status == "CORRUPT"),
            unknown=sum(1 for entry in entries if entry.status not in {"VERIFIED", "CORRUPT"}),
        )

    def build_rom_browser_rows(
        self,
        system: str,
        files: Sequence[Path],
    ) -> list[RomBrowserRow]:
        entry_map = {
            Path(entry.path).name: entry
            for entry in self.db.get_entries_by_system(system)
        }
        rows: list[RomBrowserRow] = []
        for file_path in files:
            filename = str(file_path)
            entry = entry_map.get(Path(file_path).name)
            rows.append(
                RomBrowserRow(
                    filename=filename,
                    path=entry.path if entry else filename,
                    status=entry.status if entry else "UNTRACKED",
                    ra_compatible=bool(entry and entry.extra_metadata.get("ra_compatible")),
                    entry=entry,
                )
            )
        return rows

    def get_system_rom_rows(
        self,
        system: str,
        *,
        include_quality: bool = False,
    ) -> list[RomBrowserRow]:
        rows: list[RomBrowserRow] = []
        for entry in self.db.get_entries_by_system(system):
            quality: Optional[RomQuality] = None
            if include_quality:
                quality = self._safe_analyze_quality(entry)
            rows.append(
                RomBrowserRow(
                    filename=Path(entry.path).name,
                    path=entry.path,
                    status=entry.status or "UNKNOWN",
                    quality_icon=quality.icon if quality else None,
                    quality_color=quality.color if quality else None,
                    ra_compatible=bool(entry.extra_metadata.get("ra_compatible")),
                    entry=entry,
                )
            )
        return rows

    def get_rom_inspection(self, path_str: str) -> Optional[RomInspectionSnapshot]:
        entry = self.db.get_entry(path_str)
        if not entry:
            return None

        quality = self._safe_analyze_quality(entry)
        quality_label = QUALITY_FALLBACK_MARKUP + " UNKNOWN"
        quality_score = "N/A"
        quality_summary = "ROM não verificada"
        issues: list[InspectorIssueSnapshot] = []

        if quality:
            quality_label = f"[{quality.color}]{quality.icon} {quality.quality_level.value}[/]"
            quality_score = f"{quality.score}/100"
            quality_summary = quality.get_summary()
            issues = [
                InspectorIssueSnapshot(
                    severity=issue.severity,
                    description=issue.description,
                )
                for issue in quality.issues[:5]
            ]

        title = entry.match_name or "Desconhecido"
        dat_name = entry.dat_name or "N/A"
        ra_label = (
            "Compatível 🏆"
            if entry.extra_metadata.get("ra_compatible")
            else "Incompatível ou não testado"
        )
        return RomInspectionSnapshot(
            entry=entry,
            title=title,
            status=entry.status,
            status_style=f"status_{(entry.status or 'unknown').lower()}",
            quality_label=quality_label,
            quality_score=quality_score,
            quality_summary=quality_summary,
            dat_name=dat_name,
            path=entry.path,
            ra_label=ra_label,
            metadata_lines=self._build_metadata_lines(entry),
            issues=issues,
        )

    def _resolve_collection_totals(
        self,
        scan_stats: Optional[dict[str, int]],
    ) -> tuple[int, int]:
        if scan_stats:
            return scan_stats.get("count", 0), scan_stats.get("size", 0)

        entries = self.db.get_all_entries()
        return len(entries), sum(entry.size for entry in entries)

    def _safe_analyze_quality(self, entry: LibraryEntry) -> Optional[RomQuality]:
        try:
            return self._quality_controller.analyze_rom(entry)
        except Exception:
            return None

    def _build_metadata_lines(self, entry: LibraryEntry) -> list[str]:
        lines = [
            "─" * 60,
            "📋 ROM METADATA:",
            f"  Status: {entry.status}",
        ]

        if entry.match_name:
            lines.append(f"  Title: {entry.match_name}")
        if entry.dat_name:
            lines.append(f"  Serial/ID: {entry.dat_name}")

        hashes = [
            ("CRC32", entry.crc32),
            ("SHA1", entry.sha1),
            ("MD5", entry.md5),
            ("SHA256", entry.sha256),
        ]
        if any(value for _, value in hashes):
            lines.append("  Hashes:")
            for label, value in hashes:
                if value:
                    lines.append(f"    {label}: {value}")

        lines.append(f"  Size: {human_readable_size(entry.size)}")

        extra = entry.extra_metadata or {}
        if extra.get("title"):
            lines.append(f"  Game Title: {extra['title']}")
        if extra.get("serial"):
            lines.append(f"  Game Serial: {extra['serial']}")
        if extra.get("region"):
            lines.append(f"  Region: {extra['region']}")
        if extra.get("ra_compatible"):
            lines.append("  RetroAchievements: ✓ Compatible")

        quality = self._safe_analyze_quality(entry)
        if quality:
            lines.append(
                f"  Quality: {quality.quality_level.value} "
                f"({quality.score}/100)"
            )
            if quality.quality_level in {QualityLevel.DAMAGED, QualityLevel.CORRUPT}:
                critical = quality.get_critical_issues()
                if critical:
                    lines.append(f"  Critical Issue: {critical[0].description}")

        lines.append("─" * 60)
        return lines
