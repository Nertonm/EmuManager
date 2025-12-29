#!/usr/bin/env python3
"""
Architect module (package version)

This file is a near-copy of the previous `scripts/architect_roms_master.py` but
lives inside the `emumanager` package. It keeps the same public API (main,
build_acervo, etc.) so existing code and tests keep working.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import threading
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from .config import DATE_FMT

# ANSI colors (can be disabled with --no-color)
COLORS = {
    "BOLD": "\033[1m",
    "BLUE": "\033[0;34m",
    "GREEN": "\033[0;32m",
    "CYAN": "\033[0;36m",
    "RED": "\033[0;31m",
    "YELLOW": "\033[1;33m",
    "MAGENTA": "\033[0;35m",
    "WHITE": "\033[1;37m",
    "NC": "\033[0m",
}


class GracefulExit(Exception):
    """Raised when the program should exit gracefully due to a signal."""

    pass


def enable_signal_handlers(logger: logging.Logger):
    if threading.current_thread() is not threading.main_thread():
        logger.debug("Skipping signal handlers setup (not in main thread)")
        return

    def handler(signum, frame):
        logger.warning("Execution interrupted by user (signal=%s)", signum)
        raise GracefulExit(1)

    try:
        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)
    except ValueError:
        # Fallback if for some reason we are not in main thread but check passed
        logger.debug("Could not set signal handlers (ValueError)")


def check_write_permission(parent: Path) -> bool:
    # Verify that the current user can create entries in parent
    return os.access(str(parent), os.W_OK)


def create_readme(
    path: Path,
    sistema: str,
    formatos: str,
    wiki_url: str,
    bios_req: str,
    notas: str,
    date_str: str | None = None,
):
    path.mkdir(parents=True, exist_ok=True)
    content = f"""
==============================================================================
   GUIA TÉCNICO: {sistema}
==============================================================================
DATA DE CRIAÇÃO: {date_str or datetime.now().strftime(DATE_FMT)}

[ FORMATOS RECOMENDADOS ]
{formatos}

[ REQUER BIOS? ]
{bios_req}

[ DOCUMENTAÇÃO OFICIAL ]
Wiki / Setup Guide: {wiki_url}

[ ESTRUTURA E NOTAS ]
{notas}

==============================================================================
"""
    (path / "_INFO_TECNICA.txt").write_text(content, encoding="utf-8")


def get_roms_dir(base_dir: Path) -> Path:
    """Resolve the roms directory given a base path."""
    # If base_dir is already the 'roms' folder, use it directly
    if base_dir.name == "roms":
        return base_dir
    # Otherwise, append 'roms'
    return base_dir / "roms"


def setup_retro(
    base_dir: Path,
    sys: str,
    name: str,
    formats: str,
    wiki: str,
    bios_status: str,
    logger: logging.Logger,
):
    path = get_roms_dir(base_dir) / sys
    folders = [
        "# Favoritos",
        "# Traduzidos PT-BR",
        "# Hacks & Mods",
        "A-M",
        "N-Z",
    ]
    for f in folders:
        (path / f).mkdir(parents=True, exist_ok=True)

    notas = (
        "Este sistema usa emulação baseada em arquivos únicos.\n"
        "Mantenha organizado por pastas alfabéticas se tiver muitos jogos."
    )
    create_readme(path, name, formats, wiki, bios_status, notas)
    logger.info("[Retro]   %s :: Configured.", name)
    return sys


def setup_moderno(
    base_dir: Path,
    sys: str,
    name: str,
    formats: str,
    wiki: str,
    bios_status: str,
    details: str,
    folders: Iterable[str],
    logger: logging.Logger,
):
    path = get_roms_dir(base_dir) / sys
    for sub in folders:
        (path / sub).mkdir(parents=True, exist_ok=True)
        # Create favorites where it makes sense
        if any(k in sub for k in ("Games", "ISOs", "Roms", "Decrypted", "WUA", "NSP")):
            (path / sub / "# Favoritos").mkdir(parents=True, exist_ok=True)

    create_readme(path, name, formats, wiki, bios_status, details)
    logger.info("[Modern]  %s :: Configured.", name)
    return sys


def setup_arcade(
    base_dir: Path,
    sys: str,
    name: str,
    bios_status: str,
    logger: logging.Logger,
):
    path = get_roms_dir(base_dir) / sys
    path.mkdir(parents=True, exist_ok=True)
    notas = (
        "ATENÇÃO:\n"
        "1. Não extraia os ZIPs.\n"
        "2. Não renomeie os ZIPs (a validação depende do nome exato/CRC).\n"
        "3. Use sets 'Non-Merged' para facilitar o gerenciamento individual."
    )
    create_readme(
        path,
        name,
        ".zip (Full Non-Merged)",
        "https://docs.mamedev.org/",
        bios_status,
        notas,
    )
    logger.info("[Arcade]  %s :: Configured.", name)
    return sys


def build_acervo(base_dir: Path, dry_run: bool, logger: logging.Logger):
    # Print header
    dt = datetime.now().strftime(DATE_FMT)

    if dry_run:
        logger.info("Dry-run mode: no filesystem changes will be performed.")

    parent = base_dir.parent
    if not dry_run and not check_write_permission(parent):
        logger.error("No write permission in parent directory: %s", parent)
        raise PermissionError(f"No write permission in parent directory: {parent}")

    if not dry_run:
        base_dir.mkdir(parents=True, exist_ok=True)

    log_file = base_dir / "_INSTALL_LOG.txt"
    if not dry_run:
        log_file.write_text(f"Início da criação: {dt}\n", encoding="utf-8")

    logger.info("Install location: %s", base_dir)
    logger.info("Build date: %s", dt)

    # BIOS folder and readme
    bios_dir = base_dir / "bios"
    if not dry_run:
        bios_dir.mkdir(parents=True, exist_ok=True)

    leia_me = bios_dir / "_LEIA_ME.txt"
    leia_text = """
GUIA DE BIOS E FIRMWARES
==============================================================================
Esta pasta é o coração da emulação. Sem estes arquivos, sistemas modernos falham.

[ ARQUIVOS CRÍTICOS ]
------------------------------------------------------------------------------
Nintendo Switch:
  Copie para: /bios/switch/
  Arquivos:   prod.keys, title.keys e firmware (pasta)

Sony PlayStation:
  PS1: /bios/ps1/scph1001.bin (e scph5501.bin, scph7001.bin)
  PS2: /bios/ps2/scph10000.bin (ou similar) + rom1.bin
  PS3: /bios/ps3/PS3UPDAT.PUP (Firmware oficial para instalação no RPCS3)

Sega:
  Dreamcast: /bios/dc/dc_boot.bin e dc_flash.bin
  Saturn:    /bios/saturn/sega_101.bin (Jap) e mpr-17933.bin (USA)

Arcade:
  Neo-Geo:   /bios/neogeo/neogeo.zip (Mantenha zipado!)
==============================================================================
"""
    if not dry_run:
        leia_me.write_text(leia_text.strip() + "\n", encoding="utf-8")

    logger.info("BIOS folder :: Configured.")

    # DATs folder
    dats_dir = base_dir / "dats"
    if not dry_run:
        dats_dir.mkdir(parents=True, exist_ok=True)
        (dats_dir / "no-intro").mkdir(exist_ok=True)
        (dats_dir / "redump").mkdir(exist_ok=True)

    logger.info("DATs folder :: Configured.")

    # --- NINTENDO ---
    setup_retro(
        base_dir,
        "nes",
        "Nintendo (NES)",
        ".nes, .zip",
        (
            "https://emulation.gametechwiki.com/index.php/"
            "Nintendo_Entertainment_System_emulators"
        ),
        "Não",
        logger,
    )
    setup_retro(
        base_dir,
        "snes",
        "Super Nintendo",
        ".sfc (Pref), .smc, .zip",
        "https://docs.libretro.com/library/snes9x/",
        "Não",
        logger,
    )
    setup_retro(
        base_dir,
        "n64",
        "Nintendo 64",
        ".z64 (Big Endian), .n64",
        "https://m64p.github.io/",
        "Não",
        logger,
    )
    setup_retro(
        base_dir,
        "gba",
        "Game Boy Advance",
        ".gba",
        "https://mgba.io/",
        "Sim (bios.bin opcional, mas melhora compatibilidade)",
        logger,
    )
    setup_retro(
        base_dir,
        "nds",
        "Nintendo DS",
        ".nds",
        "https://melonds.kuribo64.net/",
        "Sim (bios7.bin, bios9.bin, firmware.bin)",
        logger,
    )

    setup_moderno(
        base_dir,
        "3ds",
        "Nintendo 3DS",
        ".3ds (Encrypted), .cia, .3ds (Decrypted)",
        "https://citra-emu.org/wiki/dumping-game-cartridges/",
        "Não (exceto para Menu Home)",
        "Citra roda melhor ROMs 'Decrypted'. Arquivos CIA devem ser instalados.",
        ["Decrypted Games (Citra)", "CIA (Installers)", "DLC & Updates (CIA)"],
        logger=logger,
    )
    setup_moderno(
        base_dir,
        "gamecube",
        "GameCube",
        ".rvz, .iso",
        "https://br.dolphin-emu.org/docs/guides/ripping-games/",
        "Não",
        "Use formato RVZ para compressão sem perda. Dolphin é o padrão ouro.",
        ["ISOs (RVZ)", "Texture Packs"],
        logger=logger,
    )
    setup_moderno(
        base_dir,
        "wii",
        "Nintendo Wii",
        ".wbfs, .rvz",
        "https://br.dolphin-emu.org/",
        "Não",
        "Evite .ISO (são gigantes). WBFS é ideal para hardware real, RVZ para Dolphin.",
        ["WBFS (Games)", "WiiWare (WAD)"],
        logger=logger,
    )
    setup_moderno(
        base_dir,
        "wiiu",
        "Nintendo Wii U",
        ".rpx (Loadiine), .wua",
        "https://cemu.info/",
        "Sim (Online files opcionais)",
        "Use o formato .WUA no Cemu para agrupar Jogo + Update + DLC em um único "
        "arquivo.",
        ["Games (Loadiine_WUA)", "Installers (WUP)", "Updates & DLC"],
        logger=logger,
    )
    setup_moderno(
        base_dir,
        "switch",
        "Nintendo Switch",
        ".xci, .nsp, .nsz",
        "https://yuzu-emu.org/help/quickstart/",
        "SIM (CRÍTICO: prod.keys + Firmware)",
        "XCI são dumps de cartucho. NSP são dumps digitais (eShop). "
        "Updates são sempre NSP/NSZ.",
        [
            "Base Games (XCI-NSP)",
            "Updates & DLC (NSP-NSZ)",
            "Mods (LayeredFS)",
            "Shaders Cache",
        ],
        logger=logger,
    )

    # --- SONY ---
    setup_retro(
        base_dir,
        "psx",
        "PlayStation 1",
        ".chd, .cue/.bin, .m3u",
        "https://docs.libretro.com/library/beetle_psx_hw/",
        "Sim (scph5501.bin recomendado)",
        logger,
    )
    setup_moderno(
        base_dir,
        "ps2",
        "PlayStation 2",
        ".chd, .iso",
        "https://pcsx2.net/docs/usage/setup/",
        "Sim (scph10000.bin ou mais recente)",
        "Converta ISOs para .CHD usando 'chdman'. Economia drástica de espaço.",
        ["Games (CHD-ISO)", "Cheats_Widescreen"],
        logger=logger,
    )
    setup_moderno(
        base_dir,
        "psp",
        "PlayStation Portable",
        ".cso, .iso",
        "https://www.ppsspp.org/",
        "Não",
        "Jogos mini/PSN são pastas com EBOOT.PBP.",
        ["ISOs (CSO)", "PSN (EBOOT)"],
        logger=logger,
    )
    setup_moderno(
        base_dir,
        "psvita",
        "PlayStation Vita",
        ".pkg, .zip (Nonpdrm)",
        "https://vita3k.org/",
        "Sim (Firmware deve ser instalado)",
        "Vita3K instala arquivos .pkg ou pastas Zipadas (Nonpdrm).",
        ["NoPayStation (PKG)", "Nonpdrm (Extracted)"],
        logger=logger,
    )
    setup_moderno(
        base_dir,
        "ps3",
        "PlayStation 3",
        ".iso, Folder (JB)",
        "https://rpcs3.net/quickstart",
        "Sim (Instalar PS3UPDAT.PUP)",
        "Jogos de disco: ISO ou Pasta JB. Jogos digitais: PKG + RAP (Licença).",
        ["ISOs", "HDD_Games (BLUSxxxx)", "PKGs (Installers)", "RAP_Licenses"],
        logger=logger,
    )
    setup_moderno(
        base_dir,
        "ps4",
        "PlayStation 4",
        ".pkg (FPKG)",
        "https://github.com/red-prig/fpPS4",
        "Sim (Firmware desencriptado)",
        "Emulação experimental. Apenas FPKGs (Fake PKGs - Desbloqueados) funcionam.",
        ["FPKGs"],
        logger=logger,
    )

    # --- SEGA ---
    setup_retro(
        base_dir,
        "mastersystem",
        "Sega Master System",
        ".sms, .zip",
        "https://docs.libretro.com/library/genesis_plus_gx/",
        "Não (Bios apenas para logo de boot)",
        logger,
    )
    setup_retro(
        base_dir,
        "megadrive",
        "Sega Mega Drive",
        ".md, .gen, .zip",
        "https://docs.libretro.com/library/genesis_plus_gx/",
        "Não",
        logger,
    )
    setup_retro(
        base_dir,
        "saturn",
        "Sega Saturn",
        ".chd, .cue/.bin",
        "https://docs.libretro.com/library/beetle_saturn/",
        "Sim (Obrigatório: sega_101.bin)",
        logger,
    )
    setup_moderno(
        base_dir,
        "dreamcast",
        "Sega Dreamcast",
        ".chd, .gdi",
        "https://flycast.org/",
        "Sim (dc_boot.bin, dc_flash.bin)",
        "Evite CDI (rips de baixa qualidade). Prefira GDI original ou CHD.",
        ["Games (CHD-GDI)", "VMU_Saves"],
        logger=logger,
    )

    # --- MICROSOFT & OUTROS ---
    setup_retro(
        base_dir,
        "atari2600",
        "Atari 2600",
        ".a26, .bin, .zip",
        "https://docs.libretro.com/library/stella/",
        "Não",
        logger,
    )
    setup_moderno(
        base_dir,
        "xbox_classic",
        "Xbox Original",
        ".iso (XISO)",
        "https://xemu.app/docs/disc-images/",
        "Sim (Complexo: mcpx_1.0.bin + flash.bin + HDD Image)",
        "ISOs 'Redump' padrão NÃO funcionam. Converta para XISO com 'extract-xiso'.",
        ["XISO (Redump)", "HDD Ready"],
        logger=logger,
    )
    setup_moderno(
        base_dir,
        "xbox360",
        "Xbox 360",
        ".iso, .xex",
        "https://github.com/xenia-project/xenia",
        "Não (Geralmente)",
        "Xenia roda ISOs ou pastas extraídas (XEX/GOD).",
        ["ISOs", "XBLA (Arcade)", "Extracted (GOD/XEX)"],
        logger=logger,
    )

    # --- ARCADE ---
    setup_arcade(
        base_dir,
        "mame",
        "MAME (Arcade)",
        "Não (As BIOS são parte dos ROMsets)",
        logger,
    )
    setup_arcade(
        base_dir,
        "neogeo",
        "Neo-Geo",
        "Sim (neogeo.zip dentro da pasta de roms)",
        logger,
    )
    setup_arcade(base_dir, "fbneo", "Final Burn Neo", "Não (Incluído nos sets)", logger)

    # Final notes
    logger.info("COLLECTION BUILD COMPLETE!")
    if not dry_run:
        logger.info("Detailed log saved to: %s", log_file)
    logger.info(
        "Next steps: fill /bios, copy games and read _INFO_TECNICA.txt for each system."
    )


def _get_logger(base_dir: Path) -> logging.Logger:
    # Use centralized logger helper so behavior is consistent across modules.
    try:
        from .logging_cfg import get_logger
    except Exception:
        # Fallback: create a minimal logger inline
        logger = logging.getLogger("architect")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            ch = logging.StreamHandler()
            ch.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(ch)
        return logger

    return get_logger("architect", base_dir=base_dir, level=logging.INFO)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Architect ROMs Master - estrutura de acervo de emulação"
    )
    p.add_argument(
        "base_dir",
        nargs="?",
        default="./Acervo_Games_Ultimate",
        help="Diretório base de criação",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula ações sem alterar o sistema de arquivos",
    )
    p.add_argument(
        "--no-color", action="store_true", help="Desativa cores ANSI na saída"
    )
    return p.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    base_dir = Path(args.base_dir).expanduser().resolve()
    if not base_dir.parent.exists():
        # If parent doesn't exist, attempt to create it
        base_dir.parent.mkdir(parents=True, exist_ok=True)

    # Ensure base_dir exists so the file logger can be created
    base_dir.mkdir(parents=True, exist_ok=True)
    logger = _get_logger(base_dir)
    enable_signal_handlers(logger)

    try:
        build_acervo(base_dir, dry_run=args.dry_run, logger=logger)
    except GracefulExit:
        return 1
    except Exception as exc:
        logger.exception("Erro durante a construção: %s", exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
