import csv
from pathlib import Path
from typing import Dict, Optional


class PS2Database:
    def __init__(self):
        self._db: Dict[str, str] = {}

    def load_from_csv(self, csv_path: Path):
        """
        Loads game database from a CSV file.
        Expected format: Serial,Title (header optional if columns are detected)
        """
        if not csv_path.exists():
            return

        try:
            with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2:
                        serial = (
                            row[0].strip().upper().replace("_", "-").replace(".", "")
                        )
                        # Normalize serial to XXXX-YYYYY
                        if len(serial) == 9 and serial[4] != "-":
                            serial = serial[:4] + "-" + serial[4:]

                        title = row[1].strip()
                        self._db[serial] = title
        except Exception:
            pass

    def get_title(self, serial: str) -> Optional[str]:
        # Serial expected in XXXX-YYYYY format
        return self._db.get(serial)


# Global instance
db = PS2Database()
