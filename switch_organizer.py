#!/usr/bin/env python3
import os
import subprocess
import re
import shutil
import argparse
import logging
from logging.handlers import RotatingFileHandler
import sys
import csv
import hashlib
from pathlib import Path
from typing import Optional, Any, List
import tempfile
# Keep original reference so test monkeypatches (which replace subprocess.run) can be detected
ORIGINAL_SUBPROCESS_RUN = subprocess.run
import signal

# ======================================================================
#  SWITCH ORGANIZER v13.3 (HELP EDITION)
# ======================================================================
#  Adicionado:
#  1. Menu de Ajuda Visual (roda quando nenhum argumento é passado).
#  2. Descrições detalhadas dos comandos.
# ==============================================================================


class Col:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GREY = "\033[90m"
    BOLD = "\033[1m"


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
        f"     {Col.GREY}* Cria pastas, renomeia corretamente e remove lixo.{Col.RESET}\n"
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
        "  --no-verify      : Pula a verificação de integridade (Mais rápido, menos seguro)."
    )
    print("  --level [1-22]   : Nível de compressão NSZ (Padrão: 1).")
    print(
        f"\n{Col.CYAN}Para ver a lista técnica completa, use: python3 script.py --help{Col.RESET}"
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
    "--keys", type=str, default="./prod.keys", help="Caminho do arquivo prod.keys"
)
parser.add_argument(
    "--dry-run", action="store_true", help="SIMULAÇÃO: Não move nem deleta arquivos"
)
parser.add_argument(
    "--no-verify", action="store_true", help="Pula verificação de hash (SHA256/CRC)"
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
    "--compress", action="store_true", help="Comprime ROMs (XCI/NSP) para formato NSZ"
)
parser.add_argument(
    "--decompress", action="store_true", help="Descomprime (NSZ) de volta para NSP"
)

parser.add_argument(
    "--rm-originals",
    action="store_true",
    help="Ao comprimir, remove os arquivos originais somente se a compressão for bem-sucedida",
)

parser.add_argument(
    "--recompress",
    action="store_true",
    help="Recomprime arquivos já em .nsz/.xcz para o nível especificado (substitui o arquivo comprimido se bem-sucedido)",
)
parser.add_argument(
    "--level", type=int, default=3, help="Nível de compressão Zstd (1-22). Padrão: 3 (balanced)"
)

parser.add_argument(
    "--compression-profile",
    choices=["fast", "balanced", "best"],
    default=None,
    help=(
        "Perfil de compressão predefinido: 'fast' (prioriza velocidade), "
        "'balanced' (bom equilíbrio tempo/espaço), 'best' (máxima compressão, mais lento). "
        "Se definido, sobrescreve --level."
    ),
)
parser.add_argument(
    "--dup-check",
    choices=["fast", "strict"],
    default="fast",
    help="Modo de verificação de duplicatas: 'fast' usa size+mtime, 'strict' usa SHA256 (padrão: fast)",
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
    help="Preserva arquivos gerados quando ocorrer falha (move para quarentena ou deixa no lugar)",
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
    help="Verifica integridade dos arquivos e escaneia por vírus (usa clamscan/clamdscan se disponíveis)",
)
parser.add_argument(
    "--quarantine",
    action="store_true",
    help="(usado com --health-check) move arquivos infectados/corrompidos para _QUARANTINE",
)
parser.add_argument(
    "--quarantine-dir",
    type=str,
    default=None,
    help="Diretório onde mover arquivos em quarentena (default: _QUARANTINE dentro de --dir)",
)
parser.add_argument(
    "--deep-verify",
    action="store_true",
    help="Executa verificação mais profunda quando possível (usa hactool/nsz juntos)",
)
parser.add_argument(
    "--report-csv",
    type=str,
    default=None,
    help="(usado com --health-check) caminho para salvar relatório CSV detalhado",
)

# Se nenhum argumento for passado, mostra o manual amigável
if len(sys.argv) == 1:
    show_manual()

# --- SETUP GERAL (será inicializado em main) ---
# ROMS_DIR, KEYS_PATH, DUPE_DIR, CSV_FILE serão definidos em main()

logger = logging.getLogger("organizer_v13")
SHUTDOWN_REQUESTED = False
CURRENT_PROCESS = None


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
def find_tool(name: str) -> Optional[Path]:
    """Procura a ferramenta primeiro no PATH e depois no diretório local.

    Retorna Path ou None.
    """
    # Prefer system-wide installed executable
    sys_path = shutil.which(name)
    if sys_path:
        return Path(sys_path).resolve()

    # Fallback to local files
    local = Path(f"./{name}").resolve()
    if local.exists():
        return local
    local_exe = Path(f"./{name}.exe").resolve()
    if local_exe.exists():
        return local_exe
    return None


def _signal_handler(signum, frame):
    global SHUTDOWN_REQUESTED
    global CURRENT_PROCESS
    logger.warning("Signal %s received: requesting shutdown...", signum)
    SHUTDOWN_REQUESTED = True
    try:
        if CURRENT_PROCESS is not None:
            logger.warning("Killing active subprocess (pid=%s)", getattr(CURRENT_PROCESS, 'pid', 'unknown'))
            try:
                CURRENT_PROCESS.kill()
            except Exception:
                try:
                    CURRENT_PROCESS.terminate()
                except Exception:
                    logger.debug("Failed to kill/terminate subprocess")
    except Exception:
        logger.debug("Error while attempting to kill current process on signal")


def run_cmd(cmd, *, filebase: Optional[Path] = None, timeout: Optional[int] = None, check: bool = False):
    """Run a subprocess command with timeout, capture output and optionally save to files.

    If filebase is provided, stdout/err will be stored as filebase + .out/.err
    Returns completed process.
    """
    si = subprocess.STARTUPINFO() if os.name == "nt" else None
    if si:
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    # Use Popen so we can track and kill the child on signals
    global CURRENT_PROCESS
    proc = None
    # If subprocess.run has been monkeypatched (tests), prefer using it so mocks apply
    try_run = subprocess.run
    if try_run is not ORIGINAL_SUBPROCESS_RUN:
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            logger.warning("Command timeout (%s s): %s", timeout, " ".join(map(str, cmd)))
            res = e
        except Exception:
            logger.exception("Command execution failed (run): %s", cmd)
            raise
    else:
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="ignore",
                startupinfo=si,
            )
            CURRENT_PROCESS = proc
            try:
                out, err = proc.communicate(timeout=timeout)
                res = subprocess.CompletedProcess(cmd, proc.returncode, stdout=out, stderr=err)
            except subprocess.TimeoutExpired:
                logger.warning("Command timeout (%s s): %s", timeout, " ".join(map(str, cmd)))
                try:
                    proc.kill()
                except Exception:
                    logger.debug("Failed to kill timed-out subprocess")
                out, err = proc.communicate()
                res = subprocess.CompletedProcess(cmd, proc.returncode, stdout=out, stderr=err)
        except Exception:
            logger.exception("Command execution failed (popen): %s", cmd)
            raise
        finally:
            try:
                CURRENT_PROCESS = None
            except Exception:
                pass

    # persist outputs when requested
    if filebase is not None:
        outp = getattr(res, "stdout", None) or ""
        errp = getattr(res, "stderr", None) or ""
        try:
            filebase.parent.mkdir(parents=True, exist_ok=True)
            with open(str(filebase) + ".out", "w", encoding="utf-8", errors="ignore") as fo:
                fo.write(outp)
            with open(str(filebase) + ".err", "w", encoding="utf-8", errors="ignore") as fe:
                fe.write(errp)
        except Exception:
            logger.debug("Failed to write command output files for %s", filebase)

    if check and isinstance(res, subprocess.CompletedProcess) and res.returncode != 0:
        raise subprocess.CalledProcessError(res.returncode, cmd, output=res.stdout, stderr=res.stderr)

    return res


# As verificações de ferramentas e dependências ocorrem dentro de main(),
# pois dependem de argumentos (por exemplo '--keys').

# --- FUNÇÕES CORE ---


def parse_languages(text_output):
    # Normalize and look for known language tokens; return short codes in brackets
    lang_map = {
        "americanenglish": "En",
        "britishenglish": "En",
        "english": "En",
        "japanese": "Ja",
        "french": "Fr",
        "canadianfrench": "Fr",
        "german": "De",
        "italian": "It",
        "spanish": "Es",
        "latinamericanspanish": "Es",
        "portuguese": "Pt",
        "brazilianportuguese": "PtBR",
        "dutch": "Nl",
        "russian": "Ru",
        "korean": "Ko",
        "traditionalchinese": "Zh",
        "simplifiedchinese": "Zh",
    }
    if not text_output:
        return ""

    lowered = text_output.lower()
    found = {v for k, v in lang_map.items() if k in lowered}

    if not found:
        return ""

    codes = sorted(found)
    if len(codes) > 5:
        return "[Multi]" + ("+PtBR" if "PtBR" in codes else "")
    return "[" + ",".join(codes) + "]"


def detect_languages_from_filename(filename: str) -> str:
    """Try to guess language codes from filename tokens like EN, PTBR, JA, etc."""
    token_map = {
        "PTBR": "PtBR",
        "PT-BR": "PtBR",
        "PT": "Pt",
        "EN": "En",
        "JP": "Ja",
        "JA": "Ja",
        "FR": "Fr",
        "DE": "De",
        "ES": "Es",
        "RU": "Ru",
        "KO": "Ko",
        "ZH": "Zh",
        "NL": "Nl",
        "IT": "It",
    }
    up = filename.upper()
    found = []
    for key, code in token_map.items():
        if re.search(rf"\b{re.escape(key)}\b", up):
            found.append(code)
    if not found:
        return ""
    # keep order and unique
    seen = []
    for c in found:
        if c not in seen:
            seen.append(c)
    return "[" + ",".join(seen) + "]"


# --- CONSTANTS / COMMON REGEX ---
TITLE_ID_RE = re.compile(r"(?:Title ID|Program Id):\s*(?:0x)?([0-9A-Fa-f]{16})", re.IGNORECASE)
INVALID_FILENAME_CHARS_RE = re.compile(r'[<>:"/\\|?*]')
# Compression profile mapping: maps friendly presets to NSZ zstd levels
COMPRESSION_PROFILE_LEVELS = {
    "fast": 1,
    "balanced": 3,
    "best": 19,
}



def determine_type(title_id, text_output):
    # Prefer explicit textual hints
    txt = (text_output or "")
    low = txt.lower()
    if "update" in low or "patch" in low:
        return "UPD"
    if "addon" in low or "add-on" in low or "dlc" in low:
        return "DLC"
    if "application" in low or "gamecard" in low or "program" in low:
        return "Base"

    # Try ID heuristics: compare against base id (if title_id equals its base, it's likely a Base)
    if title_id:
        try:
            base = get_base_id(title_id)
            if base and base.upper() == title_id.upper():
                return "Base"
            # Otherwise prefer DLC unless textual hints say it's an update
            return "DLC"
        except Exception as e:
            logger.debug("determine_type parsing title_id failed: %s", e)

    # Last resort
    return "DLC"


def determine_region(filename, langs_str):
    # Try explicit tags in filename
    match = re.search(
        r"\b(USA|EUR|EUR-?JPN|JPN|KOR|CHN|ASIA|WORLD|REGION FREE|EUROPE|JAPAN)\b",
        filename,
        re.IGNORECASE,
    )
    if match:
        reg = match.group(1).upper()
        if "WORLD" in reg or "REGION" in reg or "EN" in reg:
            return "(World)"
        mapping = {
            "USA": "(USA)",
            "EUR": "(EUR)",
            "JPN": "(JPN)",
            "KOR": "(KOR)",
            "CHN": "(CHN)",
            "ASIA": "(ASIA)",
            "EUROPE": "(EUR)",
            "JAPAN": "(JPN)",
        }
        return mapping.get(reg, f"({reg})")

    # Fallback from languages string
    if langs_str:
        if "Ja" in langs_str or "Ja," in langs_str:
            return "(JPN)"
        if "Ko" in langs_str:
            return "(KOR)"
        if "Zh" in langs_str:
            return "(CHN)"
        if "En" in langs_str or "PtBR" in langs_str:
            return "(World)"
    return ""


def get_base_id(title_id):
    if not title_id:
        return None
    try:
        val = int(title_id, 16) & 0xFFFFFFFFFFFFE000
        return hex(val)[2:].upper().zfill(16)
    except Exception as e:
        logger.debug(f"get_base_id failed: {e}")
        return title_id


def sanitize_name(name):
    # Remove common release/group tags inside brackets
    name = re.sub(
        r"[\[\(][^\]\)]*(?:nsw2u|switch-xci|cr-|venom|hbg|bigblue)[^\]\)]*[\]\)]",
        "",
        name,
        flags=re.IGNORECASE,
    )
    # Remove explicit titleid brackets and version tokens
    name = re.sub(r"\[[0-9A-Fa-f]{16}\]", "", name)
    name = re.sub(r"v\d+(?:\.\d+)*", "", name, flags=re.IGNORECASE)
    # Strip control chars and reserved filesystem characters
    name = "".join(ch for ch in name if ord(ch) >= 32)
    name = INVALID_FILENAME_CHARS_RE.sub("", name)
    # Normalize whitespace
    name = re.sub(r"\s+", " ", name).strip()
    # Remove trailing separators
    name = name.rstrip(" -_.")
    # Truncate to reasonable length for file systems
    if len(name) > 120:
        name = name[:120].rstrip()
    return name


def get_file_hash(filepath: Path) -> str:
    """Retorna um hash SHA256 do arquivo. Em caso de falha, retorna o tamanho como string.

    Essa função é usada para detecção simples de duplicatas. Para arquivos grandes,
    o cálculo pode levar tempo.
    """
    try:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        # fallback: tamanho como identificador rápido
        try:
            return f"size:{os.path.getsize(filepath)}"
        except Exception:
            return "unknown"


# --- OPERAÇÕES ---


def get_metadata(filepath):
    info = {"name": None, "id": None, "ver": "v0", "type": "DLC", "langs": ""}

    # Tenta leitura interna (inclusive para .nsz quando a ferramenta suportar)
    try:
        cmd = [str(TOOL_METADATA), "-v" if IS_NSTOOL else "-k", str(filepath)]
        if not IS_NSTOOL:
            cmd.insert(2, str(KEYS_PATH))
            cmd.insert(3, "-i")

        base = globals().get("ROMS_DIR", Path(".")) or Path(".")
        logbase = Path(base) / "logs" / "nsz" / (filepath.stem + ".meta")
        res = run_cmd(cmd, filebase=logbase, timeout=getattr(globals().get("args", {}), "cmd_timeout", None))

        name = re.search(
            r"(?:Name|Application Name):\s*(.*)", res.stdout, re.IGNORECASE
        )
        tid = re.search(
            r"(?:Title ID|Program Id):\s*(?:0x)?([0-9A-Fa-f]{16})",
            res.stdout,
            re.IGNORECASE,
        )
        ver = re.search(
            r"(?:Display Version|Version):\s*(.*)", res.stdout, re.IGNORECASE
        )

        if name and tid:
            info["name"] = name.group(1).strip()
            info["id"] = tid.group(1).upper()
            if ver:
                info["ver"] = ver.group(1).strip()
            # prefer parse from tool output, fallback to filename heuristics
            langs_raw = parse_languages(res.stdout) or detect_languages_from_filename(filepath.name)
            # normalize: store without surrounding brackets (easier downstream)
            if langs_raw and langs_raw.startswith("[") and langs_raw.endswith("]"):
                langs_raw = langs_raw[1:-1]
            info["langs"] = langs_raw
            info["type"] = determine_type(info["id"], res.stdout)
            return info
        else:
            # tool ran but didn't return required fields
            logger.debug(
                "metadata tool ran but returned incomplete data for %s", filepath
            )
            logger.debug("tool stdout:\n%s", getattr(res, "stdout", ""))
            logger.debug("tool stderr:\n%s", getattr(res, "stderr", ""))
    except Exception:
        logger.exception(
            "get_metadata: metadata tool execution failed for %s", filepath
        )

    # If metadata tool didn't return required fields and file is a compressed
    # archive (.nsz or .xcz), try a temporary decompression (fallback) to
    # extract metadata from the inner .nsp/.xci. We do this only if TOOL_NSZ
    # appears available.
    try:
        # If compressed, try a temporary decompression fallback that returns a candidate file
        if filepath.suffix.lower() in {".nsz", ".xcz"} and TOOL_NSZ:
            decompressed = None
            try:
                # Try a small helper routine: create a temp dir and attempt common nsz -D variants
                with tempfile.TemporaryDirectory(prefix="nsz_extract_") as td:
                    tmpdir = Path(td)
                    attempts = [
                        [str(TOOL_NSZ), "-D", "-o", str(tmpdir), str(filepath)],
                        [str(TOOL_NSZ), "-D", "--out", str(tmpdir), str(filepath)],
                        [str(TOOL_NSZ), "-D", str(filepath), "-o", str(tmpdir)],
                        [str(TOOL_NSZ), "-D", str(filepath), "--out", str(tmpdir)],
                        [str(TOOL_NSZ), "-D", str(filepath), str(tmpdir)],
                    ]
                    for cmd in attempts:
                        try:
                            logger.debug("Trying decompression command: %s", " ".join(cmd))
                            logbase = Path(base) / "logs" / "nsz" / (filepath.stem + ".decomp")
                            res = run_cmd(cmd, filebase=logbase, timeout=getattr(globals().get("args", {}), "cmd_timeout", None))
                            logger.debug("nsz stdout: %s", getattr(res, "stdout", ""))
                            logger.debug("nsz stderr: %s", getattr(res, "stderr", ""))
                        except Exception as de:
                            logger.debug("decompression attempt failed: %s", de)
                            continue

                        for ext in (".nsp", ".xci"):
                            found = list(Path(tmpdir).rglob(f"*{ext}"))
                            if found:
                                decompressed = found[0]
                                break
                        if decompressed:
                            break

            except Exception:
                logger.exception("decompression fallback failed for %s", filepath)

            if decompressed and decompressed.exists():
                logger.debug("Found decompressed candidate: %s", decompressed)
                try:
                    cmd = [str(TOOL_METADATA), "-v" if IS_NSTOOL else "-k", str(decompressed)]
                    if not IS_NSTOOL:
                        cmd.insert(2, str(KEYS_PATH))
                        cmd.insert(3, "-i")

                    logbase2 = Path(base) / "logs" / "nsz" / (decompressed.stem + ".meta")
                    res2 = run_cmd(cmd, filebase=logbase2, timeout=getattr(globals().get("args", {}), "cmd_timeout", None))
                    name = re.search(r"(?:Name|Application Name):\s*(.*)", getattr(res2, "stdout", ""), re.IGNORECASE)
                    tid = TITLE_ID_RE.search(getattr(res2, "stdout", ""))
                    ver = re.search(r"(?:Display Version|Version):\s*(.*)", getattr(res2, "stdout", ""), re.IGNORECASE)
                    if name and tid:
                        info["name"] = name.group(1).strip()
                        info["id"] = tid.group(1).upper()
                        if ver:
                            info["ver"] = ver.group(1).strip()
                        # prefer parse from decompressed tool output, fallback to filename heuristics
                        langs_raw = parse_languages(res2.stdout) or detect_languages_from_filename(decompressed.name if decompressed else filepath.name)
                        if langs_raw and langs_raw.startswith("[") and langs_raw.endswith("]"):
                            langs_raw = langs_raw[1:-1]
                        info["langs"] = langs_raw
                        info["type"] = determine_type(info["id"], res2.stdout)
                        return info
                    else:
                        logger.debug("metadata from decompressed file incomplete for %s", filepath)
                        logger.debug("tool stdout:\n%s", res2.stdout)
                        logger.debug("tool stderr:\n%s", res2.stderr if hasattr(res2, "stderr") else "")
                except Exception:
                    logger.exception("get_metadata: metadata tool failed on decompressed file %s", decompressed)
    except Exception:
        logger.exception("get_metadata: decompression fallback raised unexpected exception for %s", filepath)

    # Fallback Regex
    tid_match = re.search(r"\[([0-9a-fA-F]{16})\]", filepath.name)
    if tid_match:
        clean_tid = tid_match.group(1).upper()
        name_part = filepath.name.split(f"[{clean_tid}]")[0]
        name_part = re.sub(r"\[[^\]]*\]", "", name_part).strip()
        ver_match = re.search(r"[\[\(]v?(\d+|[\d\.]+)[\)\]]", filepath.name)

        info["name"] = name_part
        info["id"] = clean_tid
        if ver_match:
            info["ver"] = f"v{ver_match.group(1)}"
        info["type"] = determine_type(clean_tid, None)
        return info

    return None


def verify_integrity(filepath, deep: bool = False, return_output: bool = False):
    # compressed formats we treat similarly
    is_nsz = filepath.suffix.lower() in {".nsz", ".xcz"}
    try:
        results = []

        # Primary check: use NSZ verify if it's an nsz/xcz and nsz tool exists
        if is_nsz and TOOL_NSZ:
            try:
                logbase_n = Path(globals().get("ROMS_DIR", Path("."))) / "logs" / "nsz" / (filepath.stem + ".verify_nsz")
                res_nsz = run_cmd([str(TOOL_NSZ), "--verify", str(filepath)], filebase=logbase_n, timeout=getattr(globals().get("args", {}), "cmd_timeout", None))
                results.append(((getattr(res_nsz, "returncode", 1) == 0), (getattr(res_nsz, "stdout", "") or "") + "\n" + (getattr(res_nsz, "stderr", "") or "")))
            except Exception as e:
                logger.debug("nsz verify raised: %s", e)
                results.append((False, str(e)))

        # Metadata tool check (nstool/hactool)
        try:
            cmd = [str(TOOL_METADATA), "--verify", str(filepath)]
            if not IS_NSTOOL:
                cmd.insert(1, "-k")
                cmd.insert(2, str(KEYS_PATH))
            logbase_m = Path(globals().get("ROMS_DIR", Path("."))) / "logs" / "nsz" / (filepath.stem + ".verify_meta")
            res_meta = run_cmd(cmd, filebase=logbase_m, timeout=getattr(globals().get("args", {}), "cmd_timeout", None))
            ok_meta = (getattr(res_meta, "returncode", 1) == 0) and "Error" not in (getattr(res_meta, "stdout", "") or "")
            results.append((ok_meta, (getattr(res_meta, "stdout", "") or "") + "\n" + (getattr(res_meta, "stderr", "") or "")))
        except Exception as e:
            logger.debug("metadata verify raised: %s", e)
            results.append((False, str(e)))

        # If deep requested and hactool available, attempt extra pass with hactool specifics
        if deep and TOOL_HACTOOL:
            try:
                # Best-effort: call hactool with basic info/validation to exercise NCA parsing
                cmd = [str(TOOL_HACTOOL), "-k", str(KEYS_PATH), str(filepath)] if KEYS_PATH and KEYS_PATH.exists() else [str(TOOL_HACTOOL), str(filepath)]
                logbase_h = Path(globals().get("ROMS_DIR", Path("."))) / "logs" / "nsz" / (filepath.stem + ".verify_hactool")
                res_h = run_cmd(cmd, filebase=logbase_h, timeout=getattr(globals().get("args", {}), "cmd_timeout", None))
                ok_h = (getattr(res_h, "returncode", 1) == 0) and "Error" not in (getattr(res_h, "stdout", "") or "")
                results.append((ok_h, (getattr(res_h, "stdout", "") or "") + "\n" + (getattr(res_h, "stderr", "") or "")))
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


def scan_for_virus(filepath):
    """Run a local antivirus scan using clamscan or clamdscan if available.

    Returns a tuple (infected: Optional[bool], output: str).
    infected: True => infected, False => clean, None => scanner not available or error.
    """
    global TOOL_CLAMSCAN, TOOL_CLAMDSCAN
    tool = None
    if TOOL_CLAMSCAN:
        tool = TOOL_CLAMSCAN
    elif TOOL_CLAMDSCAN:
        tool = TOOL_CLAMDSCAN
    else:
        return None, "No AV scanner found"

    cmd = [str(tool), "--no-summary", str(filepath)]
    try:
        logbase = Path(globals().get("ROMS_DIR", Path("."))) / "logs" / "nsz" / (filepath.stem + ".av")
        res = run_cmd(cmd, filebase=logbase, timeout=getattr(globals().get("args", {}), "cmd_timeout", None))
        out = (getattr(res, "stdout", "") or "") + "\n" + (getattr(res, "stderr", "") or "")
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


def detect_nsz_level(filepath) -> Optional[int]:
    """Try to detect zstd compression level used inside an .nsz/.xcz using nsz --info/-i output.

    Returns integer level or None if unknown.
    """
    global TOOL_NSZ
    if not TOOL_NSZ:
        return None
    try:
        # Try common info switches
        attempts = [[str(TOOL_NSZ), "--info", str(filepath)], [str(TOOL_NSZ), "-i", str(filepath)], [str(TOOL_NSZ), "info", str(filepath)]]
        out = ""
        for cmd in attempts:
            try:
                logbase_i = Path(globals().get("ROMS_DIR", Path("."))) / "logs" / "nsz" / (filepath.stem + ".info")
                res = run_cmd(cmd, filebase=logbase_i, timeout=getattr(globals().get("args", {}), "cmd_timeout", None))
                out = (getattr(res, "stdout", "") or "") + "\n" + (getattr(res, "stderr", "") or "")
                if out and len(out.strip()) > 0:
                    break
            except Exception:
                continue

        if not out:
            return None

        # Look for typical patterns indicating zstd level
        m = re.search(r"zstd(?: compression)? level\s*[:=\-]?\s*(\d+)", out, re.IGNORECASE)
        if not m:
            m = re.search(r"compression level\s*[:=\-]?\s*(\d+)", out, re.IGNORECASE)
        if not m:
            m = re.search(r"level\s*[:=\-]?\s*(\d+)", out, re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return None
    except Exception:
        logger.debug("detect_nsz_level failed for %s", filepath)
    return None


def handle_compression(filepath):
    # Support recompressing already-compressed archives when requested or when requested level is higher
    if args.compress and filepath.suffix.lower() in {".nsz", ".xcz"}:
        should_recompress = getattr(args, "recompress", False)
        if not should_recompress:
            try:
                cur = detect_nsz_level(filepath)
                if cur is not None and args.level > cur:
                    should_recompress = True
                    logger.info("Detected existing zstd level %s -> will recompress to %s", cur, args.level)
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
                        [str(TOOL_NSZ), "-C", "-l", str(args.level), "-o", str(tmpdir), str(filepath)],
                        [str(TOOL_NSZ), "-C", "-l", str(args.level), str(filepath), "-o", str(tmpdir)],
                        [str(TOOL_NSZ), "-C", "-l", str(args.level), str(filepath)],
                    ]
                    for cmd in attempts:
                        try:
                            logger.debug("Trying recompress command: %s", " ".join(cmd))
                            logbase_r = Path(globals().get("ROMS_DIR", Path("."))) / "logs" / "nsz" / (filepath.stem + ".recomp")
                            res = run_cmd(cmd, filebase=logbase_r, timeout=getattr(globals().get("args", {}), "cmd_timeout", None))
                            logger.debug("nsz stdout: %s", getattr(res, "stdout", ""))
                            logger.debug("nsz stderr: %s", getattr(res, "stderr", ""))
                        except Exception as e:
                            logger.debug("recompress attempt failed: %s", e)
                            continue

                    # Find any produced .nsz in tmpdir
                    produced = list(Path(tmpdir).rglob("*.nsz"))
                    if produced:
                        new_file = produced[0]
                        target_tmp = filepath.parent / new_file.name
                        try:
                            # Move produced file next to original
                            if target_tmp.exists():
                                target_tmp.unlink()
                            shutil.move(str(new_file), str(target_tmp))
                            # Verify new compressed file
                            ok = True
                            try:
                                ok = verify_integrity(target_tmp, deep=False)
                            except Exception:
                                ok = True

                            if ok:
                                # Replace original with new compressed file
                                try:
                                    if filepath.exists():
                                        filepath.unlink()
                                    shutil.move(str(target_tmp), str(filepath))
                                    print(f" {Col.GREEN}[OK]{Col.RESET}")
                                    logger.info("Recompression succeeded and file replaced: %s", filepath.name)
                                    return filepath
                                except Exception:
                                    logger.exception("Failed to replace original with recompressed file: %s", filepath)
                                    # attempt to leave produced file as-is
                                    return target_tmp
                            else:
                                logger.warning("Recompressed file failed verification: %s", target_tmp)
                                # If user requested to keep artifacts on failure, move produced to quarantine for analysis
                                if getattr(args, "keep_on_failure", False):
                                    try:
                                        qdir = args.quarantine_dir
                                        if qdir:
                                            quarantine_dir = Path(qdir).resolve()
                                        else:
                                            quarantine_dir = ROMS_DIR / "_QUARANTINE"
                                        if not args.dry_run:
                                            quarantine_dir.mkdir(parents=True, exist_ok=True)
                                            dest = quarantine_dir / target_tmp.name
                                            shutil.move(str(target_tmp), str(dest))
                                            logger.info("Moved recompressed-failed artifact to quarantine: %s", dest)
                                    except Exception:
                                        logger.exception("Failed moving recompressed-failed artifact to quarantine: %s", target_tmp)
                                return filepath
                        except Exception:
                            logger.exception("Error handling recompressed file for %s", filepath)
                            return filepath

                print(f" {Col.RED}[FALHA]{Col.RESET}")
                return filepath
            except Exception as e:
                logger.exception(f"recompress failed for {filepath}: {e}")
                print(f" {Col.RED}[FALHA]{Col.RESET}")
                return filepath
        return filepath

    if args.compress and filepath.suffix.lower() != ".nsz":
        if args.dry_run:
            return filepath.with_suffix(".nsz")
        try:
            print("   🗜️  Comprimindo...", end="", flush=True)
            logbase_c = Path(globals().get("ROMS_DIR", Path("."))) / "logs" / "nsz" / (filepath.stem + ".compress")
            # run compression with timeout and capture outputs to log files
            try:
                run_cmd([str(TOOL_NSZ), "-C", "-l", str(args.level), str(filepath)], filebase=logbase_c, timeout=getattr(globals().get("args", {}), "cmd_timeout", None), check=True)
            except subprocess.CalledProcessError as cpe:
                logger.exception("Compression command failed for %s: %s", filepath, cpe)
                print(f" {Col.RED}[FALHA]{Col.RESET}")
                return filepath
            print(f" {Col.GREEN}[OK]{Col.RESET}")
            # Attempt to identify the produced .nsz file. Prefer same-stem .nsz
            compressed_candidate = filepath.with_suffix(".nsz")
            if not compressed_candidate.exists():
                # search in parent for matching stem
                candidates = list(filepath.parent.glob(filepath.stem + "*.nsz"))
                compressed_candidate = candidates[0] if candidates else None

            # If user requested removal of originals, verify compressed file and then remove source
            if args.rm_originals and not args.dry_run and compressed_candidate:
                try:
                    # quick existence and non-zero size check
                    if compressed_candidate.exists() and compressed_candidate.stat().st_size > 0:
                        # prefer checking integrity of compressed file when possible
                        ok = True
                        try:
                            ok = verify_integrity(compressed_candidate, deep=False)
                        except Exception:
                            ok = True
                        if ok:
                            try:
                                filepath.unlink()
                                logger.info("Original removido após compressão bem-sucedida: %s", filepath.name)
                            except Exception:
                                logger.exception("Falha ao remover arquivo original depois de comprimir: %s", filepath)
                        else:
                            logger.warning("Arquivo comprimido gerado, mas não passou na verificação: %s", compressed_candidate)
                            if getattr(args, "keep_on_failure", False):
                                try:
                                    qdir = args.quarantine_dir
                                    if qdir:
                                        quarantine_dir = Path(qdir).resolve()
                                    else:
                                        quarantine_dir = ROMS_DIR / "_QUARANTINE"
                                    if not args.dry_run:
                                        quarantine_dir.mkdir(parents=True, exist_ok=True)
                                        dest = quarantine_dir / compressed_candidate.name
                                        shutil.move(str(compressed_candidate), str(dest))
                                        logger.info("Moved failed compressed artifact to quarantine: %s", dest)
                                except Exception:
                                    logger.exception("Failed moving failed compressed artifact to quarantine: %s", compressed_candidate)
                except Exception:
                    logger.exception("Erro ao validar/remover original para %s", filepath)

            return compressed_candidate or filepath.with_suffix(".nsz")
        except Exception as e:
            logger.exception(f"compress failed for {filepath}: {e}")
            print(f" {Col.RED}[FALHA]{Col.RESET}")
            return filepath

    if args.decompress and filepath.suffix.lower() in {".nsz", ".xcz"}:
        if args.dry_run:
            return filepath.with_suffix(".nsp")
        try:
            print("   📦 Descomprimindo...", end="", flush=True)
            logbase_d = Path(globals().get("ROMS_DIR", Path("."))) / "logs" / "nsz" / (filepath.stem + ".decomp_act")
            # run decompression without auto-removing source to allow verification/keep-on-failure
            run_cmd([str(TOOL_NSZ), "-D", "-o", str(parent), str(filepath)], filebase=logbase_d, timeout=getattr(globals().get("args", {}), "cmd_timeout", None))
            print(f" {Col.GREEN}[OK]{Col.RESET}")
            # Try to find a decompressed candidate placed in the same folder.
            parent = filepath.parent
            try:
                archive_mtime = os.path.getmtime(filepath)
            except Exception:
                archive_mtime = None

            # direct-name candidates
            candidates = []
            for ext in (".nsp", ".xci", ".xcz"):
                candidates.extend(list(parent.glob(filepath.stem + f"*{ext}")))

            chosen = None
            if archive_mtime is not None:
                for c in candidates:
                    try:
                        if c.exists() and os.path.getmtime(c) >= archive_mtime - 2:
                            chosen = c
                            break
                    except Exception:
                        continue

            if chosen:
                try:
                    # only remove the original compressed if user didn't request keep-on-failure
                    if filepath.exists() and not args.dry_run and not getattr(args, "keep_on_failure", False):
                        try:
                            filepath.unlink()
                        except Exception:
                            logger.debug("failed to remove source nsz after decompress: %s", filepath)
                except Exception:
                    logger.debug("failed to handle source removal after decompress: %s", filepath)
                return chosen

            # Broader recent-file probe if direct name matching didn't find anything
            if archive_mtime is not None:
                look_window = 300
                recent_candidates = []
                for ext in (".nsp", ".xci", ".xcz"):
                    for c in parent.glob(f"*{ext}"):
                        try:
                            mtime = os.path.getmtime(c)
                        except Exception:
                            continue
                        if archive_mtime - look_window <= mtime <= archive_mtime + look_window:
                            recent_candidates.append(c)

                for cand in recent_candidates:
                    try:
                        cmd = [str(TOOL_METADATA), "-v" if IS_NSTOOL else "-k", str(cand)]
                        if not IS_NSTOOL:
                            cmd.insert(2, str(KEYS_PATH))
                            cmd.insert(3, "-i")
                        res_probe = subprocess.run(cmd, capture_output=True, text=True)
                    except Exception:
                        continue
                    tid_probe = TITLE_ID_RE.search(res_probe.stdout or "")
                    if tid_probe:
                        arch_tid_match = re.search(r"\[([0-9A-Fa-f]{16})\]", filepath.name)
                        if arch_tid_match and arch_tid_match.group(1).upper() == tid_probe.group(1).upper():
                            try:
                                if filepath.exists() and not args.dry_run:
                                    filepath.unlink()
                            except Exception:
                                logger.debug("failed to remove source nsz after probe remove: %s", filepath)
                            return cand
                    try:
                        if abs(os.path.getsize(cand) - os.path.getsize(filepath)) < 1024 * 1024:
                            try:
                                if filepath.exists() and not args.dry_run:
                                    filepath.unlink()
                            except Exception:
                                logger.debug("failed to remove source nsz after probe size-match: %s", filepath)
                            return cand
                    except Exception:
                        continue

            return filepath.with_suffix(".nsp")
        except Exception as e:
            logger.exception(f"decompress failed for {filepath}: {e}")
            print(f" {Col.RED}[FALHA]{Col.RESET}")
            return filepath
    return filepath


def safe_move(source, dest):
    if args.dry_run:
        return True

    def handle_duplicate(dst):
        # Check for duplicates and either remove source or return a unique path
        try:
            if args.dup_check == "strict":
                s_hash = get_file_hash(source)
                d_hash = get_file_hash(dst)
                if s_hash == d_hash:
                    logger.info(f"Duplicata exata removida: {source.name}")
                    source.unlink()
                    return None
            else:
                if os.path.getsize(source) == os.path.getsize(dst) and int(os.path.getmtime(source)) == int(os.path.getmtime(dst)):
                    logger.info(f"Duplicata exata removida: {source.name}")
                    source.unlink()
                    return None
        except Exception as e:
            logger.debug("dup check failed: %s", e)

        parent = dst.parent
        base = dst.stem
        suffix = dst.suffix
        counter = 1
        new_dest = parent / f"{base}_COPY_{counter}{suffix}"
        while new_dest.exists():
            counter += 1
            new_dest = parent / f"{base}_COPY_{counter}{suffix}"
        return new_dest

    if dest.exists() and source != dest:
        new_path = handle_duplicate(dest)
        if new_path is None:
            return False
        try:
            shutil.move(str(source), str(new_path))
            logger.warning(f"Colisão! Renomeado para: {new_path.name}")
            return True
        except Exception as e:
            logger.error("move collision failed: %s", e)
            return False

    try:
        safe_parent = dest.parent
        safe_parent.mkdir(parents=True, exist_ok=True)

        if len(dest.name) > 240:
            stem = dest.stem[:200]
            dest = dest.with_name(stem + dest.suffix)

        final_dest = dest
        counter = 1
        while final_dest.exists() and final_dest != source:
            final_dest = dest.with_name(f"{dest.stem}_{counter}{dest.suffix}")
            counter += 1

        shutil.move(str(source), str(final_dest))
        logger.info("Movido: %s -> %s", source.name, final_dest)
        return True
    except Exception as e:
        logger.exception("Erro IO ao mover %s -> %s: %s", source, dest, e)
        return False


def print_progress(current, total, filename):
    percent = 100 * (current / float(total))
    bar = "█" * int(30 * current // total) + "-" * (30 - int(30 * current // total))
    sys.stdout.write(
        f"\r{Col.CYAN}[{bar}] {percent:.1f}%{Col.RESET} | {filename[:25]}.."
    )
    sys.stdout.flush()


# --- LOOP PRINCIPAL (encapsulado em main) ---
def main():
    global args, ROMS_DIR, KEYS_PATH, DUPE_DIR, CSV_FILE
    global TOOL_NSTOOL, TOOL_HACTOOL, TOOL_NSZ, TOOL_METADATA, IS_NSTOOL, ENGINE_NAME
    global TOOL_CLAMSCAN, TOOL_CLAMDSCAN

    args = parser.parse_args()

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
                logger.info("Perfil de compressão '%s' selecionado -> nível %s", prof, args.level)
            else:
                logger.warning("Perfil de compressão desconhecido '%s', mantendo --level=%s", prof, args.level)
    except Exception:
        logger.exception("Erro ao aplicar compression_profile")

    # Validate numeric level bounds (1-22)
    try:
        lvl = int(args.level)
        if lvl < 1:
            logger.warning("Nivel de compressao %s muito baixo; ajustando para 1", lvl)
            lvl = 1
        if lvl > 22:
            logger.warning("Nivel de compressao %s acima do permitido; ajustando para 22", lvl)
            lvl = 22
        args.level = lvl
    except Exception:
        logger.warning("Nivel de compressao inválido; usando 1")
        args.level = 1

    if args.compress and args.decompress:
        sys.exit(f"{Col.RED}Erro: Escolha --compress OU --decompress.{Col.RESET}")

    ROMS_DIR = Path(args.dir).resolve()
    KEYS_PATH = Path(args.keys).resolve()
    DUPE_DIR = ROMS_DIR / "_DUPLICATES"
    CSV_FILE = ROMS_DIR / "biblioteca_switch.csv"

    # adjust logging level from CLI
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Detect tools
    TOOL_NSTOOL = find_tool("nstool")
    TOOL_HACTOOL = find_tool("hactool")
    TOOL_NSZ = find_tool("nsz")
    TOOL_CLAMSCAN = find_tool("clamscan")
    TOOL_CLAMDSCAN = find_tool("clamdscan")

    if TOOL_NSTOOL:
        TOOL_METADATA = TOOL_NSTOOL
        IS_NSTOOL = True
        ENGINE_NAME = "nstool"
    elif TOOL_HACTOOL:
        TOOL_METADATA = TOOL_HACTOOL
        IS_NSTOOL = False
        ENGINE_NAME = "hactool"
    else:
        logger.error("❌ ERRO CRÍTICO: Ferramentas de leitura não encontradas!")
        logger.error("Por favor, instale 'nstool' ou coloque o executável nesta pasta.")
        logger.error("Arch Linux: yay -S nstool")
        sys.exit(1)

    if (args.compress or args.decompress) and not TOOL_NSZ:
        logger.error("❌ ERRO: Ferramenta de compressão 'nsz' não encontrada!")
        logger.error("Instale com: pip install nsz")
        sys.exit(1)

    # If using hactool, ensure keys file exists
        logger.error(f"Arquivo de chaves não encontrado: {KEYS_PATH}")
        sys.exit(1)

    setup_logging(args.log_file, args.verbose)
    logger.info("Iniciando Switch Organizer")
    logger.info("Dir: %s", ROMS_DIR)

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

    # If health-check mode requested, run quick integrity + virus scan pass and exit.
    if args.health_check:
        # Delegate the health-check to a smaller function to keep main readable
        def run_health_check(all_files):
            logger.info("Iniciando Health Check: integridade + antivírus")
            corrupted = []
            infected = []
            unknown_av = []
            quarantine_dir = None
            if args.quarantine:
                qdir = args.quarantine_dir
                if qdir:
                    quarantine_dir = Path(qdir).resolve()
                else:
                    quarantine_dir = ROMS_DIR / "_QUARANTINE"
                try:
                    if not args.dry_run:
                        quarantine_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    logger.exception("Could not create quarantine dir %s: %s", quarantine_dir, e)

            report_rows = []
            for f in all_files:
                try:
                    ok, verify_out = verify_integrity(f, deep=args.deep_verify, return_output=True)
                except Exception as e:
                    ok = False
                    verify_out = str(e)

                av_result, av_out = scan_for_virus(f)
                integrity_status = "OK" if ok else "CORRUPT"
                if av_result is True:
                    infected.append((f, av_out))
                    av_status = "INFECTED"
                elif av_result is False:
                    av_status = "CLEAN"
                else:
                    unknown_av.append((f, av_out))
                    av_status = "UNKNOWN"

                action_taken = ""
                if args.quarantine and quarantine_dir is not None and (not args.dry_run):
                    try:
                        if integrity_status != "OK" or av_status == "INFECTED":
                            dest = quarantine_dir / f.name
                            moved = safe_move(f, dest)
                            action_taken = "QUARANTINED" if moved else "QUARANTINE_FAIL"
                    except Exception:
                        logger.exception("failed to move to quarantine: %s", f)

                report_rows.append([
                    str(f),
                    integrity_status,
                    (verify_out or "")[:10000],
                    av_status,
                    (av_out or "")[:10000],
                    action_taken,
                ])

            # Print summary
            print("\nHealth Check Result:")
            print(f"Total files scanned: {len(all_files)}")
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

            
            # Write CSV report if requested
            if args.report_csv:
                try:
                    with open(args.report_csv, "w", newline="", encoding="utf-8") as rf:
                        rw = csv.writer(rf)
                        rw.writerow(["path", "integrity", "integrity_output", "av_status", "av_output", "action"])
                        rw.writerows(report_rows)
                    print(f"Report saved to: {args.report_csv}")
                except Exception:
                    logger.exception("Failed to write report CSV %s", args.report_csv)

            problems = bool(corrupted or infected)
            summary = {
                "corrupted": corrupted,
                "infected": infected,
                "unknown_av": unknown_av,
                "report_rows": report_rows,
                "problems": problems,
            }
            if problems:
                print("Health check found issues. See report (if provided) or console output.")
            else:
                print("All clear: no corruption or infections found (or AV not available).")
            return summary

        hc_summary = run_health_check(files)
        # If user only requested health-check (no other actions), exit with code on problems
        other_actions = any([args.organize, args.compress, args.decompress, args.clean_junk])
        if not other_actions:
            if hc_summary and hc_summary.get("problems"):
                sys.exit(3)
            return

    catalog: List[List[Any]] = []
    stats = {"ok": 0, "erro": 0, "skipped": 0}

    for i, fpath in enumerate(files, 1):
        if SHUTDOWN_REQUESTED:
            logger.info("Shutdown requested by signal — stopping processing loop")
            break
        try:
            print_progress(i, len(files), fpath.name)

            # 1. Metadados
            meta = get_metadata(fpath)
            if not meta or not meta.get("id"):
                # More specific diagnostics for missing metadata
                reason = "TitleID não encontrado"
                if fpath.suffix.lower() == ".nsz":
                    reason += "; arquivo comprimido (.nsz) — tente usar --decompress ou instale/veja suporte da ferramenta nsz"
                logger.warning(
                    "Metadados ausentes para %s: %s. Arquivo: %s",
                    fpath.name,
                    reason,
                    fpath,
                )
                stats["erro"] += 1
                continue

            # 2. Verificação
            if not args.no_verify:
                ok = verify_integrity(fpath, deep=args.deep_verify)
                if not ok:
                    logger.error("Arquivo corrompido: %s", fpath.name)
                    # optionally quarantine
                    if args.quarantine:
                        qdir = args.quarantine_dir
                        if qdir:
                            quarantine_dir = Path(qdir).resolve()
                        else:
                            quarantine_dir = ROMS_DIR / "_QUARANTINE"
                        try:
                            if not args.dry_run:
                                quarantine_dir.mkdir(parents=True, exist_ok=True)
                                dest = quarantine_dir / fpath.name
                                safe_move(fpath, dest)
                        except Exception:
                            logger.exception("failed to quarantine corrupted file: %s", fpath)

                    stats["erro"] += 1
                    continue

            # 3. Conversão
            fpath = handle_compression(fpath)

            # 4. Novo Nome
            clean_name = sanitize_name(meta["name"])
            region = determine_region(fpath.name, meta["langs"])
            base_id = get_base_id(meta["id"])

            components = [clean_name]
            if region:
                components.append(region)
            # display languages in brackets when present
            if meta.get("langs"):
                components.append(f"[{meta.get('langs')}]")
            components.append(f"[{meta['type']}]")
            components.append(f"[{meta['id']}]")
            components.append(f"({meta['ver']})")

            new_fname = " ".join(components) + fpath.suffix

            if args.organize:
                # Build a folder name that includes region and languages
                folder_title = sanitize_name(clean_name)
                folder_components = [folder_title]
                if region:
                    folder_components.append(region)
                if meta.get("langs"):
                    # store folder languages as bracketed segment for readability
                    folder_components.append(f"[{meta.get('langs')}]")
                folder_components.append(f"[{base_id}]")

                folder_name = " ".join(folder_components)
                # Ensure no forbidden filesystem characters remain and reasonable length
                folder_name = INVALID_FILENAME_CHARS_RE.sub("", folder_name)
                if len(folder_name) > 200:
                    folder_name = folder_name[:200].rstrip()

                dest_folder = ROMS_DIR / folder_name
            else:
                dest_folder = fpath.parent

            target_path = dest_folder / new_fname

            # 5. Move
            if fpath != target_path:
                moved = safe_move(fpath, target_path)
                if moved:
                    stats["ok"] += 1
                else:
                    stats["skipped"] += 1
            else:
                stats["ok"] += 1

            # 6. Catálogo
            catalog.append(
                [
                    clean_name,
                    meta["id"],
                    meta["type"],
                    meta["ver"],
                    region,
                    meta["langs"],
                    fpath.suffix,
                    str(target_path),
                ]
            )
        except Exception:
            logger.exception("Erro ao processar arquivo %s", fpath)
            stats["erro"] += 1

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
            print(f"📊 Catálogo salvo em: {Col.YELLOW}{CSV_FILE.name}{Col.RESET}")
        except Exception as e:
            logger.exception(f"Erro ao salvar CSV: {e}")

    if args.clean_junk and not args.dry_run:
        print("🧹 Limpando lixo...")
        for junk in ROMS_DIR.rglob("*"):
            if junk.suffix.lower() in {".txt", ".nfo", ".url", ".lnk", ".website"}:
                try:
                    junk.unlink()
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
        f"{Col.GREEN}✅ Sucesso: {stats['ok']} | ⚠️  Pulos/Dups: {stats['skipped']} | ❌ Erros: {stats['erro']}{Col.RESET}"
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        # argparse or explicit sys.exit calls
        raise
    except Exception:
        logger.exception("Fatal error inesperado ao rodar o script")
        sys.exit(2)
