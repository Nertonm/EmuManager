import csv
from pathlib import Path
from typing import Dict, Optional

class PSXDatabase:
    def __init__(self):
        self._db: Dict[str, str] = {}

    def load_from_csv(self, csv_path: Path):
        """Load game database from CSV: Serial,Title (header optional)."""
        if not csv_path.exists():
            return
        try:
            with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2:
                        serial = row[0].strip().upper().replace("_", "-").replace(".", "")
                        if len(serial) == 9 and serial[4] != "-":
                            serial = serial[:4] + "-" + serial[4:]
                        title = row[1].strip()
                        self._db[serial] = title
        except Exception:
            pass

    def get_title(self, serial: str) -> Optional[str]:
        return self._db.get(serial)

    def clear(self):
        """Clear in-memory mappings (useful for tests or when no DB is provided)."""
        self._db.clear()

# Global instance
db = PSXDatabase()
