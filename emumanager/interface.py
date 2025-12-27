#!/usr/bin/env python3
"""
EmuManager - Interactive interface (package version)

This module provides the same interactive REPL as the script shim but lives
inside the `emumanager` package so it can be imported and tested easily.
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Optional

try:
    # Normal package import when used as module: `python -m emumanager.interface`
    from . import manager as emu
    from .config import BASE_DEFAULT
except Exception:
    # Allow running the file directly (e.g. `python emumanager/interface.py`) by
    # patching sys.path so the package root is importable and then using
    # absolute imports. This keeps the convenience of running the script
    # directly while preserving import-time behavior when used as a package.
    import sys
    from pathlib import Path as _P

    _ROOT = _P(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    from emumanager import manager as emu
    from emumanager.config import BASE_DEFAULT


DEFAULT_BASE = Path(BASE_DEFAULT)


def prompt(text: str, default: Optional[str] = None) -> str:
    if default:
        resp = input(f"{text} [{default}]: ")
        return resp.strip() or default
    return input(f"{text}: ").strip()


def yes_no(text: str, default: bool = True) -> bool:
    d = "Y/n" if default else "y/N"
    resp = input(f"{text} ({d}): ").strip().lower()
    if resp == "":
        return default
    return resp in ("y", "yes")


def cmd_init_interactive():
    base = (
        Path(prompt("Diretório base de criação", str(DEFAULT_BASE)))
        .expanduser()
        .resolve()
    )
    dry = yes_no("Executar em modo dry-run (sem alterações)?", default=False)
    print("Iniciando criação... (dry-run=%s)" % dry)
    rc = emu.cmd_init(base, dry_run=dry)
    print("Retorno:", rc)


def cmd_list_interactive():
    base = (
        Path(prompt("Diretório base (onde está o Acervo)", str(DEFAULT_BASE)))
        .expanduser()
        .resolve()
    )
    systems = emu.cmd_list_systems(base)
    if not systems:
        print("Nenhum sistema encontrado — execute 'init' primeiro.")
        return
    print("Sistemas encontrados:")
    for s in systems:
        print(" -", s)


def cmd_add_interactive():
    src = Path(prompt("Caminho para o ROM (arquivo)")).expanduser().resolve()
    base = (
        Path(prompt("Diretório base (onde colocar)", str(DEFAULT_BASE)))
        .expanduser()
        .resolve()
    )
    system = (
        prompt("Sistema alvo (ex: nes) — deixe vazio para adivinhar", "").strip()
        or None
    )
    move = yes_no("Mover arquivo em vez de copiar?", default=False)
    dry = yes_no("Dry-run (simular)?", default=False)

    try:
        dest = emu.cmd_add_rom(src, base, system=system, move=move, dry_run=dry)
        print("Destino:", dest)
    except Exception as e:
        print("Erro ao adicionar ROM:", e)


def show_help():
    print("Comandos: init, list, add, help, exit")


def repl():
    print("EmuManager - interface interativa")
    print("Digite 'help' para ver comandos. Ctrl-C para sair.")
    while True:
        try:
            line = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSaindo...")
            return

        if not line:
            continue

        parts = shlex.split(line)
        cmd = parts[0].lower()

        if cmd in ("exit", "quit"):
            print("Saindo...")
            return
        if cmd in ("help", "h", "?"):
            show_help()
            continue

        if cmd in ("init",):
            cmd_init_interactive()
            continue

        if cmd in ("list", "list-systems"):
            cmd_list_interactive()
            continue

        if cmd in ("add", "add-rom"):
            cmd_add_interactive()
            continue

        print("Comando desconhecido:", cmd)
        show_help()


def main() -> int:
    repl()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
