import csv
from pathlib import Path
from typing import Optional

class N3DSDatabase:
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
                        # 3DS serials often have dashes, e.g. CTR-P-AGME
                        # We'll store them stripped for consistency if needed, 
                        # but usually they are kept with dashes in DBs.
                        # Let's strip dashes for normalization.
                        serial = row[0].strip().upper().replace("-", "")
                        title = row[1].strip()
                        self.data[serial] = title
        except Exception:
            pass
            
    def clear(self):
        self.data = {}

    def get_title(self, serial: str) -> Optional[str]:
        if not serial:
            return None
        # Normalize input
        s = serial.upper().replace("-", "")
        return self.data.get(s)

db = N3DSDatabase()
