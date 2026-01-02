"""Small example script to run DAT verify across multiple systems and write CSV.

This script is intentionally lightweight and reuses the core worker (worker_hash_verify)
so it will run in the same virtualenv as the project.

Usage:
    python scripts/verify_batch.py --base /path/to/library --dats /path/to/dats --out report.csv

It enumerates systems via manager.cmd_list_systems(base), runs verification for each,
and writes a CSV with columns: system,file,status,match,crc,sha1,md5,dat_name
"""
from __future__ import annotations

import argparse
import csv
import threading
from pathlib import Path
from typing import Optional

from emumanager import manager
from emumanager.workers.verification import worker_hash_verify


def run_verify_for_system(base: Path, system: str, dats_root: Path) -> Optional[object]:
    roms_path = base / "roms"
    candidate1 = roms_path / system
    candidate2 = base / system
    target = candidate1 if candidate1.exists() else candidate2
    if not target.exists():
        print(f"Skipping missing system path: {target}")
        return None

    args = type("A", (), {})()
    args.dat_path = None
    args.dats_roots = [dats_root]
    args.progress_callback = lambda p, m: None
    args.cancel_event = threading.Event()

    report = worker_hash_verify(
        target,
        args,
        lambda m: print(m),
        lambda p: [p for p in target.rglob("*") if p.is_file()],
    )
    return report


def write_csv(report, system: str, out_path: Path):
    with out_path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in report.results:
            w.writerow(
                [
                    system,
                    r.filename,
                    r.status,
                    r.match_name,
                    r.crc,
                    r.sha1,
                    r.md5,
                    r.dat_name,
                    r.full_path,
                ]
            )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True, type=Path, help="Base da biblioteca")
    p.add_argument("--dats", required=True, type=Path, help="Pasta contendo DATs")
    p.add_argument("--out", required=True, type=Path, help="CSV de saída")

    args = p.parse_args()

    base: Path = args.base
    dats: Path = args.dats
    out: Path = args.out

    systems = manager.cmd_list_systems(base)
    if not systems:
        print("Nenhum sistema detectado")
        return

    # Write header
    with out.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(
            [
                "system",
                "file",
                "status",
                "match",
                "crc",
                "sha1",
                "md5",
                "dat_name",
                "full_path",
            ]
        )

    for sys in systems:
        print(f"Running verify for system: {sys}")
        rep = run_verify_for_system(base, sys, dats)
        if not rep:
            continue
        write_csv(rep, sys, out)
        print(f"Wrote {len(rep.results)} rows for {sys}")


if __name__ == "__main__":
    main()
