from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from emumanager.application import (
    CollectionReportService,
    LibraryInsightsService,
    execute_core_workflow,
    format_status_prefixed_name,
    strip_status_prefixed_name,
)
from emumanager.library import LibraryDB, LibraryEntry


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield LibraryDB(db_path)


@pytest.fixture
def sample_entry(temp_db):
    entry = LibraryEntry(
        path="/roms/ps2/Tekken 4.iso",
        system="ps2",
        size=4_000_000_000,
        mtime=1234567890,
        status="VERIFIED",
        crc32="ABC12345",
        sha1="DEADBEEF",
        match_name="Tekken 4",
        dat_name="SLES-50003",
        extra_metadata={"ra_compatible": True, "region": "USA"},
    )
    temp_db.update_entry(entry)
    return entry


def test_format_status_prefixed_name():
    assert format_status_prefixed_name("game.iso", "VERIFIED") == "✓ game.iso"
    assert format_status_prefixed_name("game.iso", "CORRUPT") == "✗ game.iso"
    assert format_status_prefixed_name("game.iso", None) == "  game.iso"


def test_strip_status_prefixed_name():
    assert strip_status_prefixed_name("✓ game.iso") == "game.iso"
    assert strip_status_prefixed_name("✗ game.iso") == "game.iso"
    assert strip_status_prefixed_name("? game.iso") == "game.iso"
    assert strip_status_prefixed_name("  game.iso") == "game.iso"
    assert strip_status_prefixed_name("game.iso") == "game.iso"


def test_library_insights_dashboard_snapshot_uses_db_totals(temp_db, sample_entry):
    service = LibraryInsightsService(temp_db)

    snapshot = service.build_dashboard_snapshot(systems=["ps2"])

    assert snapshot.systems_count == 1
    assert snapshot.total_files == 1
    assert snapshot.total_size_bytes == sample_entry.size
    assert snapshot.total_size_label.endswith("GB")


def test_library_insights_build_rom_browser_rows(temp_db, sample_entry):
    service = LibraryInsightsService(temp_db)

    rows = service.build_rom_browser_rows("ps2", [Path("Tekken 4.iso"), Path("Unknown.iso")])

    assert [row.display_name for row in rows] == ["✓ Tekken 4.iso", "  Unknown.iso"]
    assert rows[0].entry is not None
    assert rows[1].entry is None


def test_library_insights_get_rom_inspection_includes_metadata_lines(temp_db, sample_entry):
    service = LibraryInsightsService(temp_db)

    inspection = service.get_rom_inspection(sample_entry.path)

    assert inspection is not None
    assert inspection.title == "Tekken 4"
    assert inspection.ra_label == "Compatível 🏆"
    assert any("SHA1: DEADBEEF" in line for line in inspection.metadata_lines)
    assert any("Quality:" in line for line in inspection.metadata_lines)


def test_collection_report_service_build_analytics_report(temp_db, sample_entry):
    service = CollectionReportService(temp_db)

    report = service.build_analytics_report()

    assert "Analytics complete" in report.summary
    assert any("COLLECTION ANALYTICS REPORT" in line for line in report.lines)


def test_execute_core_workflow_routes_supported_arguments():
    orchestrator = MagicMock()
    orchestrator.scan_library.return_value = {"count": 1}
    orchestrator.full_organization_flow.return_value = {"ok": 1}
    orchestrator.maintain_integrity.return_value = {"removed": 0}
    orchestrator.bulk_transcode.return_value = {"converted": 0}

    progress_cb = MagicMock()
    cancel_event = MagicMock()

    scan_result = execute_core_workflow(
        orchestrator,
        "scan",
        dry_run=True,
        progress_cb=progress_cb,
        cancel_event=cancel_event,
    )
    organize_result = execute_core_workflow(
        orchestrator,
        "organize",
        dry_run=True,
        progress_cb=progress_cb,
    )
    maintain_result = execute_core_workflow(
        orchestrator,
        "maintain",
        dry_run=True,
        progress_cb=progress_cb,
    )
    transcode_result = execute_core_workflow(
        orchestrator,
        "transcode",
        dry_run=True,
        progress_cb=progress_cb,
    )

    assert scan_result == {"count": 1}
    assert organize_result == {"ok": 1}
    assert maintain_result == {"removed": 0}
    assert transcode_result == {"converted": 0}

    orchestrator.scan_library.assert_called_once_with(
        progress_cb=progress_cb,
        cancel_event=cancel_event,
    )
    orchestrator.full_organization_flow.assert_called_once_with(
        dry_run=True,
        progress_cb=progress_cb,
    )
    orchestrator.maintain_integrity.assert_called_once_with(dry_run=True)
    orchestrator.bulk_transcode.assert_called_once_with(
        dry_run=True,
        progress_cb=progress_cb,
    )
