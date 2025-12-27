import csv
from pathlib import Path
from typing import Dict, Optional


class WiiDatabase:
    def __init__(self):
        self._db: Dict[str, str] = {}

    def load_from_csv(self, csv_path: Path):
        """
        Loads game database from a CSV file.
        Expected format: GameID,Title
        """
        if not csv_path.exists():
            return

        try:
            with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2:
                        game_id = row[0].strip().upper()
                        title = row[1].strip()
                        if len(game_id) == 6:
                            self._db[game_id] = title
        except Exception:
            pass

    def get_title(self, game_id: str) -> Optional[str]:
        return self._db.get(game_id.upper())


# Global instance
db = WiiDatabase()
