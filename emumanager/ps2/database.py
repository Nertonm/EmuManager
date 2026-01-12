import csv
import os
import sys
from pathlib import Path
from typing import Dict, Optional


class PS2Database:
    def __init__(self):
        self._db: Dict[str, str] = {}
        self._initialized = False

    def _auto_load(self):
        """Tenta carregar a base de dados de locais padrão se ainda não o fez."""
        if self._initialized:
            return
        
        # Ordem de procura:
        # 1. Recurso embutido (PyInstaller _MEIPASS)
        # 2. Pasta do script/executável
        # 3. Diretório de trabalho atual
        
        candidates = []
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            candidates.append(Path(sys._MEIPASS) / "ps2_db.csv")
        
        candidates.append(Path(sys.argv[0]).parent / "ps2_db.csv")
        candidates.append(Path("ps2_db.csv"))
        
        for cand in candidates:
            if cand.exists():
                self.load_from_csv(cand)
                break
        self._initialized = True

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
        self._auto_load()
        return self._db.get(serial)


# Global instance
db = PS2Database()
