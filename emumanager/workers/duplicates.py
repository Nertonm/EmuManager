from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable, Optional

from emumanager.library import DuplicateGroup, LibraryDB


def worker_find_duplicates(
    db: LibraryDB,
    log_cb: Optional[Callable[[str], None]] = None,
    progress_cb: Optional[Callable[[float, str], None]] = None,
    cancel_event: Any = None,
    include_name: bool = True,
    filter_non_games: bool = True,
    hash_prefer: tuple[str, ...] = ("sha1", "md5", "crc32"),
) -> dict[str, Any]:
    """Find duplicates groups using the LibraryDB.

    Contract:
      - returns dict with keys: groups (list), total_groups, total_items, wasted_bytes
      - is cancellation-aware via cancel_event (threading.Event-like)
      - uses optional progress_cb(0..100, text)

    Notes:
      - `groups` are serialized (plain dicts) to make it safe to pass across threads.
    """

    def canceled() -> bool:
        return bool(cancel_event and getattr(cancel_event, "is_set", lambda: False)())

    if progress_cb:
        progress_cb(0.0, "Scanning duplicates...")

    groups: list[DuplicateGroup] = []

    if canceled():
        return {"groups": [], "total_groups": 0, "total_items": 0, "wasted_bytes": 0}

    # Hash-based
    if progress_cb:
        progress_cb(10.0, "Checking hash duplicates...")
    try:
        groups.extend(
            db.find_duplicates_by_hash(
                prefer=hash_prefer, filter_non_games=filter_non_games
            )
        )
    except Exception as e:
        if log_cb:
            log_cb(f"Duplicate scan (hash) failed: {e}")

    if canceled():
        return {"groups": [], "total_groups": 0, "total_items": 0, "wasted_bytes": 0}

    # Name-based
    if include_name:
        if progress_cb:
            progress_cb(60.0, "Checking name duplicates...")
        try:
            groups.extend(
                db.find_duplicates_by_normalized_name(filter_non_games=filter_non_games)
            )
        except Exception as e:
            if log_cb:
                log_cb(f"Duplicate scan (name) failed: {e}")

    # Summary
    total_groups = len(groups)
    total_items = sum(g.count for g in groups)
    wasted_bytes = sum(g.wasted_bytes for g in groups)

    # Serialize
    serial_groups: list[dict[str, Any]] = []
    for g in groups:
        serial_groups.append(
            {
                "key": g.key,
                "kind": g.kind,
                "count": g.count,
                "wasted_bytes": g.wasted_bytes,
                "entries": [asdict(e) for e in g.entries],
            }
        )

    if progress_cb:
        progress_cb(100.0, f"Found {total_groups} duplicate groups")

    return {
        "groups": serial_groups,
        "total_groups": total_groups,
        "total_items": total_items,
        "wasted_bytes": wasted_bytes,
    }
