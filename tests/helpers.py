from dataclasses import dataclass
from typing import Optional


@dataclass
class Args:
    compress: bool = False
    recompress: bool = False
    dry_run: bool = False
    level: int = 3
    quarantine: bool = False
    quarantine_dir: Optional[str] = None
    cmd_timeout: Optional[int] = None
    keep_on_failure: bool = False
