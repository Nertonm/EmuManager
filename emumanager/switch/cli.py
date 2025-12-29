#!/usr/bin/env python3
# ruff: noqa
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, List, Optional

from emumanager.switch import metadata
from emumanager.common.execution import (
    run_cmd,
    cancel_current_process,
    find_tool,
)
import argparse
import csv
import logging
from logging.handlers import RotatingFileHandler
from emumanager.switch import meta_extractor, meta_parser
from emumanager.logging_cfg import Col, get_fileops_logger
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
    print(
        f"     {Col.GREY}* Mostra o que seria feito sem alterar nada.{Col.RESET}\n"
    )

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
    help=(
        "Executa verificação mais profunda quando possível "
        "(usa hactool/nsz juntos)"
    ),
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
) -> None:
    """Configura o logger global com rotação e console.

    logfile: caminho para o arquivo de log
    verbose: se True, nível DEBUG
    """
    # remove handlers antigos
    for h in logger.handlers:
        logger.removeHandler(h)

    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    # Rotating file handler
    try:
        fh = RotatingFileHandler(
            logfile, maxBytes=max_bytes, backupCount=backups, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception:
        # fallback to basic file handler
        fh = logging.FileHandler(logfile, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    # console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)


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
    # compressed formats we treat similarly
    is_nsz = filepath.suffix.lower() in {".nsz", ".xcz"}
    try:
        # local import to avoid circular dependencies during early package staging
        from emumanager.switch.verify import (
            verify_nsz,
            verify_metadata_tool,
            verify_hactool_deep,
        )

        results = []

        # Primary check: use NSZ verify if it's an nsz/xcz and nsz tool exists
        if is_nsz and tool_nsz:
            try:
                logbase_n = (
                    Path(roms_dir) / "logs" / "nsz" / (filepath.stem + ".verify_nsz")
                )
                res_nsz = run_cmd(
                    [str(tool_nsz), "--verify", str(filepath)],
                    filebase=logbase_n,
                    timeout=cmd_timeout,
                )
                # Use the verify helper but avoid re-running the tool by passing a lambda
                # that returns the captured result
                ok_nsz = verify_nsz(
                    filepath,
                    lambda *a, **k: res_nsz,
                    tool_nsz=str(tool_nsz),
                )
                results.append(
                    (
                        ok_nsz,
                        (getattr(res_nsz, "stdout", "") or "")
                        + "\n"
                        + (getattr(res_nsz, "stderr", "") or ""),
                    )
                )
            except Exception as e:
                logger.debug("nsz verify raised: %s", e)
                results.append((False, str(e)))

        # Metadata tool check (nstool/hactool)
        try:
            cmd = [str(tool_metadata), "--verify", str(filepath)]
            if not is_nstool:
                cmd.insert(1, "-k")
                cmd.insert(2, str(keys_path))
            logbase_m = (
                Path(roms_dir)
                / "logs"
                / "nsz"
                / (filepath.stem + ".verify_meta")
            )
            res_meta = run_cmd(cmd, filebase=logbase_m, timeout=cmd_timeout)
            ok_meta = verify_metadata_tool(
                filepath,
                lambda *a, **k: res_meta,
                tool_metadata=str(tool_metadata),
                is_nstool=is_nstool,
                keys_path=keys_path,
            )
            results.append(
                (
                    ok_meta,
                    (getattr(res_meta, "stdout", "") or "")
                    + "\n"
                    + (getattr(res_meta, "stderr", "") or ""),
                )
            )
        except Exception as e:
            logger.debug("metadata verify raised: %s", e)
            results.append((False, str(e)))

        # If deep requested and hactool available, attempt extra pass with
        # hactool specifics
        if deep and tool_hactool:
            try:
                cmd = (
                    [str(tool_hactool), "-k", str(keys_path), str(filepath)]
                    if keys_path and keys_path.exists()
                    else [str(tool_hactool), str(filepath)]
                )
                logbase_h = (
                    Path(roms_dir)
                    / "logs"
                    / "nsz"
                    / (filepath.stem + ".verify_hactool")
                )
                res_h = run_cmd(cmd, filebase=logbase_h, timeout=cmd_timeout)
                ok_h = verify_hactool_deep(
                    filepath, lambda *a, **k: res_h, keys_path=keys_path
                )
                results.append(
                    (
                        ok_h,
                        (getattr(res_h, "stdout", "") or "")
                        + "\n"
                        + (getattr(res_h, "stderr", "") or ""),
                    )
                )
            except Exception as e:
                logger.debug("hactool deep verify raised: %s", e)
                results.append((False, str(e)))

        # Evaluate results: prefer conservative approach - require at least one positive
        any_ok = any(r for r, _ in results)
        combined_out = "\n---\n".join(out for _, out in results)
        if return_output:
            return any_ok, combined_out
        # normal boolean return
        if not any_ok:
            logger.debug("verify_integrity outputs:\n%s", combined_out)
            return False
        return True
    except Exception:
        logger.exception("verify_integrity raised an unexpected exception")
        return False


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


def detect_nsz_level(filepath, *, tool_nsz, roms_dir, cmd_timeout) -> Optional[int]:
    """Try to detect zstd compression level used inside an .nsz/.xcz using
    nsz --info/-i output.

    Returns integer level or None if unknown.
    """
    if not tool_nsz:
        return None
    try:
        # Try common info switches
        attempts = [
            [str(tool_nsz), "--info", str(filepath)],
            [str(tool_nsz), "-i", str(filepath)],
            [str(tool_nsz), "info", str(filepath)],
        ]
        out = ""
        for cmd in attempts:
            try:
                logbase_i = Path(roms_dir) / "logs" / "nsz" / (filepath.stem + ".info")
                res = run_cmd(cmd, filebase=logbase_i, timeout=cmd_timeout)
                out = (
                    (getattr(res, "stdout", "") or "")
                    + "\n"
                    + (getattr(res, "stderr", "") or "")
                )
                if out and len(out.strip()) > 0:
                    break
            except Exception:
                continue

        if not out:
            return None

        # Look for typical patterns indicating zstd level
        # Fix for python:S5852 (slow regex due to overlapping \s* and optional separator)
        # We replace \s*[:=\-]?\s* with \s*(?:[:=\-]\s*)? to avoid \s*\s* when separator is missing.
        m = re.search(
            r"zstd(?: compression)? level\s*(?:[:=\-]\s*)?(\d+)",
            out,
            re.IGNORECASE,
        )
        if not m:
            m = re.search(
                r"compression level\s*(?:[:=\-]\s*)?(\d+)", out, re.IGNORECASE
            )
        if not m:
            m = re.search(r"level\s*(?:[:=\-]\s*)?(\d+)", out, re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return None
    except Exception:
        logger.debug("detect_nsz_level failed for %s", filepath)
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
    should_recompress = getattr(args, "recompress", False)
    if not should_recompress:
        try:
            cur = detect_nsz_level(
                filepath,
                tool_nsz=tool_nsz,
                roms_dir=roms_dir,
                cmd_timeout=cmd_timeout,
            )
            if cur is not None and args.level > cur:
                should_recompress = True
                logger.info(
                    "Detected existing zstd level %s -> will recompress to %s",
                    cur,
                    args.level,
                )
        except Exception:
            logger.debug("Failed to detect existing nsz level for %s", filepath)

    if should_recompress:
        if args.dry_run:
            return filepath
        try:
            print("   🗜️  Recomprimindo (ajuste de nível)...", end="", flush=True)
            with tempfile.TemporaryDirectory(prefix="nsz_recomp_") as td:
                tmpdir = Path(td)
                attempts = [
                    [
                        str(tool_nsz),
                        "-C",
                        "-l",
                        str(args.level),
                        "-o",
                        str(tmpdir),
                        str(filepath),
                    ],
                    [
                        str(tool_nsz),
                        "-C",
                        "-l",
                        str(args.level),
                        str(filepath),
                        "-o",
                        str(tmpdir),
                    ],
                    [
                        str(tool_nsz),
                        "-C",
                        "-l",
                        str(args.level),
                        str(filepath),
                    ],
                ]
                # delegate attempts execution to compression helper
                from emumanager.switch.compression import (
                    try_multiple_recompress_attempts,
                    handle_produced_file,
                )

                produced = try_multiple_recompress_attempts(
                    tmpdir,
                    attempts,
                    lambda *a, **k: run_cmd(
                        a[0],
                        filebase=Path(roms_dir)
                        / "logs"
                        / "nsz"
                        / (filepath.stem + ".recomp"),
                        timeout=cmd_timeout,
                    ),
                    progress_callback=getattr(args, "progress_callback", None),
                )

                if produced:
                    new_file = produced[0]
                    try:
                        result_path = handle_produced_file(
                            new_file,
                            filepath,
                            lambda *a, **k: run_cmd(
                                a[0],
                                filebase=Path(roms_dir)
                                / "logs"
                                / "nsz"
                                / (filepath.stem + ".recomp"),
                                timeout=cmd_timeout,
                            ),
                            verify_fn=lambda p, rc: verify_integrity(
                                p,
                                deep=False,
                                tool_nsz=tool_nsz,
                                roms_dir=roms_dir,
                                cmd_timeout=cmd_timeout,
                                tool_metadata=tool_metadata,
                                is_nstool=is_nstool,
                                keys_path=keys_path,
                                tool_hactool=tool_hactool,
                            ),
                            args=args,
                            roms_dir=roms_dir,
                        )
                        if result_path == filepath:
                            print(f" {Col.GREEN}[OK]{Col.RESET}")
                            logger.info(
                                "Recompression succeeded and file replaced: %s",
                                filepath.name,
                            )
                            return filepath
                        # if returned other path, return it as candidate
                        return result_path
                    except Exception:
                        logger.exception(
                            "Error handling recompressed file for %s", filepath
                        )
                        return filepath

            print(f" {Col.RED}[FALHA]{Col.RESET}")
            return filepath
        except Exception as e:
            logger.exception(f"recompress failed for {filepath}: {e}")
            print(f" {Col.RED}[FALHA]{Col.RESET}")
            return filepath
    return filepath


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

        compressed_candidate = compress_file(
            filepath,
            lambda *a, **k: run_cmd(
                a[0],
                filebase=Path(roms_dir)
                / "logs"
                / "nsz"
                / (filepath.stem + ".compress"),
                timeout=cmd_timeout,
                check=k.get("check", False),
            ),
            tool_nsz=str(tool_nsz),
            level=args.level,
            args=args,
            roms_dir=Path(roms_dir),
        )

        if not compressed_candidate:
            print(f" {Col.RED}[FALHA]{Col.RESET}")
            return filepath

        print(f" {Col.GREEN}[OK]{Col.RESET}")

        # If user requested removal of originals, verify compressed file and then
        # remove source
        if args.rm_originals and not args.dry_run and compressed_candidate:
            try:
                if (
                    compressed_candidate.exists()
                    and compressed_candidate.stat().st_size > 0
                ):
                    ok = True
                    try:
                        ok = verify_integrity(
                            compressed_candidate,
                            deep=False,
                            tool_nsz=tool_nsz,
                            roms_dir=roms_dir,
                            cmd_timeout=cmd_timeout,
                            tool_metadata=tool_metadata,
                            is_nstool=is_nstool,
                            keys_path=keys_path,
                            tool_hactool=tool_hactool,
                        )
                    except Exception:
                        ok = True
                    if ok:
                        try:
                            filepath.unlink()
                            logger.info(
                                "Original removido após compressão bem-sucedida: "
                                "%s",
                                filepath.name,
                            )
                            logger.debug(
                                "Original removido (caminho completo): %s",
                                filepath,
                            )
                        except Exception:
                            logger.exception(
                                "Falha ao remover arquivo original depois de "
                                "comprimir: %s",
                                filepath,
                            )
                    else:
                        logger.warning(
                            "Compressed file generated but failed verification: %s",
                            compressed_candidate,
                        )
                        if getattr(args, "keep_on_failure", False):
                            try:
                                qdir = args.quarantine_dir
                                if qdir:
                                    quarantine_dir = Path(qdir).resolve()
                                else:
                                    quarantine_dir = roms_dir / "_QUARANTINE"
                                if not args.dry_run:
                                    quarantine_dir.mkdir(parents=True, exist_ok=True)
                                    dest = quarantine_dir / compressed_candidate.name
                                    shutil.move(str(compressed_candidate), str(dest))
                                    logger.info(
                                        "Moved failed compressed artifact to "
                                        "quarantine: %s",
                                        dest,
                                    )
                            except Exception:
                                logger.exception(
                                    "Failed moving failed compressed artifact to "
                                    "quarantine: %s",
                                    compressed_candidate,
                                )
            except Exception:
                logger.exception(
                    "Error while validating/removing original for %s", filepath
                )

        return compressed_candidate or filepath.with_suffix(".nsz")
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
def main(argv: Optional[List[str]] = None):
    args = parser.parse_args(argv)

    # Install signal handlers for graceful shutdown
    try:
        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)
    except Exception:
        logger.debug("Could not install signal handlers")

    # Apply compression profile if provided: it overrides numeric --level
    try:
        if getattr(args, "compression_profile", None):
            prof = args.compression_profile
            if prof in COMPRESSION_PROFILE_LEVELS:
                args.level = COMPRESSION_PROFILE_LEVELS[prof]
                logger.info(
                    "Compression profile '%s' selected -> level %s",
                    prof,
                    args.level,
                )
            else:
                logger.warning(
                    "Unknown compression profile '%s', keeping --level=%s",
                    prof,
                    args.level,
                )
    except Exception:
        logger.exception("Error while applying compression_profile")

    # Validate numeric level bounds (1-22)
    try:
        lvl = int(args.level)
        if lvl < 1:
            logger.warning("Compression level %s too low; adjusting to 1", lvl)
            lvl = 1
        if lvl > 22:
            logger.warning("Compression level %s above allowed; adjusting to 22", lvl)
            lvl = 22
        args.level = lvl
    except Exception:
        logger.warning("Invalid compression level; using 1")
        args.level = 1

    if args.compress and args.decompress:
        sys.exit(f"{Col.RED}Erro: Escolha --compress OU --decompress.{Col.RESET}")

    # adjust logging level from CLI
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Detect tools and configure environment
    from emumanager.switch.main_helpers import configure_environment

    env = configure_environment(args, logger, find_tool)
    ROMS_DIR = env["ROMS_DIR"]
    KEYS_PATH = env["KEYS_PATH"]
    CSV_FILE = env["CSV_FILE"]
    TOOL_HACTOOL = env["TOOL_HACTOOL"]
    TOOL_NSZ = env["TOOL_NSZ"]
    TOOL_CLAMSCAN = env["TOOL_CLAMSCAN"]
    TOOL_CLAMDSCAN = env["TOOL_CLAMDSCAN"]
    TOOL_METADATA = env["TOOL_METADATA"]
    IS_NSTOOL = env["IS_NSTOOL"]

    setup_logging(args.log_file, args.verbose)
    logger.info("Starting Switch Organizer")
    logger.info("Directory: %s", ROMS_DIR)

    files = [
        f
        for f in ROMS_DIR.rglob("*")
        if f.suffix.lower() in {".xci", ".nsp", ".nsz", ".xcz"} and f.is_file()
    ]
    if not files:
        logger.info(
            "Nenhum arquivo .xci/.nsp/.nsz/.xcz encontrado no diretório especificado."
        )
        return

    # Prepare catalog/stats and optionally run health-check mode.
    catalog: List[List[Any]] = []
    stats = {"ok": 0, "erro": 0, "skipped": 0}

    # Create closures for dependencies to pass to helpers
    def verify_integrity_fn(f, **k):
        return verify_integrity(
            f,
            tool_nsz=TOOL_NSZ,
            roms_dir=ROMS_DIR,
            cmd_timeout=getattr(args, "cmd_timeout", None),
            tool_metadata=TOOL_METADATA,
            is_nstool=IS_NSTOOL,
            keys_path=KEYS_PATH,
            tool_hactool=TOOL_HACTOOL,
            **k,
        )

    def scan_for_virus_fn(f):
        return scan_for_virus(
            f,
            tool_clamscan=TOOL_CLAMSCAN,
            tool_clamdscan=TOOL_CLAMDSCAN,
            roms_dir=ROMS_DIR,
            cmd_timeout=getattr(args, "cmd_timeout", None),
        )

    def safe_move_fn(s, d):
        return safe_move(s, d, args=args, logger=logger)

    def get_metadata_fn(f):
        return get_metadata(
            f,
            tool_metadata=TOOL_METADATA,
            is_nstool=IS_NSTOOL,
            keys_path=KEYS_PATH,
            roms_dir=ROMS_DIR,
            tool_nsz=TOOL_NSZ,
            cmd_timeout=getattr(args, "cmd_timeout", None),
        )

    def handle_compression_fn(f):
        return handle_compression(
            f,
            args=args,
            tool_nsz=TOOL_NSZ,
            roms_dir=ROMS_DIR,
            tool_metadata=TOOL_METADATA,
            is_nstool=IS_NSTOOL,
            keys_path=KEYS_PATH,
            cmd_timeout=getattr(args, "cmd_timeout", None),
            tool_hactool=TOOL_HACTOOL,
        )

    # If health-check mode requested, run quick integrity + virus scan pass and exit.
    if args.health_check:
        # Delegate the health-check to the extracted helper to keep main readable
        from emumanager.switch.main_helpers import run_health_check

        hc_summary = run_health_check(
            files,
            args,
            ROMS_DIR,
            verify_integrity_fn,
            scan_for_virus_fn,
            safe_move_fn,
            logger,
        )
        # If user only requested health-check (no other actions), exit with code
        # on problems
        other_actions = any(
            [args.organize, args.compress, args.decompress, args.clean_junk]
        )

        if not other_actions:
            problems = bool(hc_summary.get("corrupted") or hc_summary.get("infected"))
            sys.exit(1 if problems else 0)

    # Delegate file processing to extracted helper to reduce main size
    from emumanager.switch.main_helpers import process_files

    ctx = {
        "args": args,
        "ROMS_DIR": ROMS_DIR,
        "CSV_FILE": CSV_FILE,
        "get_metadata": get_metadata_fn,
        "sanitize_name": sanitize_name,
        "determine_region": determine_region,
        "determine_type": determine_type,
        "parse_languages": parse_languages,
        "detect_languages_from_filename": detect_languages_from_filename,
        "safe_move": safe_move_fn,
        "verify_integrity": verify_integrity_fn,
        "scan_for_virus": scan_for_virus_fn,
        "handle_compression": handle_compression_fn,
        "TOOL_METADATA": TOOL_METADATA,
        "IS_NSTOOL": IS_NSTOOL,
        "logger": logger,
        "Col": Col,
        "TITLE_ID_RE": TITLE_ID_RE,
    }

    catalog, stats = process_files(files, ctx)

    print("\n" + "=" * 75)

    # --- FINALIZAÇÃO ---
    if catalog and not args.dry_run:
        try:
            with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "Nome",
                        "TitleID",
                        "Tipo",
                        "Versão",
                        "Região",
                        "Idiomas",
                        "Formato",
                        "Caminho",
                    ]
                )
                writer.writerows(catalog)
            print(
                f"📊 Catálogo salvo em: {Col.YELLOW}{CSV_FILE.name}{Col.RESET}"
            )
        except Exception as e:
            logger.exception(f"Erro ao salvar CSV: {e}")

    if args.clean_junk and not args.dry_run:
        print("🧹 Limpando lixo...")
        for junk in ROMS_DIR.rglob("*"):
            if junk.suffix.lower() in {
                ".txt",
                ".nfo",
                ".url",
                ".lnk",
                ".website",
            }:
                try:
                    from emumanager.common.fileops import safe_unlink

                    safe_unlink(junk, logger)
                except Exception as e:
                    logger.debug(f"failed to remove junk {junk}: {e}")

        # Remove pastas vazias (ordem reversa para apagar subpastas primeiro)
        all_dirs = sorted(
            [p for p in ROMS_DIR.rglob("*") if p.is_dir()],
            key=lambda p: str(p),
            reverse=True,
        )
        for p in all_dirs:
            try:
                if not any(p.iterdir()):
                    p.rmdir()
            except Exception as e:
                logger.debug(f"failed to remove dir {p}: {e}")

    print(
        f"{Col.GREEN}✅ Sucesso: {stats['ok']} | "
        f"⚠️  Pulos/Dups: {stats['skipped']} | "
        f"❌ Erros: {stats['erro']}{Col.RESET}"
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        # argparse or explicit sys.exit calls
        raise
    except Exception:
        logger.exception("Unexpected fatal error while running script")
        sys.exit(2)
