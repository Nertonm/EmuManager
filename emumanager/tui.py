"""Terminal UI + CLI for EmuManager.

Esta interface oferece um modo TUI interativo e comandos de linha de
comando completos que espelham as principais ações da GUI: inicializar a
biblioteca, listar e escanear sistemas, adicionar ROMs, organizar o
acervo (incluindo Switch), verificar via DAT, identificar arquivos,
limpar lixo e atualizar DATs.

A implementação usa `typer` para o roteamento de comandos e `rich` para
exibir tabelas/logs agradáveis no terminal. Sempre que possível, ela
reaproveita as funções já usadas pela GUI (`manager`, `workers`,
`switch`).
"""

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace
import asyncio
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Footer,
    Header,
    Label,
    ListItem,
    ListView,
    ProgressBar,
    # ScrollView has different names across textual versions; import
    # defensively below.
)


# Textual's TextLog widget exists in some versions. Provide a small
# compatibility wrapper if it's not available in the installed textual.
# Import ScrollView defensively: different textual versions expose either
# `ScrollView` or `scroll_view`. Fallback to `Static` if neither exists.
try:
    from textual.widgets import ScrollView  # type: ignore
except Exception:
    try:
        from textual.widgets import scroll_view as ScrollView  # type: ignore
    except Exception:
        from textual.widgets import Static as ScrollView  # type: ignore

try:
    from textual.widgets import TextLog  # type: ignore
except Exception:
    class TextLog(ScrollView):
        """Lightweight fallback that exposes a .write(msg) method used by the
        dashboard. It appends text to the ScrollView contents.
        """

        def write(self, msg: str) -> None:
            try:
                # Preserve existing content, append new line
                existing = ""
                if getattr(self, "renderable", None):
                    existing = str(self.renderable)
                new = (existing + "\n" + msg).lstrip("\n")
                self.update(new)
            except Exception:
                try:
                    self.update(msg)
                except Exception:
                    pass
import typer

from . import manager
from .config import BASE_DEFAULT
from .logging_cfg import configure_logging
from .workers.common import worker_clean_junk
from .workers.distributor import worker_distribute_root
from .workers.scanner import worker_scan_library
from .workers.switch import (
    worker_compress_single,
    worker_decompress_single,
    worker_health_check,
    worker_organize,
    worker_recompress_single,
    worker_switch_compress,
    worker_switch_decompress,
)
from .workers.verification import worker_hash_verify, worker_identify_all

# Switch helpers
from .common.execution import find_tool
from .switch.main_helpers import configure_environment

app = typer.Typer(help="Interface TUI/CLI do EmuManager")
console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _roms_root(base: Path) -> Path:
    """Resolve a pasta de ROMs considerando base ou base/roms."""
    if base.name == "roms":
        return base
    candidate = base / "roms"
    return candidate if candidate.exists() else base


def _switch_root(base: Path) -> Path:
    """Retorna a pasta de Switch, caindo para base se não existir."""
    roms = _roms_root(base)
    switch_dir = roms / "switch"
    return switch_dir if switch_dir.exists() else roms


def _list_files_flat(base: Path) -> list[Path]:
    return [p for p in base.rglob("*") if p.is_file()]


def _list_dirs_flat(base: Path) -> list[Path]:
    return [p for p in base.rglob("*") if p.is_dir()]


def _progress_cb(percent: float, message: str):
    console.log(f"[{percent*100:05.1f}%] {message}")


def _log_cb(msg: str):
    console.log(msg)


def _common_args(
    *,
    dry_run: bool = False,
    level: int = 3,
    compression_profile: Optional[str] = None,
    rm_originals: bool = False,
    quarantine: bool = False,
    deep_verify: bool = False,
    standardize_names: bool = False,
    report_csv: Optional[Path] = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        dry_run=dry_run,
        level=level,
        compression_profile=compression_profile,
        rm_originals=rm_originals,
        quarantine=quarantine,
        deep_verify=deep_verify,
        clean_junk=False,
        organize=False,
        compress=False,
        decompress=False,
        recompress=False,
        keep_on_failure=False,
        cmd_timeout=None,
        quarantine_dir=None,
        report_csv=str(report_csv) if report_csv else None,
        dup_check="fast",
        verbose=False,
        progress_callback=_progress_cb,
        cancel_event=threading.Event(),
        standardize_names=standardize_names,
    )


# ---------------------------------------------------------------------------
# Fullscreen TUI (Textual)
# ---------------------------------------------------------------------------


class FullscreenTui(App):
    """Dashboard fullscreen com painéis vivos e navegação por teclado."""

    CSS = """
    Screen {
        layout: vertical;
    }
    #top {
        height: auto;
        padding: 1 1;
    }
    #body {
        height: 1fr;
    }
    #actions {
        width: 32%;
        border: solid #666;
    }
    #main {
        border: solid #666;
    }
    TextLog {
        height: 1fr;
        border-top: solid #444;
    }
    """

    BINDINGS = [
        ("q", "quit", "Sair"),
        ("c", "cancel", "Cancelar operação"),
    ]

    def __init__(
        self, base: Path, keys: Optional[Path], dats_root: Optional[Path]
    ) -> None:
        super().__init__()
        self.base = base
        self.keys = keys
        self.dats_root = dats_root
        self.cancel_event = threading.Event()
        self.progress_bar: ProgressBar | None = None
        self.progress_label: Label | None = None
        self.log_view: TextLog | None = None
        self.actions_view: ListView | None = None
        # Selection helper used when prompting user for a system
        self._selection_future: Optional[asyncio.Future] = None
        # If user selected a system for verify, store the path here
        self._selected_system_target: Optional[Path] = None
        self._actions: list[tuple[str, str]] = [
            ("init", "Init"),
            ("list", "Listar sistemas"),
            ("refresh_systems", "Refresh systems"),
            ("scan", "Scan biblioteca"),
            ("organize", "Organizar Switch"),
            ("health", "Health check"),
            ("verify", "Verify (DAT)"),
            ("clean", "Clean junk"),
            ("update_dats", "Update DATs"),
            ("quit", "Sair"),
        ]
        # persistent systems view
        self.systems_view: ListView | None = None

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Header(id="top")
        with Horizontal(id="body"):
            with Vertical(id="actions"):
                yield Label(f"Base: {self.base}")
                # Create ListItem objects first and supply them to ListView
                items = [ListItem(Label(label), id=aid) for aid, label in self._actions]
                lv = ListView(*items)
                self.actions_view = lv
                yield lv
                # Systems list below actions
                try:
                    systems = manager.cmd_list_systems(self.base) or []
                except Exception:
                    systems = []
                sys_items = [ListItem(Label(s), id=f"_sys::{s}") for s in systems]
                sv = ListView(*sys_items)
                self.systems_view = sv
                yield Label("Sistemas:")
                yield sv
            with Vertical(id="main"):
                self.progress_label = Label("Pronto")
                yield self.progress_label
                self.progress_bar = ProgressBar(total=100)
                yield self.progress_bar
                try:
                    self.log_view = TextLog(highlight=True)
                except TypeError:
                    # Fallback TextLog (compat) may not accept highlight
                    self.log_view = TextLog()
                yield self.log_view
        yield Footer()

    def on_list_view_selected(self, event: ListView.Selected) -> None:  # type: ignore[override]
        action_id = event.item.id
        # If the selection is from the systems pane, handle specially
        if isinstance(action_id, str) and action_id.startswith("_sys::"):
            sys_name = action_id.split("::", 1)[1]
            # Normalize and set selected target
            try:
                tgt = self._resolve_system_target(sys_name)
                if tgt:
                    self._selected_system_target = tgt
                    self._log(f"Sistema selecionado: {sys_name} -> {tgt}")
                else:
                    self._log(
                        f"Sistema selecionado, mas pasta não encontrada: {sys_name}"
                    )
            except Exception:
                self._log(f"Erro ao resolver sistema: {sys_name}")
            return

        # If we are currently prompting for a selection, fulfill it here
        if self._selection_future is not None:
            try:
                # set result and clear the prompt
                if action_id:
                    # allow a special 'CANCEL' id to abort
                    if action_id == "_VERIFY_CANCEL":
                        if not self._selection_future.done():
                            self._selection_future.set_result(None)
                    else:
                        if not self._selection_future.done():
                            self._selection_future.set_result(action_id)
            except Exception:
                pass
            finally:
                return

        if action_id:
            self.call_later(self._run_action_async, action_id)

    async def _run_action_async(self, action_id: str):
        if action_id == "quit":
            await self.action_quit()
            return
        if action_id == "cancel":
            await self.action_cancel()
            return
        # If verify action, prompt the user to select a system first (UI thread)
        if action_id == "verify":
            selected = await self._prompt_select_system()
            if not selected:
                self._log("Verify cancelado pelo usuário")
                return
            # store selected path for worker thread to consume
            self._selected_system_target = selected

        self.cancel_event.clear()
        self._reset_progress()
        self._log(f"Executando: {action_id}")
        worker = self.run_worker(
            lambda: self._run_action_sync(action_id), exclusive=True
        )
        await worker.wait()

    def _run_action_sync(self, action_id: str):
        try:
            dispatch = {
                "init": self._act_init,
                "list": self._act_list,
                "refresh_systems": self._act_refresh_systems,
                "scan": self._act_scan,
                "organize": self._act_organize,
                "health": self._act_health,
                "verify": self._act_verify,
                "clean": self._act_clean,
                "update_dats": self._act_update_dats,
            }
            fn = dispatch.get(action_id)
            if fn:
                fn()
        except Exception as exc:  # pragma: no cover - mostra ao usuário
            self._log(f"Erro: {exc}")
        finally:
            self._set_progress(1.0, "Pronto")

    def _progress_cb(self, percent: float, message: str):
        try:
            self.call_from_thread(self._set_progress, percent, message)
        except RuntimeError:
            # If already in the app thread, call directly
            self._set_progress(percent, message)

    def _log(self, msg: str):
        try:
            self.call_from_thread(self._append_log, msg)
        except RuntimeError:
            # If already in the app thread, append directly
            self._append_log(msg)

    def _append_log(self, msg: str):
        if self.log_view:
            self.log_view.write(msg)

    def _set_progress(self, percent: float, message: str):
        if self.progress_bar:
            try:
                self.progress_bar.update(progress=int(percent * 100))
            except Exception:
                pass
        if self.progress_label:
            self.progress_label.update(message)

    def _reset_progress(self):
        if self.progress_bar:
            try:
                self.progress_bar.reset(progress=0)
            except Exception:
                self.progress_bar.update(progress=0)
        if self.progress_label:
            self.progress_label.update("Em execução...")

    def _act_init(self):
        rc = manager.cmd_init(self.base, dry_run=False)
        self._log(f"Init concluído (rc={rc})")

    def _act_list(self):
        systems = manager.cmd_list_systems(self.base)
        if not systems:
            self._log("Nenhum sistema encontrado")
            return
        for s in systems:
            self._log(f"- {s}")

    def _act_refresh_systems(self):
        """Refresh the persistent systems pane in-place."""
        try:
            updated = manager.cmd_list_systems(self.base) or []
        except Exception as e:
            self._log(f"Falha ao listar sistemas: {e}")
            return

        if not self.systems_view:
            # nothing mounted yet; simply log and return
            self._log("Systems view não está disponível para refresh")
            return

        # Build new ListItem nodes
        new_items = [ListItem(Label(s), id=f"_sys::{s}") for s in updated]

        # Try to update in-place using common Textual APIs. Be defensive
        try:
            # Preferred API: clear() then append
            self.systems_view.clear()
            for it in new_items:
                self.systems_view.append(it)
            self._log("Sistemas atualizados")
            return
        except Exception:
            pass

        try:
            # Alternative: remove_children / add
            if hasattr(self.systems_view, "remove_children"):
                self.systems_view.remove_children()
            # append children one by one
            for it in new_items:
                try:
                    self.systems_view.mount(it)
                except Exception:
                    try:
                        self.systems_view.append(it)
                    except Exception:
                        pass
            self._log("Sistemas atualizados")
            return
        except Exception:
            pass

        # Fallback: replace the ListView widget entirely
        try:
            parent = self.systems_view.parent
            if parent:
                # unmount old
                try:
                    self.systems_view.remove()
                except Exception:
                    pass
                new_lv = ListView(*new_items)
                self.systems_view = new_lv
                try:
                    parent.mount(new_lv)
                except Exception:
                    try:
                        parent.mount(new_lv)
                    except Exception:
                        pass
                self._log("Sistemas atualizados (substituído)")
                return
        except Exception:
            pass

        self._log("Falha ao atualizar lista de sistemas")

    def _act_scan(self):
        worker_scan_library(self.base, self._log, self._progress_cb, self.cancel_event)
        self._log("Scan concluído")

    def _act_organize(self):
        args = _common_args()
        args.organize = True
        target_root = _roms_root(self.base)
        self._log(f"Distribuindo {target_root}...")
        dist_res = worker_distribute_root(
            target_root,
            self._log,
            progress_cb=self._progress_cb,
            cancel_event=self.cancel_event,
        )
        self._log(str(dist_res))

        switch_dir = _switch_root(self.base)
        env = _switch_env(switch_dir, self.keys, args)
        res = worker_organize(
            switch_dir,
            env,
            args,
            self._log,
            _list_files_flat,
            progress_cb=self._progress_cb,
        )
        self._log(str(res))

    def _act_health(self):
        args = _common_args(quarantine=True, deep_verify=False)
        args.health_check = True
        switch_dir = _switch_root(self.base)
        env = _switch_env(switch_dir, self.keys, args)
        res = worker_health_check(
            switch_dir,
            env,
            args,
            self._log,
            _list_files_flat,
            progress_cb=self._progress_cb,
        )
        self._log(str(res))

    def _act_verify(self):
        # Allow selected system (from UI) to override default target
        if self._selected_system_target:
            target = self._selected_system_target
        else:
            target = _roms_root(self.base)

        dat_root = self.dats_root or (self.base / "dats")
        args = SimpleNamespace(
            dat_path=None,
            dats_roots=[dat_root],
            progress_callback=self._progress_cb,
            cancel_event=self.cancel_event,
        )
        rep = worker_hash_verify(target, args, self._log, _list_files_flat)
        # Reset selection so subsequent verifies start fresh
        self._selected_system_target = None

        # Render summary and table of results into the log view
        try:
            txt = self._render_verify_report(rep, target)
            self._log(txt)
        except Exception:
            self._log(rep.text or "Verificação concluída")

        # attempt to show thumbnails/cover URLs (non-blocking best-effort)
        try:
            covers_txt = self._gather_cover_urls(rep, target)
            if covers_txt:
                self._log(covers_txt)
        except Exception:
            pass

    async def _prompt_select_system(self) -> Optional[Path]:
        """Prompt the user (within the Textual app) to select a system to run verify on.

        Returns the Path to the chosen system directory under roms root, or None
        if canceled.
        """
        systems = manager.cmd_list_systems(self.base)
        if not systems:
            self._log("Nenhum sistema encontrado para verificar")
            return None

        # Build a ListView with system items + a cancel option
        items = [ListItem(Label(s), id=s) for s in systems]
        items.append(ListItem(Label("Cancelar"), id="_VERIFY_CANCEL"))
        lv = ListView(*items)

        # Mount the list view into the main area and focus it
        try:
            main = self.query_one("#main")
            main.mount(lv)
            lv.focus()
        except Exception:
            # Fallback: log and abort
            self._log("Erro ao montar seleção de sistemas")
            try:
                lv.remove()
            except Exception:
                pass
            return None

        # Create a future and wait for selection event to resolve it
        loop = asyncio.get_event_loop()
        self._selection_future = loop.create_future()
        try:
            sel = await self._selection_future
        finally:
            # cleanup
            try:
                lv.remove()
            except Exception:
                pass
            self._selection_future = None

        if not sel:
            return None

        # Build path under roms root. Manager returns names of systems
        tgt = _roms_root(self.base) / sel
        if not tgt.exists():
            # maybe manager returns full paths; try Path(sel)
            maybe = Path(sel)
            if maybe.exists():
                return maybe
            self._log(f"Pasta do sistema selecionado não encontrada: {tgt}")
            return None

        return tgt

    def _render_verify_report(self, rep, target: Path) -> str:
        """Render a rich table of verification results and return as plain text.

        Uses a temporary Console(record=True) to capture the formatted result.
        """
        try:
            from rich.console import Console as _Console

            c = _Console(record=True)
            t = Table(title=f"Verificação: {target}")
            t.add_column("Arquivo", overflow="fold")
            t.add_column("Status")
            t.add_column("Match")
            t.add_column("DAT")

            # Limit number of rows to something reasonable for terminal
            max_rows = 200
            for i, r in enumerate(rep.results):
                if i >= max_rows:
                    break
                t.add_row(
                    r.filename or "",
                    r.status or "",
                    r.match_name or "",
                    r.dat_name or "",
                )

            c.print(t)
            # also print a summary line
            c.print(rep.text or "")
            return c.export_text()
        except Exception:
            return rep.text or "Verification complete"

    def _gather_cover_urls(self, rep, target: Path) -> Optional[str]:
        """Attempt to construct cover URLs for matches using metadata providers.

        This is best-effort and does not perform network downloads. It returns
        a short text block with (file -> cover_url) lines when any URL is found.
        """
        try:
            from emumanager.metadata_providers import LibretroProvider
        except Exception:
            return None

        provider = LibretroProvider()
        system = target.name
        lines: list[str] = []
        seen = 0
        for r in rep.results:
            if not r.match_name:
                continue
            # Try by match name first
            url = provider.get_cover_url(system, None, r.match_name)
            if not url:
                # fallback to filename stem
                stem = Path(r.filename).stem if r.filename else None
                if stem:
                    url = provider.get_cover_url(system, None, stem)
            if url:
                lines.append(f"{r.filename} -> {url}")
                seen += 1
            if seen >= 30:
                break

        if not lines:
            return None

        return "Covers candidates:\n" + "\n".join(lines)

    def _resolve_system_target(self, sys_name: str) -> Optional[Path]:
        """Resolve a system identifier (name or alias) to a Path in roms/.

        Accepts common aliases and canonical names; if sys_name looks like a
        path, will return it directly when it exists.
        """
        # If sys_name is an existing path, return it
        try:
            p = Path(sys_name)
            if p.exists():
                return p
        except Exception:
            pass

        # Normalize aliases
        alias_map = {
            "gc": "gamecube",
            "game-cube": "gamecube",
            "wiiu": "wiiu",
            "psx": "psx",
            "ps2": "ps2",
            "ps3": "ps3",
            "nds": "nds",
            "3ds": "3ds",
            "n64": "n64",
        }
        key = sys_name.lower().strip()
        key = key.replace(" ", "").replace("-", "")
        mapped = alias_map.get(key, None)
        candidate_names = [sys_name]
        if mapped:
            candidate_names.insert(0, mapped)

        roms = _roms_root(self.base)
        for name in candidate_names:
            candidate = (roms / name) if not Path(name).is_absolute() else Path(name)
            if candidate.exists():
                return candidate

        # try fuzzy: lowercase match among detected systems
        try:
            systems = manager.cmd_list_systems(self.base) or []
            for s in systems:
                if s.lower().replace("-", "") == key:
                    cand = roms / s
                    if cand.exists():
                        return cand
        except Exception:
            pass

        return None

    def _act_clean(self):
        args = _common_args()
        res = worker_clean_junk(
            _roms_root(self.base), args, self._log, _list_files_flat, _list_dirs_flat
        )
        self._log(res)

    def _act_update_dats(self):
        rc = manager.cmd_update_dats(self.base, source=None)
        self._log(f"Update DATs rc={rc}")

    async def action_quit(self):
        self.exit()

    async def action_cancel(self):
        self.cancel_event.set()
        self._log("Cancel solicitado")


def _switch_env(base: Path, keys_path: Optional[Path], args: SimpleNamespace) -> dict:
    """Configura ambiente para operações do Switch reaproveitando helper da GUI."""

    class Logger:
        def info(self, msg, *a):  # type: ignore[override]
            _log_cb(msg % a if a else msg)

        def warning(self, msg, *a):  # type: ignore[override]
            _log_cb("WARN: " + (msg % a if a else msg))

        def error(self, msg, *a):  # type: ignore[override]
            _log_cb("ERROR: " + (msg % a if a else msg))

        def debug(self, msg, *a):  # type: ignore[override]
            pass

        def exception(self, msg, *a):  # type: ignore[override]
            _log_cb("EXCEPTION: " + (msg % a if a else msg))

    env_args = SimpleNamespace(
        dir=str(base),
        keys=str(keys_path or base / "keys.txt"),
        compress=getattr(args, "compress", False),
        decompress=getattr(args, "decompress", False),
        recompress=getattr(args, "recompress", False),
        organize=getattr(args, "organize", False),
        health_check=getattr(args, "health_check", False),
        progress_callback=_progress_cb,
        cancel_event=getattr(args, "cancel_event", None),
        quarantine=getattr(args, "quarantine", False),
        quarantine_dir=getattr(args, "quarantine_dir", None),
        dry_run=getattr(args, "dry_run", False),
        deep_verify=getattr(args, "deep_verify", False),
    )

    return configure_environment(env_args, Logger(), find_tool)


    # end _switch_env



# ---------------------------------------------------------------------------
# Comandos principais
# ---------------------------------------------------------------------------


@app.callback()
def _configure(_ctx: typer.Context):
    """Configura logging cedo para alinhar comportamento com GUI."""
    configure_logging()


@app.command("init")
def cmd_init(
    base: Path = typer.Option(Path(BASE_DEFAULT), help="Diretório base da biblioteca"),
    dry_run: bool = typer.Option(False, help="Simular sem alterar arquivos"),
):
    """Cria a estrutura padrão da biblioteca."""
    console.rule("Init da biblioteca")
    rc = manager.cmd_init(base, dry_run=dry_run)
    console.print(f"Concluído (rc={rc})")


@app.command("list-systems")
def cmd_list_systems(
    base: Path = typer.Option(Path(BASE_DEFAULT), help="Diretório base da biblioteca"),
):
    """Lista sistemas encontrados em roms/."""
    systems = manager.cmd_list_systems(base)
    table = Table(title=f"Sistemas em {base}")
    table.add_column("Sistema")
    for s in systems:
        table.add_row(s)
    console.print(table)


@app.command("scan")
def cmd_scan(
    base: Path = typer.Option(Path(BASE_DEFAULT), help="Diretório base ou roms"),
):
    """Escaneia biblioteca e atualiza o LibraryDB."""
    console.rule("Scanner")
    cancel = threading.Event()
    worker_scan_library(base, _log_cb, _progress_cb, cancel)


@app.command("add-rom")
def cmd_add_rom(
    src: Path = typer.Argument(..., exists=True, help="Arquivo ROM"),
    base: Path = typer.Option(Path(BASE_DEFAULT), help="Diretório base ou roms"),
    system: Optional[str] = typer.Option(None, help="Sistema (ex: nes, snes)"),
    move: bool = typer.Option(False, help="Mover ao invés de copiar"),
    dry_run: bool = typer.Option(False, help="Simular sem alterar arquivos"),
):
    """Adiciona ROM ao acervo, detectando sistema quando possível."""
    dest = manager.cmd_add_rom(src, base, system=system, move=move, dry_run=dry_run)
    console.print(f"Destino: {dest}")


@app.command("organize")
def cmd_organize(
    base: Path = typer.Option(Path(BASE_DEFAULT), help="Raiz da biblioteca ou roms"),
    keys: Optional[Path] = typer.Option(None, help="Caminho para keys.txt/prod.keys"),
    level: int = typer.Option(3, min=1, max=22, help="Nível de compressão NSZ"),
    rm_originals: bool = typer.Option(
        False, help="Apagar arquivo original após sucesso"
    ),
    standardize_names: bool = typer.Option(
        False, help="Renomear para padrão"
    ),
    quarantine: bool = typer.Option(
        False, help="Mover arquivos corrompidos para _QUARANTINE"
    ),
    dry_run: bool = typer.Option(False, help="Simular sem alterar"),
    deep_verify: bool = typer.Option(False, help="Verificação profunda"),
):
    """Organiza arquivos: distribui raiz e roda organizer do Switch."""
    console.rule("Organização completa")
    args = _common_args(
        dry_run=dry_run,
        level=level,
        rm_originals=rm_originals,
        standardize_names=standardize_names,
        quarantine=quarantine,
        deep_verify=deep_verify,
    )
    args.organize = True

    target_root = _roms_root(base)
    console.log(f"Distribuindo arquivos soltos em {target_root}...")
    dist_res = worker_distribute_root(
        target_root,
        _log_cb,
        progress_cb=_progress_cb,
        cancel_event=args.cancel_event,
    )
    console.log(f"Distribuição: {dist_res}")

    switch_dir = target_root / "switch"
    if not switch_dir.exists():
        console.print("[yellow]Pasta switch/ não encontrada; etapa de Switch pulada.")
        return

    env = _switch_env(switch_dir, keys, args)
    res = worker_organize(
        switch_dir,
        env,
        args,
        _log_cb,
        _list_files_flat,
        progress_cb=_progress_cb,
    )
    console.print(res)


@app.command("health-check")
def cmd_health_check(
    base: Path = typer.Option(Path(BASE_DEFAULT), help="Diretório switch"),
    keys: Optional[Path] = typer.Option(None, help="Caminho para keys.txt/prod.keys"),
    deep_verify: bool = typer.Option(False, help="Verificação profunda"),
    quarantine: bool = typer.Option(True, help="Isolar suspeitos em _QUARANTINE"),
    report_csv: Optional[Path] = typer.Option(None, help="Salvar relatório CSV"),
    dry_run: bool = typer.Option(False, help="Simulação"),
):
    """Executa health check (integridade + antivírus) para Switch."""
    switch_dir = _switch_root(base)
    args = _common_args(
        dry_run=dry_run,
        quarantine=quarantine,
        deep_verify=deep_verify,
        report_csv=report_csv,
    )
    args.health_check = True
    env = _switch_env(switch_dir, keys, args)
    res = worker_health_check(
        switch_dir, env, args, _log_cb, _list_files_flat, progress_cb=_progress_cb
    )
    console.print(res)


@app.command("compress")
def cmd_compress_switch(
    base: Path = typer.Option(Path(BASE_DEFAULT), help="Diretório switch"),
    keys: Optional[Path] = typer.Option(None, help="keys.txt/prod.keys"),
    level: int = typer.Option(3, min=1, max=22, help="Nível NSZ"),
    rm_originals: bool = typer.Option(False, help="Remover originais"),
    dry_run: bool = typer.Option(False, help="Simular"),
):
    """Compressão em lote (NSP/XCI -> NSZ/XCZ)."""
    switch_dir = _switch_root(base)
    args = _common_args(dry_run=dry_run, level=level, rm_originals=rm_originals)
    args.compress = True
    env = _switch_env(switch_dir, keys, args)
    res = worker_switch_compress(switch_dir, env, args, _log_cb, _list_files_flat)
    console.print(res)


@app.command("decompress")
def cmd_decompress_switch(
    base: Path = typer.Option(Path(BASE_DEFAULT), help="Diretório switch"),
    keys: Optional[Path] = typer.Option(None, help="keys.txt/prod.keys"),
    dry_run: bool = typer.Option(False, help="Simular"),
):
    """Descompressão em lote (NSZ/XCZ -> NSP/XCI)."""
    switch_dir = _switch_root(base)
    args = _common_args(dry_run=dry_run)
    args.decompress = True
    env = _switch_env(switch_dir, keys, args)
    res = worker_switch_decompress(switch_dir, env, args, _log_cb, _list_files_flat)
    console.print(res)


@app.command("recompress-one")
def cmd_recompress_one(
    filepath: Path = typer.Argument(..., exists=True, help="Arquivo NSZ/NCZ/ZIP/CHD"),
    base: Path = typer.Option(Path(BASE_DEFAULT), help="Diretório switch"),
    keys: Optional[Path] = typer.Option(None, help="keys.txt/prod.keys"),
    dry_run: bool = typer.Option(False, help="Simular"),
):
    """Recomprime apenas um arquivo, útil para testes rápidos."""
    switch_dir = _switch_root(base)
    args = _common_args(dry_run=dry_run)
    env = _switch_env(switch_dir, keys, args)
    res = worker_recompress_single(filepath, env, args, _log_cb)
    console.print(res)


@app.command("compress-one")
def cmd_compress_one(
    filepath: Path = typer.Argument(..., exists=True, help="Arquivo NSP/XCI"),
    base: Path = typer.Option(Path(BASE_DEFAULT), help="Diretório switch"),
    keys: Optional[Path] = typer.Option(None, help="keys.txt/prod.keys"),
    level: int = typer.Option(3, min=1, max=22, help="Nível de compressão"),
    rm_originals: bool = typer.Option(False, help="Remover original"),
    dry_run: bool = typer.Option(False, help="Simular"),
):
    args = _common_args(dry_run=dry_run, level=level, rm_originals=rm_originals)
    env = _switch_env(_switch_root(base), keys, args)
    res = worker_compress_single(filepath, env, args, _log_cb)
    console.print(res)


@app.command("decompress-one")
def cmd_decompress_one(
    filepath: Path = typer.Argument(..., exists=True, help="Arquivo NSZ/XCZ"),
    base: Path = typer.Option(Path(BASE_DEFAULT), help="Diretório switch"),
    keys: Optional[Path] = typer.Option(None, help="keys.txt/prod.keys"),
    dry_run: bool = typer.Option(False, help="Simular"),
):
    args = _common_args(dry_run=dry_run)
    env = _switch_env(_switch_root(base), keys, args)
    res = worker_decompress_single(filepath, env, args, _log_cb)
    console.print(res)


@app.command("verify")
def cmd_verify(
    target: Path = typer.Argument(
        Path(BASE_DEFAULT), help="Diretório do sistema a verificar"
    ),
    dat: Optional[Path] = typer.Option(None, help="Caminho do DAT específico"),
    dats_root: Optional[Path] = typer.Option(
        None, help="Diretório contendo vários DATs"
    ),
):
    """Verifica arquivos de um sistema contra um DAT."""
    args = SimpleNamespace(
        dat_path=str(dat) if dat else None,
        dats_roots=[dats_root] if dats_root else [],
        progress_callback=_progress_cb,
        cancel_event=threading.Event(),
    )
    report = worker_hash_verify(target, args, _log_cb, _list_files_flat)
    table = Table(title=f"Verificação {target}")
    table.add_column("Status")
    table.add_column("Detalhe")
    table.add_row("Resumo", report.text or "")
    console.print(table)


@app.command("identify")
def cmd_identify(
    target: Path = typer.Argument(Path(BASE_DEFAULT), help="Diretório do sistema"),
    dats_root: Path = typer.Option(Path("dats"), help="Pasta com DATs"),
):
    """Identifica arquivos usando todos os DATs disponíveis."""
    args = SimpleNamespace(
        dats_roots=[dats_root],
        progress_callback=_progress_cb,
        cancel_event=threading.Event(),
    )
    report = worker_identify_all(target, args, _log_cb, _list_files_flat)
    console.print(report.text)


@app.command("clean")
def cmd_clean(
    base: Path = typer.Option(Path(BASE_DEFAULT), help="Pasta roms ou sistema"),
    dry_run: bool = typer.Option(False, help="Simular limpeza"),
):
    """Remove arquivos lixo e diretórios vazios."""
    args = _common_args(dry_run=dry_run)
    res = worker_clean_junk(base, args, _log_cb, _list_files_flat, _list_dirs_flat)
    console.print(res)


@app.command("update-dats")
def cmd_update_dats(
    base: Path = typer.Option(Path(BASE_DEFAULT), help="Diretório base"),
    source: Optional[str] = typer.Option(
        None, help="Fonte específica: no-intro ou redump"
    ),
):
    """Baixa/atualiza arquivos DAT."""
    rc = manager.cmd_update_dats(base, source=source)
    console.print(f"Finalizado (rc={rc})")


@app.command("tui")
def cmd_tui(
    base: Path = typer.Option(Path(BASE_DEFAULT), help="Diretório base ou roms"),
):
    """Menu interativo simplificado (modo TUI)."""
    console.rule("EmuManager :: TUI")
    roms = _roms_root(base)
    console.print(Panel.fit(f"Base atual: {roms}", title="Contexto"))

    actions = {
        "1": ("Init", lambda: cmd_init(base=base, dry_run=False)),
        "2": ("Listar sistemas", lambda: cmd_list_systems(base=base)),
        "3": ("Scan", lambda: cmd_scan(base=base)),
        "4": (
            "Organizar",
            lambda: cmd_organize(
                base=base,
                keys=None,
                level=3,
                rm_originals=False,
                standardize_names=False,
                quarantine=False,
                dry_run=False,
                deep_verify=False,
            ),
        ),
        "5": (
            "Verify (DAT)",
            lambda: cmd_verify(target=roms, dat=None, dats_root=roms / "dats"),
        ),
        "6": ("Clean junk", lambda: cmd_clean(base=roms, dry_run=False)),
        "7": ("Update DATs", lambda: cmd_update_dats(base=base, source=None)),
        "0": ("Sair", lambda: None),
    }

    while True:
        table = Table(title="Selecione uma ação")
        table.add_column("Opção")
        table.add_column("Descrição")
        for key, (label, _) in actions.items():
            table.add_row(key, label)
        console.print(table)

        choice = typer.prompt("Escolha", default="0").strip()
        if choice == "0":
            console.print("Saindo do modo TUI.")
            return
        action = actions.get(choice)
        if not action:
            console.print("[red]Opção inválida")
            continue
        console.rule(f"Executando: {action[0]}")
        try:
            action[1]()
        except Exception as exc:  # pragma: no cover - falha exibida ao usuário
            console.print(f"[red]Erro: {exc}")


@app.command("tui-full")
def cmd_tui_full(
    base: Path = typer.Option(Path(BASE_DEFAULT), help="Diretório base ou roms"),
    keys: Optional[Path] = typer.Option(None, help="Caminho para keys.txt/prod.keys"),
    dats_root: Optional[Path] = typer.Option(None, help="Pasta com DATs"),
):
    """Abre o modo fullscreen com painéis ao vivo."""

    FullscreenTui(base, keys, dats_root).run()


def main():
    app()


if __name__ == "__main__":
    main()
