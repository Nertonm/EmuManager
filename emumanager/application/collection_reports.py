from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from emumanager.analytics import AnalyticsDashboard
from emumanager.deduplication import AdvancedDeduplication
from emumanager.library import LibraryDB
from emumanager.quality import QualityController, QualityLevel


@dataclass(slots=True)
class OperationReport:
    summary: str
    lines: list[str] = field(default_factory=list)


class CollectionReportService:
    """Shared report builders for analytics, deduplication, and quality views."""

    def __init__(self, db: LibraryDB):
        self.db = db

    def set_database(self, db: LibraryDB) -> None:
        self.db = db

    def build_advanced_dedup_report(self) -> OperationReport:
        dedup = AdvancedDeduplication(self.db)
        groups = dedup.find_all_duplicates()
        stats = dedup.get_statistics()

        lines = [
            "[bold cyan]🔎 Analisando duplicados...[/]",
            "[green]✓ Análise completa![/]",
            f"  Total de grupos: {stats['total_groups']}",
            f"  Espaço desperdiçado: {stats['total_wasted_gb']:.2f} GB",
        ]

        for duplicate_type, type_stats in stats["by_type"].items():
            wasted_gb = type_stats["wasted_bytes"] / (1024**3)
            lines.append(
                f"  [{duplicate_type}]: {type_stats['count']} grupos, {wasted_gb:.2f} GB"
            )

        lines.append("\n[bold yellow]TOP 10 DUPLICADOS:[/]")
        sorted_groups = sorted(groups, key=lambda group: group.space_savings, reverse=True)
        for index, group in enumerate(sorted_groups[:10], 1):
            lines.append(
                f"  {index}. [{group.duplicate_type}] {group.key[:50]}... "
                f"({group.count} files, {group.space_savings / (1024**2):.1f} MB)"
            )
            if group.recommended_keep:
                lines.append(f"     [green]→ Keep:[/] {Path(group.recommended_keep).name}")
                reason = group.get_recommendation_reason()
                if reason:
                    lines.append(f"     [dim]{reason}[/]")

        return OperationReport(
            summary=f"Found {stats['total_groups']} duplicate groups",
            lines=lines,
        )

    def build_analytics_report(self) -> OperationReport:
        dashboard = AnalyticsDashboard(self.db)
        analytics = dashboard.generate_full_report()
        report_lines = dashboard.generate_text_report().splitlines()
        lines = ["[bold cyan]📊 Gerando relatório...[/]", *report_lines]

        completion_data = {
            system: stats.completion_percent
            for system, stats in analytics.systems.items()
        }
        if completion_data:
            lines.extend(
                dashboard.generate_ascii_chart(
                    completion_data,
                    "\n📈 COMPLETION BY SYSTEM",
                    width=60,
                ).splitlines()
            )

        verification_data = {
            system: stats.verification_percent
            for system, stats in analytics.systems.items()
        }
        if verification_data:
            lines.extend(
                dashboard.generate_ascii_chart(
                    verification_data,
                    "\n✓ VERIFICATION BY SYSTEM",
                    width=60,
                ).splitlines()
            )

        return OperationReport(
            summary=(
                f"Analytics complete: {analytics.total_systems} systems, "
                f"{analytics.total_roms} ROMs"
            ),
            lines=lines,
        )

    def build_quality_report(self) -> OperationReport:
        quality_controller = QualityController(self.db)
        stats = quality_controller.get_quality_statistics()
        results = quality_controller.analyze_library()
        total = stats["total"]
        playable_percent = (stats["playable"] / total * 100) if total else 0.0
        damaged_percent = (stats["damaged"] / total * 100) if total else 0.0

        lines = [
            "[bold cyan]🏥 Verificando qualidade das ROMs...[/]",
            "[green]✓ Análise completa![/]",
            f"  Total analisado: {total} ROMs",
            f"  Score médio: {stats['average_score']:.1f}/100",
            f"  Jogáveis: {stats['playable']} ({playable_percent:.1f}%)",
            f"  Danificadas: {stats['damaged']} ({damaged_percent:.1f}%)",
            "\n[bold yellow]DISTRIBUIÇÃO DE QUALIDADE:[/]",
        ]

        level_names = {
            "PERFECT": "✓✓ Perfect",
            "GOOD": "✓ Good",
            "QUESTIONABLE": "⚠ Questionable",
            "DAMAGED": "✗ Damaged",
            "CORRUPT": "✗✗ Corrupt",
            "UNKNOWN": "? Unknown",
        }
        for level, count in stats["by_level"].items():
            percent = (count / total * 100) if total else 0.0
            lines.append(f"  {level_names.get(level, level):20} {count:4} ({percent:5.1f}%)")

        if stats["issues_by_type"]:
            issue_names = {
                "INVALID_HEADER": "Header inválido",
                "INVALID_CHECKSUM": "Checksum inválido",
                "TRUNCATED_FILE": "Arquivo truncado",
                "ZERO_BYTES": "Bytes nulos",
                "HEADER_CORRUPTION": "Header corrompido",
                "SUSPICIOUS_SIZE": "Tamanho suspeito",
                "METADATA_MISSING": "Metadados ausentes",
            }
            lines.append("\n[bold yellow]TOP PROBLEMAS ENCONTRADOS:[/]")
            sorted_issues = sorted(
                stats["issues_by_type"].items(),
                key=lambda item: item[1],
                reverse=True,
            )
            for issue_type, count in sorted_issues[:10]:
                lines.append(f"  {issue_names.get(issue_type, issue_type):30} {count:4}")

        lines.append("\n[bold red]ATENÇÃO - ROMs CORROMPIDAS:[/]")
        damaged_roms = [
            (path, quality)
            for path, quality in results.items()
            if quality.quality_level in {QualityLevel.DAMAGED, QualityLevel.CORRUPT}
        ]
        if not damaged_roms:
            lines.append("  [green]Nenhuma ROM corrompida encontrada! ✓[/]")
        else:
            for path, quality in damaged_roms[:10]:
                lines.append(f"  [{quality.color}]{quality.icon}[/] {Path(path).name[:60]}")
                critical = quality.get_critical_issues()
                if critical:
                    lines.append(f"     → {critical[0].description}")
            if len(damaged_roms) > 10:
                lines.append(f"  ... e mais {len(damaged_roms) - 10} ROMs com problemas")

        return OperationReport(
            summary=f"Quality check complete: {total} ROMs analyzed",
            lines=lines,
        )
