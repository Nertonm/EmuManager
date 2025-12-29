from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class VerifyResult:
    filename: str
    status: str  # "VERIFIED", "UNKNOWN", "MISMATCH"
    match_name: Optional[str]
    crc: Optional[str]
    sha1: Optional[str]
    md5: Optional[str] = None
    sha256: Optional[str] = None
    full_path: Optional[str] = None
    dat_name: Optional[str] = None


@dataclass
class VerifyReport:
    text: str
    results: List[VerifyResult] = field(default_factory=list)
