from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any, List, Optional


def _setup_quarantine(args: Any, roms_dir: Path, logger) -> Optional[Path]:
    if not getattr(args, "quarantine", False):
        return None

    qdir = getattr(args, "quarantine_dir", None)
    if qdir:
        quarantine_dir = Path(qdir).resolve()
    else:
        quarantine_dir = Path(roms_dir) / "_QUARANTINE"
    try:
        if not getattr(args, "dry_run", False):
            quarantine_dir.mkdir(parents=True, exist_ok=True)
        return quarantine_dir
    except Exception as e:
        logger.exception("Could not create quarantine dir %s: %s", quarantine_dir, e)
        return None


def _check_file_health(
    f: Path, args: Any, verify_integrity: callable, scan_for_virus: callable
) -> tuple[bool, str, bool | None, str]:
    try:
        ok, verify_out = verify_integrity(
            f, deep=getattr(args, "deep_verify", False), return_output=True
        )
    except Exception as e:
        ok = False
        verify_out = str(e)

    av_result, av_out = scan_for_virus(f)
    return ok, verify_out, av_result, av_out


def _handle_quarantine(
    f: Path,
    integrity_status: str,
    av_status: str,
    quarantine_dir: Optional[Path],
    args: Any,
    safe_move: callable,
    logger,
) -> str:
    if not quarantine_dir or getattr(args, "dry_run", False):
        return ""

    if integrity_status == "OK" and av_status != "INFECTED":
        return ""

    try:
        dest = quarantine_dir / f.name
        moved = safe_move(f, dest)
        return "QUARANTINED" if moved else "QUARANTINE_FAIL"
    except Exception:
        logger.exception("failed to move to quarantine: %s", f)
        return "QUARANTINE_ERROR"


def _scan_files(
    all_files: List[Path],
    args: Any,
    quarantine_dir: Optional[Path],
    verify_integrity: callable,
    scan_for_virus: callable,
    safe_move: callable,
    logger,
) -> tuple:
    corrupted = []
    infected = []
    unknown_av = []
    report_rows = []

    total = len(all_files)
    progress_cb = getattr(args, "progress_callback", None)
    cancel_event = getattr(args, "cancel_event", None)

    for i, f in enumerate(all_files):
        if cancel_event and cancel_event.is_set():
            logger.warning("Operation cancelled by user.")
            break

        if progress_cb:
            progress_cb(i / total, f"Checking {f.name}...")

        ok, verify_out, av_result, av_out = _check_file_health(
            f, args, verify_integrity, scan_for_virus
        )

        if not ok:
            corrupted.append(f)
            integrity_status = "CORRUPT"
        else:
            integrity_status = "OK"

        if av_result is True:
            infected.append((f, av_out))
            av_status = "INFECTED"
        elif av_result is False:
            av_status = "CLEAN"
        else:
            unknown_av.append((f, av_out))
            av_status = "UNKNOWN"

        action_taken = _handle_quarantine(
            f,
            integrity_status,
            av_status,
            quarantine_dir,
            args,
            safe_move,
            logger,
        )

        report_rows.append(
            [
                str(f),
                integrity_status,
                (verify_out or "")[:10000],
                av_status,
                (av_out or "")[:10000],
                action_taken,
            ]
        )

    return corrupted, infected, unknown_av, report_rows


def _print_health_summary(
    total_files: int,
    corrupted: list,
    infected: list,
    unknown_av: list,
    problems: bool,
):
    print("\nHealth Check Result:")
    print(f"Total files scanned: {total_files}")
    print(f"Corrupted/failed integrity: {len(corrupted)}")
    if corrupted:
        for c in corrupted:
            print(f" - {c}")
    print(f"Infected (AV): {len(infected)}")
    if infected:
        for inf, out in infected:
            print(f" - {inf} -> {out.splitlines()[0] if out else ''}")
    if unknown_av:
        print(f"Files with AV unknown/error: {len(unknown_av)} (no scanner or error)")

    if problems:
        print("Health check found issues. See report (if provided) or console output.")
    else:
        print("All clear: no corruption or infections found (or AV not available).")


def _write_health_csv(csv_path: str, report_rows: list, logger):
    if not csv_path:
        return
    try:
        with open(csv_path, "w", newline="", encoding="utf-8") as rf:
            rw = csv.writer(rf)
            rw.writerow(
                [
                    "path",
                    "integrity",
                    "integrity_output",
                    "av_status",
                    "av_output",
                    "action",
                ]
            )
            rw.writerows(report_rows)
        print(f"Report saved to: {csv_path}")
    except Exception:
        logger.exception("Failed to write report CSV %s", csv_path)


def run_health_check(
    all_files: List[Path],
    args: Any,
    roms_dir: Path,
    verify_integrity: callable,
    scan_for_virus: callable,
    safe_move: callable,
    logger,
) -> dict:
    """Run health check (integrity + AV) and return a summary dict."""
    logger.info("Iniciando Health Check: integridade + antivírus")

    quarantine_dir = _setup_quarantine(args, roms_dir, logger)

    corrupted, infected, unknown_av, report_rows = _scan_files(
        all_files,
        args,
        quarantine_dir,
        verify_integrity,
        scan_for_virus,
        safe_move,
        logger,
    )

    problems = bool(corrupted or infected)

    _print_health_summary(len(all_files), corrupted, infected, unknown_av, problems)
    _write_health_csv(getattr(args, "report_csv", None), report_rows, logger)

    if getattr(args, "progress_callback", None):
        getattr(args, "progress_callback")(1.0, "Health Check complete")

    return {
        "corrupted": corrupted,
        "infected": infected,
        "unknown_av": unknown_av,
        "report_rows": report_rows,
        "problems": problems,
    }


def configure_environment(args: Any, logger: Any, find_tool: callable) -> dict:
    """Configure and detect environment variables and tools.

    Returns a dict with keys: ROMS_DIR, KEYS_PATH, DUPE_DIR, CSV_FILE,
    TOOL_NSTOOL, TOOL_HACTOOL, TOOL_NSZ, TOOL_CLAMSCAN, TOOL_CLAMDSCAN,
    TOOL_METADATA, IS_NSTOOL, ENGINE_NAME
    """
    roms_dir = Path(args.dir).resolve()
    keys_path = Path(args.keys).resolve()
    dupe_dir = roms_dir / "_DUPLICATES"
    csv_file = roms_dir / "biblioteca_switch.csv"

    tool_nstool = find_tool("nstool")
    tool_hactool = find_tool("hactool")
    tool_nsz = find_tool("nsz")
    tool_clamscan = find_tool("clamscan")
    tool_clamdscan = find_tool("clamdscan")

    tool_metadata = None
    is_nstool = False
    engine_name = None
    if tool_nstool:
        tool_metadata = tool_nstool
        is_nstool = True
        engine_name = "nstool"
    elif tool_hactool:
        tool_metadata = tool_hactool
        is_nstool = False
        engine_name = "hactool"
    else:
        logger.error("❌ ERRO CRÍTICO: Ferramentas de leitura não encontradas!")
        logger.error("Por favor, instale 'nstool' ou coloque o executável nesta pasta.")
        raise RuntimeError("Ferramentas de leitura não encontradas (nstool/hactool)")

    if (
        getattr(args, "compress", False) or getattr(args, "decompress", False)
    ) and not tool_nsz:
        logger.error("❌ ERRO: Ferramenta de compressão 'nsz' não encontrada!")
        logger.error("Instale com: pip install nsz")
        raise RuntimeError("Ferramenta de compressão 'nsz' não encontrada")

    return {
        "ROMS_DIR": roms_dir,
        "KEYS_PATH": keys_path,
        "DUPE_DIR": dupe_dir,
        "CSV_FILE": csv_file,
        "TOOL_NSTOOL": tool_nstool,
        "TOOL_HACTOOL": tool_hactool,
        "TOOL_NSZ": tool_nsz,
        "TOOL_CLAMSCAN": tool_clamscan,
        "TOOL_CLAMDSCAN": tool_clamdscan,
        "TOOL_METADATA": tool_metadata,
        "IS_NSTOOL": is_nstool,
        "ENGINE_NAME": engine_name,
    }


def build_new_filename(
    clean_name: str,
    tid: str,
    ver: str,
    suffix: str,
    region: Optional[str] = None,
) -> str:
    name = f"{clean_name} [{tid}]"
    if region:
        name = f"{name} ({region})"
    if ver:
        name = f"{name} ({ver})"
    return name + suffix


def get_dest_folder(roms_dir: Path, region: str) -> Path:
    # Current behavior: simple region-based folder name with truncation
    folder_name = f"{region}"
    if len(folder_name) > 200:
        folder_name = folder_name[:200].rstrip()
    return roms_dir / folder_name


def make_catalog_entry(
    clean_name: str, meta: dict, suffix: str, target_path: Path, region: str
) -> List[Any]:
    return [
        clean_name,
        meta["id"],
        meta["type"],
        meta["ver"],
        region,
        meta["langs"],
        suffix,
        str(target_path),
    ]


def process_one_file(fpath: Path, ctx: dict):
    """Process a single file and return (catalog_row or None, status).

    status: 'ok', 'skipped', 'error'
    This is a top-level helper to allow unit testing and reuse.
    """
    get_metadata = ctx.get("get_metadata")
    sanitize_name = ctx.get("sanitize_name")
    determine_region = ctx.get("determine_region")
    handle_compression = ctx.get("handle_compression")
    safe_move = ctx.get("safe_move")
    roms_dir = ctx.get("ROMS_DIR")
    logger = ctx.get("logger")

    try:
        meta = get_metadata(fpath)
        if not meta or not meta.get("id"):
            reason = "TitleID não encontrado"
            if fpath.suffix.lower() == ".nsz":
                reason += "; arquivo comprimido (.nsz) — tente usar --decompress"
            logger.warning(
                "Metadados ausentes para %s: %s. Arquivo: %s",
                fpath.name,
                reason,
                fpath,
            )
            return None, "error"

        clean_name = sanitize_name(meta.get("name") or fpath.name)
        region = determine_region(fpath.name, meta.get("langs"))

        fpath2 = handle_compression(fpath)

        args = ctx.get("args")
        standardize = getattr(args, "standardize_names", False)
        new_fname = build_new_filename(
            clean_name,
            meta.get("id"),
            meta.get("ver"),
            fpath2.suffix,
            region if standardize else None,
        )
        dest_folder = get_dest_folder(roms_dir, region)
        target_path = dest_folder / new_fname

        if fpath2 != target_path:
            moved = safe_move(fpath2, target_path)
            if moved:
                return make_catalog_entry(
                    clean_name, meta, fpath2.suffix, target_path, region
                ), "ok"
            else:
                return None, "skipped"
        else:
            return make_catalog_entry(
                clean_name, meta, fpath2.suffix, target_path, region
            ), "ok"
    except Exception:
        logger.exception("Error while processing file %s", fpath)
        return None, "error"


def _update_progress(progress_cb, current, total, filename):
    if progress_cb:
        try:
            progress_cb(
                float(current) / max(1, total),
                f"Processing {current}/{total}: {filename}",
            )
        except Exception:
            pass


def process_files(files: List[Path], ctx: dict):
    """Process the list of files using a single context dict.

    ctx is expected to provide the following keys (mirrors previous args):
      args, ROMS_DIR, CSV_FILE, get_metadata, sanitize_name, determine_region,
      determine_type, parse_languages, detect_languages_from_filename,
      safe_move, verify_integrity, scan_for_virus, handle_compression,
      TOOL_METADATA, IS_NSTOOL, logger, Col, TITLE_ID_RE
      progress_callback (optional): function(percent: float, msg: str)

    Returns (catalog, stats).
    """
    # ctx is provided to the inner helper; process_files itself only orchestrates
    # to keep complexity low we avoid caching ctx locals here.

    catalog = []
    stats = {"ok": 0, "erro": 0, "skipped": 0}
    progress_cb = ctx.get("progress_callback")
    cancel_event = ctx.get("cancel_event")
    total = len(files)
    logger = ctx.get("logger")

    # use module-level helpers: build_new_filename, get_dest_folder, make_catalog_entry

    # process_one_file is implemented at module level for re-use and testing

    for i, fpath in enumerate(files, 1):
        if cancel_event and cancel_event.is_set():
            if logger:
                logger.warning("Operation cancelled by user.")
            break

        _update_progress(progress_cb, i, total, fpath.name)

        row, status = process_one_file(fpath, ctx)
        stats[status] = stats.get(status, 0) + 1
        if status == "ok" and row:
            catalog.append(row)

    if progress_cb:
        progress_cb(1.0, "Organization complete")

    return catalog, stats
