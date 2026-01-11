from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class VerifyResult:
    filename: str
    status: str  # "VERIFIED", "UNKNOWN", "MISMATCH"
    match_name: str | None = None
    crc: str | None = None
    sha1: str | None = None
    md5: str | None = None
    sha256: str | None = None
    full_path: str | None = None
    dat_name: str | None = None


@dataclass(slots=True)
class VerifyReport:
    text: str
    results: list[VerifyResult] = field(default_factory=list)