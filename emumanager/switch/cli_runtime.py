from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any


SWITCH_FILE_SUFFIXES = {".xci", ".nsp", ".nsz", ".xcz"}


def apply_cli_settings(
    args: Any,
    *,
    logger,
    compression_profile_levels: dict[str, int],
    signal_handler,
    signal_module,
    sys_module,
) -> None:
    try:
        signal_module.signal(signal_module.SIGINT, signal_handler)
        signal_module.signal(signal_module.SIGTERM, signal_handler)
    except Exception as e:
        logger.debug("Could not install signal handlers: %s", e)

    try:
        prof = getattr(args, "compression_profile", None)
        if prof and prof in compression_profile_levels:
            args.level = compression_profile_levels[prof]
            logger.info("Compression profile '%s' selected -> level %s", prof, args.level)
        elif prof:
            logger.warning("Unknown compression profile '%s', keeping --level=%s", prof, args.level)
    except Exception as e:
        logger.exception("Error while applying compression_profile: %s", e)

    try:
        args.level = max(1, min(22, int(args.level)))
    except Exception:
        logger.warning("Invalid compression level; using 1")
        args.level = 1

    if args.compress and args.decompress:
        sys_module.exit("Erro: Escolha --compress OU --decompress.")

    if args.verbose:
        logger.setLevel(logging.DEBUG)


def build_processing_context(
    args: Any,
    env: dict[str, Any],
    *,
    verify_integrity_fn,
    scan_for_virus_fn,
    safe_move_fn,
    get_metadata_fn,
    handle_compression_fn,
    sanitize_name_fn,
    determine_region_fn,
    determine_type_fn,
    parse_languages_fn,
    detect_languages_from_filename_fn,
    logger,
    color,
    title_id_re,
) -> dict[str, Any]:
    roms_dir = env["ROMS_DIR"]
    keys_path = env["KEYS_PATH"]
    tool_metadata = env["TOOL_METADATA"]
    is_nstool = env["IS_NSTOOL"]
    tool_hactool = env["TOOL_HACTOOL"]
    tool_nsz = env["TOOL_NSZ"]
    tool_clamscan = env["TOOL_CLAMSCAN"]
    tool_clamdscan = env["TOOL_CLAMDSCAN"]

    def verify_integrity_cb(file_path, **kwargs):
        return verify_integrity_fn(
            file_path,
            tool_nsz=tool_nsz,
            roms_dir=roms_dir,
            cmd_timeout=getattr(args, "cmd_timeout", None),
            tool_metadata=tool_metadata,
            is_nstool=is_nstool,
            keys_path=keys_path,
            tool_hactool=tool_hactool,
            **kwargs,
        )

    def scan_for_virus_cb(file_path):
        return scan_for_virus_fn(
            file_path,
            tool_clamscan=tool_clamscan,
            tool_clamdscan=tool_clamdscan,
            roms_dir=roms_dir,
            cmd_timeout=getattr(args, "cmd_timeout", None),
        )

    def safe_move_cb(source, dest):
        return safe_move_fn(source, dest, args=args, logger=logger)

    def get_metadata_cb(file_path):
        return get_metadata_fn(
            file_path,
            tool_metadata=tool_metadata,
            is_nstool=is_nstool,
            keys_path=keys_path,
            roms_dir=roms_dir,
            tool_nsz=tool_nsz,
            cmd_timeout=getattr(args, "cmd_timeout", None),
        )

    def handle_compression_cb(file_path):
        return handle_compression_fn(
            file_path,
            args=args,
            tool_nsz=tool_nsz,
            roms_dir=roms_dir,
            tool_metadata=tool_metadata,
            is_nstool=is_nstool,
            keys_path=keys_path,
            cmd_timeout=getattr(args, "cmd_timeout", None),
            tool_hactool=tool_hactool,
        )

    return {
        "args": args,
        "ROMS_DIR": roms_dir,
        "CSV_FILE": env["CSV_FILE"],
        "get_metadata": get_metadata_cb,
        "sanitize_name": sanitize_name_fn,
        "determine_region": determine_region_fn,
        "determine_type": determine_type_fn,
        "parse_languages": parse_languages_fn,
        "detect_languages_from_filename": detect_languages_from_filename_fn,
        "safe_move": safe_move_cb,
        "verify_integrity": verify_integrity_cb,
        "scan_for_virus": scan_for_virus_cb,
        "handle_compression": handle_compression_cb,
        "TOOL_METADATA": tool_metadata,
        "IS_NSTOOL": is_nstool,
        "logger": logger,
        "Col": color,
        "TITLE_ID_RE": title_id_re,
    }


def discover_switch_files(roms_dir: Path) -> list[Path]:
    return [
        file_path
        for file_path in roms_dir.rglob("*")
        if file_path.suffix.lower() in SWITCH_FILE_SUFFIXES and file_path.is_file()
    ]


def finalize_main(
    args: Any,
    catalog: list[list[Any]],
    stats: dict[str, int],
    roms_dir: Path,
    csv_file: Path,
    *,
    logger,
    color,
    cleanup_junk_fn,
) -> None:
    print("\n" + "=" * 75)
    if catalog and not args.dry_run:
        try:
            with open(csv_file, "w", newline="", encoding="utf-8") as file_obj:
                writer = csv.writer(file_obj)
                writer.writerow(
                    ["Nome", "TitleID", "Tipo", "Versão", "Região", "Idiomas", "Formato", "Caminho"]
                )
                writer.writerows(catalog)
            print(f"📊 Catálogo salvo em: {color.YELLOW}{csv_file.name}{color.RESET}")
        except Exception as e:
            logger.exception("Erro ao salvar CSV: %s", e)

    if args.clean_junk and not args.dry_run:
        cleanup_junk_fn(roms_dir)

    print(
        f"{color.GREEN}✅ Sucesso: {stats['ok']} | ⚠️  Pulos/Dups: {stats['skipped']} | "
        f"❌ Erros: {stats['erro']}{color.RESET}"
    )


def perform_clean_junk(roms_dir: Path, *, logger) -> None:
    print("🧹 Limpando lixo...")
    for junk in roms_dir.rglob("*"):
        if junk.suffix.lower() in {".txt", ".nfo", ".url", ".lnk", ".website"}:
            try:
                from emumanager.common.fileops import safe_unlink

                safe_unlink(junk, logger)
            except Exception as e:
                logger.debug("failed to remove junk %s: %s", junk, e)

    all_dirs = sorted(
        [path for path in roms_dir.rglob("*") if path.is_dir()],
        key=lambda path: str(path),
        reverse=True,
    )
    for path in all_dirs:
        try:
            if not any(path.iterdir()):
                path.rmdir()
        except Exception as e:
            logger.debug("failed to remove dir %s: %s", path, e)
