#!/usr/bin/env python3
"""
PS2 CSO -> CHD converter

Clean, single canonical implementation. Provides a programmatic API and a CLI.
"""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Callable

__all__ = ["convert_directory"]

from ..logging_cfg import get_logger, Col
from ..common.execution import find_tool, run_cmd

logger = get_logger("ps2_converter")


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    handler.setFormatter(fmt)
    logger.setLevel(level)
    logger.handlers.clear()
    logger.addHandler(handler)


@dataclass
class ConversionResult:
    cso: Path
    iso: Optional[Path]
    chd: Optional[Path]
    success: bool
    message: str


def _decompress_to_iso(cso_path: Path, iso_path: Path, maxcso: Path, dry_run: bool, timeout: int) -> bool:
    logger.info("Decompressing %s -> %s", cso_path.name, iso_path.name)
    if dry_run:
        return True
    run_cmd([str(maxcso), "--decompress", str(cso_path), "-o", str(iso_path)], timeout=timeout, check=True)
    return iso_path.exists()


def _convert_iso_to_chd(iso_path: Path, chd_path: Path, chdman: Path, dry_run: bool, timeout: int) -> bool:
    logger.info("Converting %s -> %s", iso_path.name, chd_path.name)
    if dry_run:
        return True
    run_cmd([str(chdman), "createdvd", "-i", str(iso_path), "-o", str(chd_path)], timeout=timeout, check=True)
    return chd_path.exists()


def _finalize_cleanup(cso_path: Path, iso_path: Path, chd_path: Path, backup_dir: Path, dry_run: bool, remove_original: bool) -> None:
    logger.info("Finalizing (backup=%s remove=%s)", backup_dir, remove_original)
    if dry_run:
        return
    try:
        try:
            iso_path.unlink(missing_ok=True)
        except TypeError:
            if iso_path.exists():
                iso_path.unlink()
    except Exception:
        logger.debug("Failed to remove ISO %s", iso_path)

    if remove_original:
        try:
            cso_path.unlink()
        except Exception:
            logger.debug("Failed to remove original CSO %s", cso_path)
    else:
        backup_dir.mkdir(parents=True, exist_ok=True)
        try:
            cso_path.rename(backup_dir / cso_path.name)
        except Exception:
            logger.debug("Failed to move original CSO %s to %s", cso_path, backup_dir)


def convert_file(
    cso_path: Path,
    maxcso: Path,
    chdman: Path,
    backup_dir: Path,
    dry_run: bool = False,
    timeout: int = 3600,
    remove_original: bool = False,
) -> ConversionResult:
    iso_path = cso_path.with_suffix(".iso")
    chd_path = cso_path.with_suffix(".chd")

    if chd_path.exists():
        msg = f"{chd_path.name} already exists, skipping"
        logger.info(Col.YELLOW + msg + Col.RESET)
        return ConversionResult(cso=cso_path, iso=None, chd=chd_path, success=False, message=msg)

    try:
        ok = _decompress_to_iso(cso_path, iso_path, maxcso, dry_run, timeout)
        if not ok:
            msg = "Failed to produce ISO"
            logger.error(Col.RED + "[FAIL] %s" % msg + Col.RESET)
            return ConversionResult(cso=cso_path, iso=iso_path, chd=None, success=False, message=msg)

        ok = _convert_iso_to_chd(iso_path, chd_path, chdman, dry_run, timeout)
        if not ok:
            msg = "Failed to produce CHD"
            logger.error(Col.RED + "[ERROR] %s" % msg + Col.RESET)
            return ConversionResult(cso=cso_path, iso=iso_path, chd=chd_path, success=False, message=msg)

        _finalize_cleanup(cso_path, iso_path, chd_path, backup_dir, dry_run, remove_original)
        return ConversionResult(cso=cso_path, iso=iso_path, chd=chd_path, success=True, message="OK")
    except subprocess.CalledProcessError as exc:
        msg = f"External tool failed: {exc}"
        logger.error(Col.RED + msg + Col.RESET)
        return ConversionResult(cso=cso_path, iso=iso_path, chd=None, success=False, message=msg)
    except Exception as exc:  # pragma: no cover - unexpected
        msg = f"Unexpected error: {exc}"
        logger.exception(msg)
        return ConversionResult(cso=cso_path, iso=iso_path, chd=None, success=False, message=msg)


def convert_directory(
    directory: str | Path = ".",
    dry_run: bool = False,
    backup_dir: str | Path = "_LIXO_CSO",
    timeout: int = 3600,
    verbose: bool = False,
    remove_original: bool = False,
    maxcso: Optional[Path] = None,
    chdman: Optional[Path] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> List[ConversionResult]:
    directory = Path(directory)
    backup_dir = Path(backup_dir)

    if not maxcso:
        maxcso = find_tool("maxcso")
    if not chdman:
        chdman = find_tool("chdman")
    
    if not maxcso:
        raise RuntimeError("'maxcso' not found. Install it (eg. sudo pacman -S maxcso)")
    if not chdman:
        raise RuntimeError("'chdman' not found. Install it (eg. sudo pacman -S mame-tools)")

    results: List[ConversionResult] = []
    files = sorted(directory.glob("*.cso"))
    total = len(files)
    
    for i, p in enumerate(files):
        if progress_callback:
            progress_callback(i / total, f"Converting {p.name}...")
            
        logger.info("--------------------------------------------------")
        logger.info("Processing: %s", p.name)
        res = convert_file(
            p,
            maxcso=maxcso,
            chdman=chdman,
            backup_dir=backup_dir,
            dry_run=dry_run,
            timeout=timeout,
            remove_original=remove_original,
        )
        results.append(res)
        
    if progress_callback:
        progress_callback(1.0, "PS2 Conversion complete")

    logger.info("=== OPERATION COMPLETE ===")
    logger.info("Original CSO files (when converted) are in: %s", str(backup_dir))
    return results


def _main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Convert PS2 CSO files to CHD using maxcso + chdman")
    parser.add_argument("--dir", default=".", help="Directory with .cso files (default: current)")
    parser.add_argument("--backup-dir", default="_LIXO_CSO", help="Where to move original .cso files")
    parser.add_argument("--dry-run", action="store_true", help="Do not execute commands, only simulate")
    parser.add_argument("--timeout", type=int, default=3600, help="Timeout seconds for each external command")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    parser.add_argument(
        "--remove-original",
        action="store_true",
        help="Remove original .cso instead of moving it to backup after successful conversion",
    )
    args = parser.parse_args(argv)

    setup_logging(verbose=args.verbose)

    try:
        convert_directory(
            directory=args.dir,
            dry_run=args.dry_run,
            backup_dir=args.backup_dir,
            timeout=args.timeout,
            verbose=args.verbose,
            remove_original=args.remove_original,
        )
        return 0
    except RuntimeError as e:
        logger.error(str(e))
        return 2
    except Exception as e:
        logger.exception("Unhandled error: %s", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(_main())
