#!/usr/bin/env python3
"""
Manager module

Provides the small CLI-like API that was previously `scripts/emumanager.py`.
This module lives inside the `emumanager` package so it can be imported
reliably by other modules/tests.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import List, Optional

from . import architect
from .config import BASE_DEFAULT, EXT_TO_SYSTEM
from .logging_cfg import get_logger
from .switch import cli as switch_cli


def guess_system_for_file(path: Path) -> Optional[str]:
    ext = path.suffix.lower()
    return EXT_TO_SYSTEM.get(ext)


def cmd_init(base_dir: Path, dry_run: bool) -> int:
    logger = get_logger("manager")
    logger.info("Calling init on %s (dry=%s)", base_dir, dry_run)
    args: List[str] = [str(base_dir)]
    if dry_run:
        args.append("--dry-run")
    return architect.main(args)


def cmd_list_systems(base_dir: Path):
    logger = get_logger("manager")
    roms = base_dir / "roms"
    if not roms.exists():
        logger.debug("No roms directory at %s", roms)
        return []
    systems = sorted([p.name for p in roms.iterdir() if p.is_dir()])
    logger.debug("Found systems: %s", systems)
    return systems


def cmd_add_rom(src: Path, base_dir: Path, system: Optional[str], move: bool = False, dry_run: bool = False) -> Path:
    logger = get_logger("manager")
    if not src.exists():
        logger.error("Source not found: %s", src)
        raise FileNotFoundError(src)

    target_sys = system or guess_system_for_file(src)
    if not target_sys:
        logger.error("Unable to guess system for file: %s", src)
        raise ValueError("Unable to guess system for file; please pass --system")

    dest_dir = base_dir / "roms" / target_sys
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / src.name
    logger.info("Adding ROM %s -> %s (move=%s dry=%s)", src, dest, move, dry_run)
    if dry_run:
        return dest

    if move:
        shutil.move(str(src), str(dest))
    else:
        shutil.copy2(str(src), str(dest))

    return dest


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="emumanager", description="Manage emulation collection")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", help="Create standard folder structure")
    sp.add_argument("base_dir", nargs="?", default=BASE_DEFAULT)
    sp.add_argument("--dry-run", action="store_true")

    sp = sub.add_parser("list-systems", help="List configured systems (folders under roms)")
    sp.add_argument("base_dir", nargs="?", default=BASE_DEFAULT)

    sp = sub.add_parser("add-rom", help="Add a ROM file to the collection")
    sp.add_argument("src", help="Path to ROM file")
    sp.add_argument("base_dir", nargs="?", default=BASE_DEFAULT)
    sp.add_argument("--system", help="Target system folder (e.g. nes, snes)")
    sp.add_argument("--move", action="store_true", help="Move file instead of copying")
    sp.add_argument("--dry-run", action="store_true")

    sp = sub.add_parser("switch", help="Manage Switch ROMs (organize, compress, verify)", add_help=False)
    sp.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to switch organizer")

    return p.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    
    if args.cmd == "init":
        return cmd_init(Path(args.base_dir), args.dry_run)
    elif args.cmd == "list-systems":
        systems = cmd_list_systems(Path(args.base_dir))
        print("\n".join(systems))
        return 0
    elif args.cmd == "add-rom":
        try:
            cmd_add_rom(Path(args.src), Path(args.base_dir), args.system, args.move, args.dry_run)
            return 0
        except Exception as e:
            print(f"Error: {e}")
            return 1
    elif args.cmd == "switch":
        # Delegate to switch module
        # We need to reconstruct argv for switch_cli
        # args.args contains the remainder
        return switch_cli.main(args.args)
        
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
