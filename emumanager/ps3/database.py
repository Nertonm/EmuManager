import csv
from pathlib import Path
from typing import Optional


class PS3Database:
    def __init__(self):
        self.data = {}

    def load_from_csv(self, csv_path: Path):
        if not csv_path.exists():
            return

        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2:
                        serial = row[0].strip().upper().replace("-", "")
                        title = row[1].strip()
                        self.data[serial] = title
        except Exception:
            pass

    def get_title(self, serial: str) -> Optional[str]:
        if not serial:
            return None
        return self.data.get(serial.upper().replace("-", ""))


db = PS3Database()
