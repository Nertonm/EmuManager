from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Callable, Optional

from emumanager.library import DuplicateGroup, LibraryDB
from emumanager.logging_cfg import log_call, set_correlation_id


def _is_canceled(cancel_event: Any) -> bool:
    return bool(cancel_event and getattr(cancel_event, "is_set", lambda: False)())


def _gather_duplicate_groups(
    db: LibraryDB,
    hash_prefer: tuple[str, ...],
    include_name: bool,
    progress_cb: Optional[Callable[[float, str], None]],
    log_cb: Optional[Callable[[str], None]],
    cancel_event: Any,
) -> list[DuplicateGroup]:
    groups: list[DuplicateGroup] = []

    # 1. Hash-based
    if progress_cb:
        progress_cb(10.0, "Checking hash duplicates...")
    try:
        groups.extend(db.find_duplicates_by_hash(prefer=hash_prefer))
    except Exception as e:
        if log_cb:
            log_cb(f"Duplicate scan (hash) failed: {e}")

    if _is_canceled(cancel_event):
        return []

    # 2. Name-based
    if include_name:
        if progress_cb:
            progress_cb(60.0, "Checking name duplicates...")
        try:
            groups.extend(db.find_duplicates_by_normalized_name())
        except Exception as e:
            if log_cb:
                log_cb(f"Duplicate scan (name) failed: {e}")

    return groups


def _serialize_groups(groups: list[DuplicateGroup]) -> list[dict[str, Any]]:
    return [
        {
            "key": g.key,
            "kind": g.kind,
            "count": g.count,
            "wasted_bytes": g.wasted_bytes,
            "entries": [asdict(e) for e in g.entries],
        }
        for g in groups
    ]


@log_call(level=logging.INFO)
def worker_find_duplicates(
    db: LibraryDB,
    log_cb: Optional[Callable[[str], None]] = None,
    progress_cb: Optional[Callable[[float, str], None]] = None,
    cancel_event: Any = None,
    include_name: bool = True,
    filter_non_games: bool = True,
    hash_prefer: tuple[str, ...] = ("sha1", "md5", "crc32"),
) -> dict[str, Any]:
    """Find duplicates groups using the LibraryDB."""
    set_correlation_id()

    if progress_cb:
        progress_cb(0.0, "Scanning duplicates...")

    if _is_canceled(cancel_event):
        return {"groups": [], "total_groups": 0, "total_items": 0, "wasted_bytes": 0}

    groups = _gather_duplicate_groups(
        db, hash_prefer, include_name, progress_cb, log_cb, cancel_event
    )

    if not groups and _is_canceled(cancel_event):
        return {"groups": [], "total_groups": 0, "total_items": 0, "wasted_bytes": 0}

    # Summary and Serialization
    total_groups = len(groups)
    total_items = sum(g.count for g in groups)
    wasted_bytes = sum(g.wasted_bytes for g in groups)
    serial_groups = _serialize_groups(groups)

    if progress_cb:
        progress_cb(100.0, f"Found {total_groups} duplicate groups")

    return {
        "groups": serial_groups,
        "total_groups": total_groups,
        "total_items": total_items,
        "wasted_bytes": wasted_bytes,
    }
