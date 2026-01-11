#!/usr/bin/env python3
# ruff: noqa
import argparse
import csv
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
from emumanager.logging_cfg import (
    Col,
    get_fileops_logger,
    configure_logging,
    get_logger,
)
from emumanager.switch import meta_extractor, meta_parser, metadata
from emumanager.verification.hasher import get_file_hash

# Keep original reference so test monkeypatches (which replace subprocess.run)
# can be detected
ORIGINAL_SUBPROCESS_RUN = subprocess.run

# ======================================================================
#  SWITCH ORGANIZER v13.3 (HELP EDITION)
# ======================================================================
#  Adicionado:
#  1. Menu de Ajuda Visual (roda quando nenhum argumento é passado).
#  2. Descrições detalhadas dos comandos.
# ==============================================================================


def show_banner():
    print(f"{Col.CYAN}")
    print(r"   _____         _ _       _       ")
    print(r"  / ____|       (_) |     | |      ")
    print(r" | (___   __      _ |_ ___| |__    ")
    print(r"  \___ \ \ \ /\ / / | __/ __| '_ \   ORGANIZER v13.3")
    print(r"  ____) | \ V  V /| | || (__| | | |  Nintendo Switch Library Manager")
    print(r" |_____/   \_/\_/ |_|\__\___|_| |_|  ")
    print(f"{Col.RESET}")


def show_manual():
    show_banner()
    print(f"{Col.BOLD}BEM-VINDO AO SWITCH ORGANIZER!{Col.RESET}")
    print("Este script organiza, comprime, verifica e cataloga sua coleção de jogos.\n")

    print(f"{Col.YELLOW}EXEMPLOS DE USO COMUNS:{Col.RESET}")
    print(f"  1. {Col.GREEN}Organizar Tudo (Recomendado):{Col.RESET}")
    print("     python3 script.py --organize --clean-junk")
    print(
        f"     {Col.GREY}* Cria pastas, renomeia corretamente e remove lixo.{Col.RESET}"
        "\n"
    )

    print(f"  2. {Col.GREEN}Economizar Espaço (Compressão):{Col.RESET}")
    print("     python3 script.py --compress --organize --clean-junk")
    print(f"     {Col.GREY}* Converte tudo para .NSZ e organiza.{Col.RESET}\n")

    print(f"  3. {Col.GREEN}Restaurar para Original:{Col.RESET}")
    print("     python3 script.py --decompress")
    print(f"     {Col.GREY}* Converte .NSZ de volta para .NSP.{Col.RESET}\n")

    print(f"  4. {Col.GREEN}Modo Simulação (Teste):{Col.RESET}")
    print("     python3 script.py --organize --dry-run")
    print(f"     {Col.GREY}* Mostra o que seria feito sem alterar nada.{Col.RESET}\n")

    print(f"{Col.YELLOW}ARGUMENTOS DISPONÍVEIS:{Col.RESET}")
    print("  --dir [PASTA]    : Define a pasta dos jogos (Padrão: atual).")
    print("  --keys [ARQUIVO] : Caminho do prod.keys.")
    print(
        "  --no-verify      : Pula a verificação de integridade "
        "(Mais rápido, menos seguro)."
    )
    print("  --level [1-22]   : Nível de compressão NSZ (Padrão: 1).")
    print(
        f"\n{Col.CYAN}Para ver a lista técnica completa, use: "
        f"python3 script.py --help{Col.RESET}"
    )
    sys.exit(0)


# --- CONFIGURAÇÃO ARGPARSE ---
parser = argparse.ArgumentParser(
    description="Gerenciador Avançado de ROMs Nintendo Switch",
    formatter_class=argparse.RawTextHelpFormatter,
    epilog="Exemplo: python3 script.py --compress --organize --clean-junk",
)

parser.add_argument(
    "--dir",
    type=str,
    default=".",
    help="Diretório alvo das ROMs (Default: pasta atual)",
)
parser.add_argument(
    "--keys",
    type=str,
    default="./prod.keys",
    help="Caminho do arquivo prod.keys",
)
parser.add_argument(
    "--dry-run",
    action="store_true",
    help="SIMULAÇÃO: Não move nem deleta arquivos",
)
parser.add_argument(
    "--no-verify",
    action="store_true",
    help="Pula verificação de hash (SHA256/CRC)",
)
parser.add_argument(
    "--organize",
    action="store_true",
    help="Move arquivos para subpastas: 'Nome do Jogo [IDBase]'",
)
parser.add_argument(
    "--clean-junk",
    action="store_true",
    help="Remove arquivos inúteis (.txt, .nfo, .url, .lnk)",
)
parser.add_argument(
    "--compress",
    action="store_true",
    help="Comprime ROMs (XCI/NSP) para formato NSZ",
)
parser.add_argument(
    "--decompress",
    action="store_true",
    help="Descomprime (NSZ) de volta para NSP",
)

parser.add_argument(
    "--rm-originals",
    action="store_true",
    help=(
        "Ao comprimir, remove os arquivos originais somente se a compressão "
        "for bem-sucedida"
    ),
)

parser.add_argument(
    "--recompress",
    action="store_true",
    help=(
        "Recomprime arquivos já em .nsz/.xcz para o nível especificado "
        "(substitui o arquivo comprimido se bem-sucedido)"
    ),
)
parser.add_argument(
    "--level",
    type=int,
    default=3,
    help="Nível de compressão Zstd (1-22). Padrão: 3 (balanced)",
)

parser.add_argument(
    "--compression-profile",
    choices=["fast", "balanced", "best"],
    default=None,
    help=(
        "Perfil de compressão predefinido: 'fast' (prioriza velocidade), "
        "'balanced' (bom equilíbrio tempo/espaço), 'best' (máxima compressão, "
        "mais lento). Se definido, sobrescreve --level."
    ),
)
parser.add_argument(
    "--dup-check",
    choices=["fast", "strict"],
    default="fast",
    help=(
        "Modo de verificação de duplicatas: 'fast' usa size+mtime, "
        "'strict' usa SHA256 (padrão: fast)"
    ),
)
parser.add_argument(
    "--verbose", action="store_true", help="Ativa logging verboso (DEBUG)"
)
parser.add_argument(
    "--log-file",
    type=str,
    default="organizer_v13.log",
    help="Arquivo de log (padrão: organizer_v13.log)",
)
parser.add_argument(
    "--log-max-bytes",
    type=int,
    default=5 * 1024 * 1024,
    help="Tamanho máximo do log em bytes antes de rotacionar (padrão: 5MB)",
)
parser.add_argument(
    "--log-backups",
    type=int,
    default=3,
    help="Número de arquivos de log de backup a manter (padrão: 3)",
)

parser.add_argument(
    "--keep-on-failure",
    action="store_true",
    help=(
        "Preserva arquivos gerados quando ocorrer falha (move para quarentena "
        "ou deixa no lugar)"
    ),
)

parser.add_argument(
    "--cmd-timeout",
    type=int,
    default=3600,
    help="Timeout em segundos para comandos externos (padrão: 3600)",
)

parser.add_argument(
    "--health-check",
    action="store_true",
    help=(
        "Verifica integridade dos arquivos e escaneia por vírus "
        "(usa clamscan/clamdscan se disponíveis)"
    ),
)
parser.add_argument(
    "--quarantine",
    action="store_true",
    help=(
        "(usado com --health-check) move arquivos infectados/corrompidos "
        "para _QUARANTINE"
    ),
)
parser.add_argument(
    "--quarantine-dir",
    type=str,
    default=None,
    help=(
        "Diretório onde mover arquivos em quarentena "
        "(default: _QUARANTINE dentro de --dir)"
    ),
)
parser.add_argument(
    "--deep-verify",
    action="store_true",
    help=("Executa verificação mais profunda quando possível (usa hactool/nsz juntos)"),
)
parser.add_argument(
    "--report-csv",
    type=str,
    default=None,
    help="(usado com --health-check) caminho para salvar relatório CSV detalhado",
)

# NOTE: Do not call show_manual() at import time. Calling it when the module
# is imported (for example by tests or by other modules) causes an early
# sys.exit which breaks imports. The script will show the manual when run as
# __main__ with no arguments.

# --- SETUP GERAL (será inicializado em main) ---
# ROMS_DIR, KEYS_PATH, DUPE_DIR, CSV_FILE serão definidos em main()

logger = logging.getLogger("organizer_v13")
SHUTDOWN_REQUESTED = False


def setup_logging(
    logfile: str,
    verbose: bool = False,
    max_bytes: int = 5 * 1024 * 1024,
    backups: int = 3,
    base_dir: Optional[Path] = None,
) -> None:
    """Configure logging using central `configure_logging`.

    This sets environment overrides so that the centralized logging
    configuration will place the persistent log file where the CLI
    expects. We intentionally keep behavior idempotent and minimal here.
    """
    # Respect CLI-specified logfile: prefer a path relative to base_dir
    try:
        if logfile:
            # If logfile is not an absolute path, place it under base_dir or cwd
            lf = Path(logfile)
            if not lf.is_absolute():
                target_dir = Path(base_dir) if base_dir else Path.cwd()
                lf = target_dir / lf
            os.environ["EMUMANAGER_LOG_FILE"] = str(lf)
    except Exception:
        # Best-effort only; don't fail the app for logging env setup
        pass

    # Map verbose flag to log level env so configure_logging picks it up
    if verbose:
        os.environ.setdefault("EMUMANAGER_LOG_LEVEL", str(logging.DEBUG))

    # Call centralized configure with rotation parameters
    configure_logging(
        base_dir=Path(base_dir) if base_dir else None,
        level=logging.DEBUG if verbose else logging.INFO,
        max_bytes=max_bytes,
        backup_count=backups,
    )

    # Ensure module logger uses the centralized handlers
    global logger
    logger = get_logger("organizer_v13", base_dir=Path(base_dir) if base_dir else None)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)


# --- DETECÇÃO DE FERRAMENTAS ---
# find_tool imported from emumanager.common.execution


def _signal_handler(signum, frame):
    global SHUTDOWN_REQUESTED
    logger.warning("Signal %s received: requesting shutdown...", signum)
    SHUTDOWN_REQUESTED = True
    cancel_current_process()


# As verificações de ferramentas e dependências ocorrem dentro de main(),
# pois dependem de argumentos (por exemplo '--keys').

# --- FUNÇÕES CORE ---
# (Funções auxiliares importadas de metadata.py)
parse_languages = metadata.parse_languages
detect_languages_from_filename = metadata.detect_languages_from_filename
determine_type = metadata.determine_type
determine_region = metadata.determine_region
get_base_id = metadata.get_base_id
sanitize_name = metadata.sanitize_name


# --- CONSTANTS / COMMON REGEX ---
TITLE_ID_RE = re.compile(
    r"(?:Title ID|Program Id):\s*(?:0x)?([0-9A-F]{16})", re.IGNORECASE
)
INVALID_FILENAME_CHARS_RE = re.compile(r'[<>:"/\\|?*]')
# Compression profile mapping: maps friendly presets to NSZ zstd levels
COMPRESSION_PROFILE_LEVELS = {
    "fast": 1,
    "balanced": 3,
    "best": 19,
}


# --- OPERAÇÕES ---


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
    return meta_extractor.get_metadata_info(
        filepath,
        run_cmd=run_cmd,
        tool_metadata=tool_metadata,
        is_nstool=is_nstool,
        keys_path=keys_path,
        tool_nsz=tool_nsz,
        roms_dir=roms_dir,
        cmd_timeout=cmd_timeout,
        parse_tool_output=meta_parser.parse_tool_output,
        parse_languages=parse_languages,
        detect_languages_from_filename=detect_languages_from_filename,
        determine_type=determine_type,
    )


def _verify_nsz_pass(filepath, tool_nsz, roms_dir, cmd_timeout):
    from emumanager.switch.verify import verify_nsz
    try:
        logbase = Path(roms_dir) / "logs" / "nsz" / (filepath.stem + ".verify_nsz")
        res = run_cmd([str(tool_nsz), "--verify", str(filepath)], filebase=logbase, timeout=cmd_timeout)
        ok = verify_nsz(filepath, lambda *a, **k: res, tool_nsz=str(tool_nsz))
        out = (getattr(res, "stdout", "") or "") + "\n" + (getattr(res, "stderr", "") or "")
        return ok, out
    except Exception as e:
        logger.debug("nsz verify pass failed for %s: %s", filepath, e)
        return False, str(e)


def _verify_metadata_pass(filepath, tool_metadata, is_nstool, keys_path, roms_dir, cmd_timeout):
    from emumanager.switch.verify import verify_metadata_tool
    try:
        cmd = [str(tool_metadata), "--verify", str(filepath)]
        if not is_nstool:
            cmd.insert(1, "-k")
            cmd.insert(2, str(keys_path))
        logbase = Path(roms_dir) / "logs" / "nsz" / (filepath.stem + ".verify_meta")
        res = run_cmd(cmd, filebase=logbase, timeout=cmd_timeout)
        ok = verify_metadata_tool(filepath, lambda *a, **k: res, tool_metadata=str(tool_metadata), 
                                  is_nstool=is_nstool, keys_path=keys_path)
        out = (getattr(res, "stdout", "") or "") + "\n" + (getattr(res, "stderr", "") or "")
        return ok, out
    except Exception as e:
        logger.debug("metadata verify pass failed for %s: %s", filepath, e)
        return False, str(e)


def _verify_hactool_deep_pass(filepath, tool_hactool, keys_path, roms_dir, cmd_timeout):
    from emumanager.switch.verify import verify_hactool_deep
    try:
        cmd = [str(tool_hactool), "-k", str(keys_path), str(filepath)] if keys_path and keys_path.exists() else [str(tool_hactool), str(filepath)]
        logbase = Path(roms_dir) / "logs" / "nsz" / (filepath.stem + ".verify_hactool")
        res = run_cmd(cmd, filebase=logbase, timeout=cmd_timeout)
        ok = verify_hactool_deep(filepath, lambda *a, **k: res, keys_path=keys_path)
        out = (getattr(res, "stdout", "") or "") + "\n" + (getattr(res, "stderr", "") or "")
        return ok, out
    except Exception as e:
        logger.debug("hactool deep verify pass failed for %s: %s", filepath, e)
        return False, str(e)


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
    results = []
    is_nsz = filepath.suffix.lower() in {".nsz", ".xcz"}

    if is_nsz and tool_nsz:
        results.append(_verify_nsz_pass(filepath, tool_nsz, roms_dir, cmd_timeout))

    if tool_metadata:
        results.append(_verify_metadata_pass(filepath, tool_metadata, is_nstool, keys_path, roms_dir, cmd_timeout))

    if deep and tool_hactool:
        results.append(_verify_hactool_deep_pass(filepath, tool_hactool, keys_path, roms_dir, cmd_timeout))

    any_ok = any(r for r, _ in results)
    combined_out = "\n---\n".join(out for _, out in results)

    if return_output:
        return any_ok, combined_out

    if not any_ok:
        logger.debug("verify_integrity outputs:\n%s", combined_out)
        return False
    return True


def scan_for_virus(filepath, *, tool_clamscan, tool_clamdscan, roms_dir, cmd_timeout):
    """Run a local antivirus scan using clamscan or clamdscan if available.

    Returns a tuple (infected: Optional[bool], output: str).
    infected: True => infected, False => clean, None => scanner not available
    or error.
    """
    tool = None
    if tool_clamscan:
        tool = tool_clamscan
    elif tool_clamdscan:
        tool = tool_clamdscan
    else:
        return None, "No AV scanner found"

    cmd = [str(tool), "--no-summary", str(filepath)]
    try:
        logbase = Path(roms_dir) / "logs" / "nsz" / (filepath.stem + ".av")
        res = run_cmd(cmd, filebase=logbase, timeout=cmd_timeout)
        out = (
            (getattr(res, "stdout", "") or "")
            + "\n"
            + (getattr(res, "stderr", "") or "")
        )
        # clamscan/clamdscan: 0 = OK, 1 = infected, 2 = error
        rc = getattr(res, "returncode", None)
        if rc == 0:
            return False, out
        if rc == 1:
            return True, out
        # treat other codes as unknown/error
        logger.debug("AV scan returned code %s for %s", rc, filepath)
        return None, out
    except Exception as e:
        logger.exception("scan_for_virus failed for %s", filepath)
        return None, str(e)


def _run_nsz_info_attempts(filepath, tool_nsz, roms_dir, cmd_timeout):
    attempts = [
        [str(tool_nsz), "--info", str(filepath)],
        [str(tool_nsz), "-i", str(filepath)],
        [str(tool_nsz), "info", str(filepath)],
    ]
    for cmd in attempts:
        try:
            logbase = Path(roms_dir) / "logs" / "nsz" / (filepath.stem + ".info")
            res = run_cmd(cmd, filebase=logbase, timeout=cmd_timeout)
            out = (getattr(res, "stdout", "") or "") + "\n" + (getattr(res, "stderr", "") or "")
            if out and out.strip():
                return out
        except Exception as e:
            logger.debug("nsz info attempt failed: %s", e)
            continue
    return ""


def detect_nsz_level(filepath, *, tool_nsz, roms_dir, cmd_timeout) -> Optional[int]:
    if not tool_nsz:
        return None
    
    try:
        out = _run_nsz_info_attempts(filepath, tool_nsz, roms_dir, cmd_timeout)
        if not out:
            return None

        patterns = [
            r"zstd(?: compression)? level\s*(?:[:=\-]\s*)?(\d+)",
            r"compression level\s*(?:[:=\-]\s*)?(\d+)",
            r"level\s*(?:[:=\-]\s*)?(\d+)"
        ]
        
        for pat in patterns:
            m = re.search(pat, out, re.IGNORECASE)
            if m:
                return int(m.group(1))
                
    except Exception as e:
        logger.debug("detect_nsz_level failed for %s: %s", filepath, e)
    return None


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
    # Support recompressing already-compressed archives when requested or when
    # requested level is higher
    if args.compress and filepath.suffix.lower() in {".nsz", ".xcz"}:
        return _handle_recompression(
            filepath,
            args,
            tool_nsz,
            roms_dir,
            cmd_timeout,
            tool_metadata,
            is_nstool,
            keys_path,
            tool_hactool,
        )

    if args.compress and filepath.suffix.lower() != ".nsz":
        return _handle_new_compression(
            filepath,
            args,
            tool_nsz,
            roms_dir,
            cmd_timeout,
            tool_metadata,
            is_nstool,
            keys_path,
            tool_hactool,
        )

    if args.decompress and filepath.suffix.lower() in {".nsz", ".xcz"}:
        return _handle_decompression(
            filepath,
            args,
            tool_nsz,
            roms_dir,
            cmd_timeout,
            tool_metadata,
            is_nstool,
            keys_path,
        )

    return filepath


def _should_recompress(filepath, args, tool_nsz, roms_dir, cmd_timeout):


    if getattr(args, "recompress", False):


        return True


    try:


        cur = detect_nsz_level(filepath, tool_nsz=tool_nsz, roms_dir=roms_dir, cmd_timeout=cmd_timeout)


        if cur is not None and args.level > cur:


            logger.info("Detected existing zstd level %s -> will recompress to %s", cur, args.level)


            return True


    except Exception as e:


        logger.debug("Failed to detect existing nsz level for %s: %s", filepath, e)


    return False








def _execute_recompression(filepath, args, tool_nsz, roms_dir, cmd_timeout, tool_metadata, is_nstool, keys_path, tool_hactool):


    from emumanager.switch.compression import handle_produced_file, try_multiple_recompress_attempts


    try:


        print("   🗜️  Recomprimindo (ajuste de nível)...", end="", flush=True)


        with tempfile.TemporaryDirectory(prefix="nsz_recomp_") as td:


            tmpdir = Path(td)


            attempts = [[str(tool_nsz), "-C", "-l", str(args.level), "-o", str(tmpdir), str(filepath)],


                        [str(tool_nsz), "-C", "-l", str(args.level), str(filepath), "-o", str(tmpdir)],


                        [str(tool_nsz), "-C", "-l", str(args.level), str(filepath)]]


            


            log_cb = lambda *a, **k: run_cmd(a[0], filebase=Path(roms_dir) / "logs" / "nsz" / (filepath.stem + ".recomp"), timeout=cmd_timeout)


            produced = try_multiple_recompress_attempts(tmpdir, attempts, log_cb, progress_callback=getattr(args, "progress_callback", None))





            if produced:


                verify_fn = lambda p, rc: verify_integrity(p, deep=False, tool_nsz=tool_nsz, roms_dir=roms_dir, cmd_timeout=cmd_timeout, 


                                                           tool_metadata=tool_metadata, is_nstool=is_nstool, keys_path=keys_path, tool_hactool=tool_hactool)


                result_path = handle_produced_file(produced[0], filepath, log_cb, verify_fn=verify_fn, args=args, roms_dir=roms_dir)


                if result_path == filepath:


                    print(f" {Col.GREEN}[OK]{Col.RESET}")


                    logger.info("Recompression succeeded and file replaced: %s", filepath.name)


                return result_path





        print(f" {Col.RED}[FALHA]{Col.RESET}")


    except Exception as e:


        logger.exception(f"recompress failed for {filepath}: {e}")


        print(f" {Col.RED}[FALHA]{Col.RESET}")


    return filepath








def _handle_recompression(


    filepath,


    args,


    tool_nsz,


    roms_dir,


    cmd_timeout,


    tool_metadata,


    is_nstool,


    keys_path,


    tool_hactool,


):


    if _should_recompress(filepath, args, tool_nsz, roms_dir, cmd_timeout):


        if args.dry_run:


            return filepath


        return _execute_recompression(filepath, args, tool_nsz, roms_dir, cmd_timeout, tool_metadata, is_nstool, keys_path, tool_hactool)


    return filepath





def _post_compression_cleanup(filepath, compressed_candidate, args, tool_nsz, roms_dir, cmd_timeout, tool_metadata, is_nstool, keys_path, tool_hactool):
    if not (args.rm_originals and not args.dry_run and compressed_candidate):
        return

    try:
        if not (compressed_candidate.exists() and compressed_candidate.stat().st_size > 0):
            return

        ok = verify_integrity(compressed_candidate, deep=False, tool_nsz=tool_nsz, roms_dir=roms_dir, cmd_timeout=cmd_timeout, 
                              tool_metadata=tool_metadata, is_nstool=is_nstool, keys_path=keys_path, tool_hactool=tool_hactool)
        if ok:
            filepath.unlink()
            logger.info("Original removido após compressão bem-sucedida: %s", filepath.name)
        else:
            logger.warning("Compressed file generated but failed verification: %s", compressed_candidate)
            if getattr(args, "keep_on_failure", False):
                _move_to_quarantine(compressed_candidate, args, roms_dir)
    except Exception as e:
        logger.exception("Error while validating/removing original for %s: %s", filepath, e)


def _move_to_quarantine(path, args, roms_dir):
    try:
        qdir = args.quarantine_dir or (roms_dir / "_QUARANTINE")
        quarantine_dir = Path(qdir).resolve()
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        dest = quarantine_dir / path.name
        shutil.move(str(path), str(dest))
        logger.info("Moved failed compressed artifact to quarantine: %s", dest)
    except Exception as e:
        logger.exception("Failed moving failed compressed artifact to quarantine: %s (%s)", path, e)


def _handle_new_compression(
    filepath,
    args,
    tool_nsz,
    roms_dir,
    cmd_timeout,
    tool_metadata,
    is_nstool,
    keys_path,
    tool_hactool,
):
    if args.dry_run:
        return filepath.with_suffix(".nsz")
    try:
        print("   🗜️  Comprimindo...", end="", flush=True)
        from emumanager.switch.compression import compress_file

        log_cb = lambda *a, **k: run_cmd(a[0], filebase=Path(roms_dir) / "logs" / "nsz" / (filepath.stem + ".compress"), 
                                         timeout=cmd_timeout, check=k.get("check", False))
        compressed_candidate = compress_file(filepath, log_cb, tool_nsz=str(tool_nsz), level=args.level, args=args, roms_dir=Path(roms_dir))

        if not compressed_candidate:
            print(f" {Col.RED}[FALHA]{Col.RESET}")
            return filepath

        print(f" {Col.GREEN}[OK]{Col.RESET}")
        _post_compression_cleanup(filepath, compressed_candidate, args, tool_nsz, roms_dir, cmd_timeout, tool_metadata, is_nstool, keys_path, tool_hactool)
        return compressed_candidate
    except Exception as e:
        logger.exception(f"compress failed for {filepath}: {e}")
        print(f" {Col.RED}[FALHA]{Col.RESET}")
        return filepath


def _handle_decompression(
    filepath,
    args,
    tool_nsz,
    roms_dir,
    cmd_timeout,
    tool_metadata,
    is_nstool,
    keys_path,
):
    if args.dry_run:
        return filepath.with_suffix(".nsp")
    try:
        print("   📦 Descomprimindo...", end="", flush=True)
        from emumanager.switch.compression import decompress_and_find_candidate

        candidate = decompress_and_find_candidate(
            filepath,
            lambda *a, **k: run_cmd(
                a[0],
                filebase=Path(roms_dir)
                / "logs"
                / "nsz"
                / (filepath.stem + ".decomp_act"),
                timeout=cmd_timeout,
            ),
            tool_nsz=str(tool_nsz),
            tool_metadata=str(tool_metadata) if tool_metadata else None,
            is_nstool=is_nstool,
            keys_path=keys_path,
            args=args,
            roms_dir=roms_dir,
        )

        if candidate:
            print(f" {Col.GREEN}[OK]{Col.RESET}")
            return candidate

        print(f" {Col.RED}[FALHA]{Col.RESET}")
        return filepath
    except Exception as e:
        logger.exception(f"decompress failed for {filepath}: {e}")
        print(f" {Col.RED}[FALHA]{Col.RESET}")
        return filepath


def safe_move(source, dest, *, args, logger):
    # thin wrapper delegating to the testable implementation in
    # emumanager.common.fileops
    try:
        from emumanager.common.fileops import safe_move as _safe_move_impl

        # Prefer dedicated fileops logger for audit; fall back to provided logger
        base_dir = (
            getattr(args, "roms_dir", None) or getattr(args, "base_path", None) or None
        )
        fileops_logger = get_fileops_logger(base_dir) if base_dir else logger

        return _safe_move_impl(
            source,
            dest,
            args=args,
            get_file_hash=get_file_hash,
            logger=fileops_logger,
        )
    except Exception:
        # Fallback: attempt a simple move
        try:
            if getattr(args, "dry_run", False):
                return True
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(dest))
            return True
        except Exception:
            logger.exception("Fallback move failed %s -> %s", source, dest)
            return False


def print_progress(current, total, filename):
    percent = 100 * (current / float(total))
    bar = "█" * int(30 * current // total) + "-" * (30 - int(30 * current // total))
    sys.stdout.write(
        f"\r{Col.CYAN}[{bar}] {percent:.1f}%{Col.RESET} | {filename[:25]}.."
    )
    sys.stdout.flush()


# --- LOOP PRINCIPAL (encapsulado em main) ---
def _apply_cli_settings(args):
    # Install signal handlers for graceful shutdown
    try:
        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)
    except Exception as e:
        logger.debug("Could not install signal handlers: %s", e)

    # Apply compression profile if provided
    try:
        prof = getattr(args, "compression_profile", None)
        if prof and prof in COMPRESSION_PROFILE_LEVELS:
            args.level = COMPRESSION_PROFILE_LEVELS[prof]
            logger.info("Compression profile '%s' selected -> level %s", prof, args.level)
        elif prof:
            logger.warning("Unknown compression profile '%s', keeping --level=%s", prof, args.level)
    except Exception as e:
        logger.exception("Error while applying compression_profile: %s", e)

    # Validate numeric level bounds (1-22)
    try:
        args.level = max(1, min(22, int(args.level)))
    except Exception:
        logger.warning("Invalid compression level; using 1")
        args.level = 1

    if args.compress and args.decompress:
        sys.exit(f"{Col.RED}Erro: Escolha --compress OU --decompress.{Col.RESET}")

    if args.verbose:
        logger.setLevel(logging.DEBUG)


def _prepare_ctx(args, env):
    ROMS_DIR = env["ROMS_DIR"]
    KEYS_PATH = env["KEYS_PATH"]
    TOOL_METADATA = env["TOOL_METADATA"]
    IS_NSTOOL = env["IS_NSTOOL"]
    TOOL_HACTOOL = env["TOOL_HACTOOL"]
    TOOL_NSZ = env["TOOL_NSZ"]
    TOOL_CLAMSCAN = env["TOOL_CLAMSCAN"]
    TOOL_CLAMDSCAN = env["TOOL_CLAMDSCAN"]

    verify_integrity_fn = lambda f, **k: verify_integrity(f, tool_nsz=TOOL_NSZ, roms_dir=ROMS_DIR, cmd_timeout=getattr(args, "cmd_timeout", None),
                                                          tool_metadata=TOOL_METADATA, is_nstool=IS_NSTOOL, keys_path=KEYS_PATH, tool_hactool=TOOL_HACTOOL, **k)
    scan_for_virus_fn = lambda f: scan_for_virus(f, tool_clamscan=TOOL_CLAMSCAN, tool_clamdscan=TOOL_CLAMDSCAN, roms_dir=ROMS_DIR, cmd_timeout=getattr(args, "cmd_timeout", None))
    safe_move_fn = lambda s, d: safe_move(s, d, args=args, logger=logger)
    get_metadata_fn = lambda f: get_metadata(f, tool_metadata=TOOL_METADATA, is_nstool=IS_NSTOOL, keys_path=KEYS_PATH, roms_dir=ROMS_DIR, tool_nsz=TOOL_NSZ, cmd_timeout=getattr(args, "cmd_timeout", None))
    handle_compression_fn = lambda f: handle_compression(f, args=args, tool_nsz=TOOL_NSZ, roms_dir=ROMS_DIR, tool_metadata=TOOL_METADATA, is_nstool=IS_NSTOOL, keys_path=KEYS_PATH, cmd_timeout=getattr(args, "cmd_timeout", None), tool_hactool=TOOL_HACTOOL)

    return {
        "args": args, "ROMS_DIR": ROMS_DIR, "CSV_FILE": env["CSV_FILE"], "get_metadata": get_metadata_fn, "sanitize_name": sanitize_name,
        "determine_region": determine_region, "determine_type": determine_type, "parse_languages": parse_languages,
        "detect_languages_from_filename": detect_languages_from_filename, "safe_move": safe_move_fn, "verify_integrity": verify_integrity_fn,
        "scan_for_virus": scan_for_virus_fn, "handle_compression": handle_compression_fn, "TOOL_METADATA": TOOL_METADATA,
        "IS_NSTOOL": IS_NSTOOL, "logger": logger, "Col": Col, "TITLE_ID_RE": TITLE_ID_RE,
    }


def _finalize_main(args, catalog, stats, roms_dir, csv_file):
    print("\n" + "=" * 75)
    if catalog and not args.dry_run:
        try:
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Nome", "TitleID", "Tipo", "Versão", "Região", "Idiomas", "Formato", "Caminho"])
                writer.writerows(catalog)
            print(f"📊 Catálogo salvo em: {Col.YELLOW}{csv_file.name}{Col.RESET}")
        except Exception as e:
            logger.exception("Erro ao salvar CSV: %s", e)

    if args.clean_junk and not args.dry_run:
        _perform_clean_junk(roms_dir)

    print(f"{Col.GREEN}✅ Sucesso: {stats['ok']} | ⚠️  Pulos/Dups: {stats['skipped']} | ❌ Erros: {stats['erro']}{Col.RESET}")


def _perform_clean_junk(roms_dir):
    print("🧹 Limpando lixo...")
    for junk in roms_dir.rglob("*"):
        if junk.suffix.lower() in {".txt", ".nfo", ".url", ".lnk", ".website"}:
            try:
                from emumanager.common.fileops import safe_unlink
                safe_unlink(junk, logger)
            except Exception as e:
                logger.debug("failed to remove junk %s: %s", junk, e)

    all_dirs = sorted([p for p in roms_dir.rglob("*") if p.is_dir()], key=lambda p: str(p), reverse=True)
    for p in all_dirs:
        try:
            if not any(p.iterdir()):
                p.rmdir()
        except Exception as e:
            logger.debug("failed to remove dir %s: %s", p, e)


def main(argv: Optional[List[str]] = None):
    args = parser.parse_args(argv)
    _apply_cli_settings(args)

    from emumanager.switch.main_helpers import configure_environment
    env = configure_environment(args, logger, find_tool)
    setup_logging(args.log_file, args.verbose)
    
    logger.info("Starting Switch Organizer")
    logger.info("Directory: %s", env["ROMS_DIR"])

    files = [f for f in env["ROMS_DIR"].rglob("*") if f.suffix.lower() in {".xci", ".nsp", ".nsz", ".xcz"} and f.is_file()]
    if not files:
        logger.info("Nenhum arquivo .xci/.nsp/.nsz/.xcz encontrado no diretório especificado.")
        return

    ctx = _prepare_ctx(args, env)

    if args.health_check:
        from emumanager.switch.main_helpers import run_health_check
        hc_summary = run_health_check(files, args, env["ROMS_DIR"], ctx["verify_integrity"], ctx["scan_for_virus"], ctx["safe_move"], logger)
        if not any([args.organize, args.compress, args.decompress, args.clean_junk]):
            sys.exit(1 if hc_summary.get("corrupted") or hc_summary.get("infected") else 0)

    from emumanager.switch.main_helpers import process_files
    catalog, stats = process_files(files, ctx)
    _finalize_main(args, catalog, stats, env["ROMS_DIR"], env["CSV_FILE"])


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        # argparse or explicit sys.exit calls
        raise
    except Exception:
        logger.exception("Unexpected fatal error while running script")
        sys.exit(2)
