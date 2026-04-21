from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class LibraryEntry:
    path: str
    system: str
    size: int
    mtime: float
    status: str = "UNKNOWN"
    crc32: str | None = None
    md5: str | None = None
    sha1: str | None = None
    sha256: str | None = None
    match_name: str | None = None
    dat_name: str | None = None
    extra_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DuplicateGroup:
    key: str
    kind: str
    entries: list[LibraryEntry]

    @property
    def count(self) -> int:
        return len(self.entries)

    @property
    def wasted_bytes(self) -> int:
        if len(self.entries) <= 1:
            return 0
        sizes = sorted((entry.size for entry in self.entries), reverse=True)
        return sum(sizes[1:])


def normalize_game_name(name: str) -> str:
    """Remove tags and normalize a name for fuzzy duplicate comparison."""
    normalized = Path(name).stem
    normalized = re.sub(r"\([^)]*\)", "", normalized)
    normalized = re.sub(r"\[[^]]*\]", "", normalized)
    normalized = re.sub(r"\{[^}]*\}", "", normalized)
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9 ]", " ", normalized)
    return " ".join(normalized.split())
