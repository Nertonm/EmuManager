#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, List, Optional

from emumanager.common.execution import cancel_current_process, find_tool, run_cmd
from emumanager.logging_cfg import Col, configure_logging, get_fileops_logger, get_logger
from emumanager.switch import meta_parser, metadata
from emumanager.switch.cli_args import (
    COMPRESSION_PROFILE_LEVELS,
    build_parser,
    show_banner,
    show_manual,
)
from emumanager.switch.cli_operations import (
    detect_nsz_level_impl,
    get_metadata_impl,
    handle_compression_impl,
    safe_move_impl,
    scan_for_virus_impl,
    verify_integrity_impl,
)
from emumanager.switch.cli_runtime import (
    apply_cli_settings,
    build_processing_context,
    discover_switch_files,
    finalize_main,
    perform_clean_junk,
)
from emumanager.switch.main_helpers import configure_environment, process_files, run_health_check
from emumanager.verification.hasher import get_file_hash

# Keep original reference so test monkeypatches can be detected by execution helpers.
ORIGINAL_SUBPROCESS_RUN = subprocess.run

parser = build_parser()

logger = logging.getLogger("organizer_v13")
SHUTDOWN_REQUESTED = False
args: Any = None

parse_languages = metadata.parse_languages
detect_languages_from_filename = metadata.detect_languages_from_filename
determine_type = metadata.determine_type
determine_region = metadata.determine_region
get_base_id = metadata.get_base_id
sanitize_name = metadata.sanitize_name

TITLE_ID_RE = re.compile(
    r"(?:Title ID|Program Id):\s*(?:0x)?([0-9A-F]{16})",
    re.IGNORECASE,
)
INVALID_FILENAME_CHARS_RE = re.compile(r'[<>:"/\\|?*]')
__all__ = [
    "COMPRESSION_PROFILE_LEVELS",
    "INVALID_FILENAME_CHARS_RE",
    "ORIGINAL_SUBPROCESS_RUN",
    "TITLE_ID_RE",
    "args",
    "configure_environment",
    "detect_languages_from_filename",
    "detect_nsz_level",
    "determine_region",
    "determine_type",
    "find_tool",
    "get_base_id",
    "get_file_hash",
    "get_metadata",
    "handle_compression",
    "main",
    "parse_languages",
    "parser",
    "safe_move",
    "sanitize_name",
    "scan_for_virus",
    "setup_logging",
    "show_banner",
    "show_manual",
    "verify_integrity",
]


def setup_logging(
    logfile: str,
    verbose: bool = False,
    max_bytes: int = 5 * 1024 * 1024,
    backups: int = 3,
    base_dir: Optional[Path] = None,
) -> None:
    """Configure logging using the shared logging configuration."""
    try:
        if logfile:
            logfile_path = Path(logfile)
            if not logfile_path.is_absolute():
                target_dir = Path(base_dir) if base_dir else Path.cwd()
                logfile_path = target_dir / logfile_path
            os.environ["EMUMANAGER_LOG_FILE"] = str(logfile_path)
    except Exception:
        pass

    if verbose:
        os.environ.setdefault("EMUMANAGER_LOG_LEVEL", str(logging.DEBUG))

    configure_logging(
        base_dir=Path(base_dir) if base_dir else None,
        level=logging.DEBUG if verbose else logging.INFO,
        max_bytes=max_bytes,
        backup_count=backups,
    )

    global logger
    logger = get_logger("organizer_v13", base_dir=Path(base_dir) if base_dir else None)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)


def _signal_handler(signum, frame):
    del frame
    global SHUTDOWN_REQUESTED
    logger.warning("Signal %s received: requesting shutdown...", signum)
    SHUTDOWN_REQUESTED = True
    cancel_current_process()


def get_metadata(
    filepath,
    *,
    tool_metadata,
    is_nstool,
    keys_path,
    roms_dir,
    cmd_timeout,
    tool_nsz,
):
    return get_metadata_impl(
        filepath,
        tool_metadata=tool_metadata,
        is_nstool=is_nstool,
        keys_path=keys_path,
        roms_dir=roms_dir,
        cmd_timeout=cmd_timeout,
        tool_nsz=tool_nsz,
        run_cmd_fn=run_cmd,
        parse_tool_output_fn=meta_parser.parse_tool_output,
        parse_languages_fn=parse_languages,
        detect_languages_from_filename_fn=detect_languages_from_filename,
        determine_type_fn=determine_type,
    )


def verify_integrity(
    filepath,
    *,
    deep: bool = False,
    return_output: bool = False,
    tool_nsz,
    roms_dir,
    cmd_timeout,
    tool_metadata,
    is_nstool,
    keys_path,
    tool_hactool,
):
    return verify_integrity_impl(
        filepath,
        deep=deep,
        return_output=return_output,
        tool_nsz=tool_nsz,
        roms_dir=roms_dir,
        cmd_timeout=cmd_timeout,
        tool_metadata=tool_metadata,
        is_nstool=is_nstool,
        keys_path=keys_path,
        tool_hactool=tool_hactool,
        run_cmd_fn=run_cmd,
        logger=logger,
    )


def scan_for_virus(filepath, *, tool_clamscan, tool_clamdscan, roms_dir, cmd_timeout):
    return scan_for_virus_impl(
        filepath,
        tool_clamscan=tool_clamscan,
        tool_clamdscan=tool_clamdscan,
        roms_dir=roms_dir,
        cmd_timeout=cmd_timeout,
        run_cmd_fn=run_cmd,
        logger=logger,
    )


def detect_nsz_level(filepath, *, tool_nsz, roms_dir, cmd_timeout) -> Optional[int]:
    return detect_nsz_level_impl(
        filepath,
        tool_nsz=tool_nsz,
        roms_dir=roms_dir,
        cmd_timeout=cmd_timeout,
        run_cmd_fn=run_cmd,
        logger=logger,
    )


def handle_compression(
    filepath,
    *,
    args,
    tool_nsz,
    roms_dir,
    tool_metadata,
    is_nstool,
    keys_path,
    cmd_timeout,
    tool_hactool,
):
    return handle_compression_impl(
        filepath,
        args=args,
        tool_nsz=tool_nsz,
        roms_dir=roms_dir,
        tool_metadata=tool_metadata,
        is_nstool=is_nstool,
        keys_path=keys_path,
        cmd_timeout=cmd_timeout,
        tool_hactool=tool_hactool,
        run_cmd_fn=run_cmd,
        logger=logger,
        col=Col,
        tempfile_module=tempfile,
        shutil_module=shutil,
        verify_integrity_fn=verify_integrity,
        detect_nsz_level_fn=detect_nsz_level,
    )


def safe_move(source, dest, *, args, logger):
    return safe_move_impl(
        source,
        dest,
        args=args,
        logger=logger,
        get_file_hash_fn=get_file_hash,
        get_fileops_logger_fn=get_fileops_logger,
        shutil_module=shutil,
    )


def print_progress(current, total, filename):
    percent = 100 * (current / float(total))
    bar = "█" * int(30 * current // total) + "-" * (30 - int(30 * current // total))
    sys.stdout.write(f"\r{Col.CYAN}[{bar}] {percent:.1f}%{Col.RESET} | {filename[:25]}..")
    sys.stdout.flush()


def _apply_cli_settings(parsed_args):
    return apply_cli_settings(
        parsed_args,
        logger=logger,
        compression_profile_levels=COMPRESSION_PROFILE_LEVELS,
        signal_handler=_signal_handler,
        signal_module=signal,
        sys_module=sys,
    )


def _prepare_ctx(parsed_args, env):
    return build_processing_context(
        parsed_args,
        env,
        verify_integrity_fn=verify_integrity,
        scan_for_virus_fn=scan_for_virus,
        safe_move_fn=safe_move,
        get_metadata_fn=get_metadata,
        handle_compression_fn=handle_compression,
        sanitize_name_fn=sanitize_name,
        determine_region_fn=determine_region,
        determine_type_fn=determine_type,
        parse_languages_fn=parse_languages,
        detect_languages_from_filename_fn=detect_languages_from_filename,
        logger=logger,
        color=Col,
        title_id_re=TITLE_ID_RE,
    )


def _perform_clean_junk(roms_dir):
    perform_clean_junk(roms_dir, logger=logger)


def _finalize_main(parsed_args, catalog, stats, roms_dir, csv_file):
    finalize_main(
        parsed_args,
        catalog,
        stats,
        roms_dir,
        csv_file,
        logger=logger,
        color=Col,
        cleanup_junk_fn=_perform_clean_junk,
    )


def main(argv: Optional[List[str]] = None):
    global args
    args = parser.parse_args(argv)
    _apply_cli_settings(args)

    base_dir = Path(args.dir).resolve()
    setup_logging(
        args.log_file,
        args.verbose,
        args.log_max_bytes,
        args.log_backups,
        base_dir=base_dir,
    )

    env = configure_environment(args, logger, find_tool)
    logger.info("Starting Switch Organizer")
    logger.info("Directory: %s", env["ROMS_DIR"])

    files = discover_switch_files(env["ROMS_DIR"])
    if not files:
        logger.info("Nenhum arquivo .xci/.nsp/.nsz/.xcz encontrado no diretório especificado.")
        return

    ctx = _prepare_ctx(args, env)

    if args.health_check:
        hc_summary = run_health_check(
            files,
            args,
            env["ROMS_DIR"],
            ctx["verify_integrity"],
            ctx["scan_for_virus"],
            ctx["safe_move"],
            logger,
        )
        if not any([args.organize, args.compress, args.decompress, args.clean_junk]):
            sys.exit(1 if hc_summary.get("corrupted") or hc_summary.get("infected") else 0)

    catalog, stats = process_files(files, ctx)
    _finalize_main(args, catalog, stats, env["ROMS_DIR"], env["CSV_FILE"])


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        logger.exception("Unexpected fatal error while running script")
        sys.exit(2)
