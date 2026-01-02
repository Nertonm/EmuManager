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

import asyncio
import os
import re
import shutil
import sys
import threading
from datetime import datetime
from pathlib import Path
from pathlib import Path as _Path
from types import SimpleNamespace
from typing import Optional

try:
    # Python 3.8+
    from importlib import metadata as importlib_metadata
except Exception:  # pragma: no cover - defensive for older Pythons
    # Should rarely be needed; keep a best-effort fallback.
    import importlib_metadata  # type: ignore

import typer
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
)

from . import manager

# Switch helpers
from .common.execution import find_tool
from .config import BASE_DEFAULT
from .logging_cfg import configure_logging
from .switch.main_helpers import configure_environment
from .tui_compat import (
    TextLog,
    create_checkbox,
    data_table_class,
    get_checkbox_value,
    key_matches,
    safe_append,
    safe_clear,
    safe_focus,
    safe_mount,
    safe_remove,
)
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

app = typer.Typer(help="Interface TUI/CLI do EmuManager")
console = Console()

# Global flag to allow non-interactive "assume yes" behavior for scripts.
# Honor environment variable EMUMANAGER_ASSUME_YES for non-Typer entrypoints.
ASSUME_YES = str(os.environ.get("EMUMANAGER_ASSUME_YES", "")).lower() in (
    "1",
    "true",
    "yes",
    "y",
)
ACTION_LOG_PATH = Path("logs") / "tui_actions.log"


def _ensure_action_log_dir() -> None:
    try:
        ACTION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _log_action_decision(action: str, source: str, decision: str) -> None:
    """Append an audit line to logs/tui_actions.log with timestamp."""
    try:
        _ensure_action_log_dir()
        ts = datetime.utcnow().isoformat() + "Z"
        line = f"{ts}\t{source}\t{action}\t{decision}\n"
        with open(ACTION_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:
        # best-effort only
        pass


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
    console.log(f"[{percent * 100:05.1f}%] {message}")


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


def confirm_or_assume(
    prompt: str,
    default: bool = False,
    action_name: Optional[str] = None,
    source: str = "cli",
) -> bool:
    """Ask user to confirm unless global ASSUME_YES is set.

    Logs the decision to `logs/tui_actions.log` for auditability. The
    `action_name` and `source` (e.g. 'cli' or 'tui') are recorded when
    available.
    """
    try:
        if ASSUME_YES:
            console.log(f"Assuming YES for prompt: {prompt}")
            _log_action_decision(action_name or prompt, source, "assumed-yes")
            return True
    except Exception:
        pass

    try:
        res = typer.confirm(prompt, default=default)
    except Exception:
        # If terminal interaction fails, be conservative and return False
        _log_action_decision(action_name or prompt, source, "error-no-interaction")
        return False

    _log_action_decision(action_name or prompt, source, "yes" if res else "no")
    return res


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
        ("?", "show_help", "Ajuda"),
        ("p", "palette", "Command palette"),
        ("/", "search_files", "Buscar arquivos"),
    ]

    def __init__(
        self,
        base: Path,
        keys: Optional[Path],
        dats_root: Optional[Path],
        auto_verify_on_select: bool = True,
        assume_yes: bool = False,
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
        # mapping from sanitized widget ids to real system names
        self._sys_id_map: dict[str, str] = {}
        # If user selected a system for verify, store the path here
        self._selected_system_target: Optional[Path] = None
        self._actions: list[tuple[str, str]] = [
            ("init", "Inicializar biblioteca"),
            ("list", "Listar sistemas"),
            ("refresh_systems", "Atualizar lista de sistemas"),
            ("scan", "Escanear biblioteca"),
            ("add_rom", "Adicionar ROM(s)"),
            ("organize", "Organizar biblioteca (Switch)"),
            ("health", "Verificar integridade (Switch)"),
            ("compress", "Comprimir (Switch)"),
            ("decompress", "Descomprimir (Switch)"),
            ("verify", "Verificar via DAT"),
            ("identify", "Identificar arquivos"),
            ("clean", "Limpar lixo"),
            ("update_dats", "Atualizar DATs"),
            ("quit", "Sair"),
        ]
        # persistent systems view
        self.systems_view: ListView | None = None
        # per-system files view and id map
        self.files_view: ListView | None = None
        self._file_id_map: dict[str, Path] = {}
        # whether selecting a system triggers Verify automatically
        self.auto_verify_on_select = bool(auto_verify_on_select)
        # whether to skip interactive confirmations
        self.assume_yes = bool(assume_yes)

    def _check_textual_version(self) -> None:
        """Check installed textual version and log a friendly warning if it's outside
        the recommended range.
        """
        try:
            import textual

            v = getattr(textual, "__version__", None)
            if not v:
                return
            parts = v.split(".")
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            # recommended range: >=0.20 and <0.27
            if (major, minor) < (0, 20) or (major, minor) >= (0, 27):
                self._log(f"Aviso: versão do 'textual' detectada: {v}.")
                self._log(
                    "Recomendado: textual >=0.20 and <0.27. Se tiver problemas: "
                    "pip install 'textual>=0.20,<0.27'"
                )
        except Exception:
            # don't fail startup for any reason
            return

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
                # Build mapping and sanitized ids
                self._sys_id_map.clear()
                sys_items = []
                for s in systems:
                    sid = f"sys_{re.sub(r'[^A-Za-z0-9_-]', '_', s)}"
                    self._sys_id_map[sid] = s
                    sys_items.append(ListItem(Label(s), id=sid))
                sv = ListView(*sys_items)
                self.systems_view = sv
                yield Label("Sistemas:")
                yield sv
                # files list for selected system (initially empty)
                fv = ListView()
                self.files_view = fv
                yield Label("Arquivos:")
                yield fv
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
        # schedule a quick runtime check of Textual version after mount
        try:
            self.call_later(self._check_textual_version)
        except Exception:
            pass

    async def action_show_help(self) -> None:
        """Show a small help overlay listing keyboard shortcuts."""
        try:
            await self._prompt_help_modal()
        except Exception:
            # fallback: print to log_view
            try:
                self._log(
                    "Teclas: q=sair, c=cancelar, ?=ajuda, p=paleta, /=buscar, "
                    "Esc=fechar modais"
                )
            except Exception:
                pass

    async def action_palette(self) -> None:
        """Open a command palette modal to run common actions via keyboard."""
        try:
            sel = await self._prompt_command_palette()
            if sel:
                # interpret sel as action id and trigger it
                try:
                    self.call_later(self._run_action_async, sel)
                except Exception:
                    try:
                        asyncio.create_task(self._run_action_async(sel))
                    except Exception:
                        pass
        except Exception:
            pass

    async def action_search_files(self) -> None:
        """Prompt for a filename substring and focus files_view filtered to matches."""
        try:
            # Use console fallback when Input isn't available
            try:
                from textual.widgets import Input as _Input
            except Exception:
                _Input = None  # type: ignore

            if _Input is None:
                # headless fallback
                term_q = typer.prompt("Search files (substring)", default="")
                q = term_q.strip()
            else:
                # Mount a simple input modal
                from textual.containers import Vertical as _Vertical
                from textual.widgets import Static as _Static

                modal = _Vertical(id="modal_search")
                try:
                    modal.mount(_Static("Search files:"))
                except Exception:
                    try:
                        modal.mount(Label("Search files:"))
                    except Exception:
                        pass
                try:
                    inp = _Input()
                    modal.mount(inp)
                except Exception:
                    inp = None
                ok = ListItem(Label("OK"), id="_OPT_OK")
                cancel = ListItem(Label("Cancelar"), id="_OPT_CANCEL")
                lv = ListView(ok, cancel)
                try:
                    modal.mount(lv)
                except Exception:
                    pass
                try:
                    safe_mount(self, modal)
                    if inp is not None:
                        safe_focus(inp)
                    else:
                        safe_focus(lv)
                except Exception:
                    try:
                        safe_remove(modal)
                    except Exception:
                        pass
                    return

                loop = asyncio.get_event_loop()
                self._selection_future = loop.create_future()
                try:
                    sel = await self._selection_future
                finally:
                    try:
                        safe_remove(modal)
                    except Exception:
                        pass
                    self._selection_future = None

                if sel == "_OPT_OK" and inp is not None:
                    try:
                        q = getattr(inp, "value", "").strip()
                    except Exception:
                        q = ""
                else:
                    q = ""

            # If we have a query, filter the files_view items
            if q:
                try:
                    files = getattr(self, "_current_file_list", []) or []
                    matches = [f for f in files if q.lower() in f.name.lower()]
                    if self.files_view is not None:
                        safe_clear(self.files_view)
                        for i, f in enumerate(matches[:500]):
                            fid = f"file_{i}"
                            self._file_id_map[fid] = f
                            safe_append(
                                self.files_view,
                                ListItem(Label(f.name), id=fid),
                            )
                        self._log(f"Search: {len(matches)} matches for '{q}'")
                except Exception:
                    pass
        except Exception:
            pass

    # Prompt helpers -----------------------------------------------------
    async def _prompt_help_modal(self) -> Optional[str]:
        """Show a small help modal with keyboard bindings and return when closed.

        Returns the selected id (or None). Uses headless fallback via prompt.
        """
        # Test hook: allow tests to short-circuit the modal early
        if getattr(self, "_test_auto_help", None):
            return "_HELP_OK"

        try:
            # If Textual Input isn't available, fallback to console
            if "textual" not in sys.modules:
                typer.echo("Teclas: q=sair, c=cancelar, ?=ajuda, p=paleta, /=buscar")
                _ = typer.prompt("Pressione Enter para continuar", default="")
                return None

            # Build a simple modal with a static help message and an OK button
            from textual.widgets import Static

            modal = Vertical(id="modal_help")
            help_lines = [
                "Atalhos:",
                "  q: Sair",
                "  c: Cancelar operação",
                "  ?: Ajuda",
                "  p: Paleta de comandos",
                "  /: Buscar arquivos",
                "  Esc: Fechar modal/tabela",
            ]
            try:
                modal.mount(Static("\n".join(help_lines)))
            except Exception:
                # defensive: best-effort
                pass

            ok = ListItem(Label("OK"), id="_HELP_OK")
            lv = ListView(ok)
            try:
                modal.mount(lv)
            except Exception:
                pass

            try:
                safe_mount(self, modal)
                safe_focus(lv)
            except Exception:
                try:
                    safe_remove(modal)
                except Exception:
                    pass
                return None

            loop = asyncio.get_event_loop()
            self._selection_future = loop.create_future()
            try:
                sel = await self._selection_future
            finally:
                try:
                    safe_remove(modal)
                except Exception:
                    pass
                self._selection_future = None
            return sel
        except Exception:
            return None

        # Test hook: allow tests to short-circuit the modal
        if getattr(self, "_test_auto_help", None):
            return "_HELP_OK"

    async def _prompt_command_palette(self) -> Optional[str]:
        """Present a palette of commands; return the selected command id or None.

        Headless fallback uses a console prompt to pick from a short list.
        """
        # Test hook: if set, return the canned command id for tests early
        if getattr(self, "_test_auto_palette", None):
            return getattr(self, "_test_auto_palette")

        try:
            # Mirror the actions panel so palette stays in sync with feature parity.
            commands = list(getattr(self, "_actions", []))

            # headless fallback
            if "textual" not in sys.modules:
                typer.echo("Command palette:")
                for i, (_id, label) in enumerate(commands, start=1):
                    typer.echo(f"  {i}) {label}")
                choice = typer.prompt("Escolha (número)", default="0").strip()
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(commands):
                        return commands[idx][0]
                except Exception:
                    return None
                return None

            # Textual modal palette
            modal = Vertical(id="modal_palette")
            items = []
            for _id, label in commands:
                items.append(ListItem(Label(label), id=_id))
            lv = ListView(*items)
            try:
                modal.mount(lv)
            except Exception:
                pass

            try:
                safe_mount(self, modal)
                safe_focus(lv)
            except Exception:
                try:
                    safe_remove(modal)
                except Exception:
                    pass
                return None

            loop = asyncio.get_event_loop()
            self._selection_future = loop.create_future()
            try:
                sel = await self._selection_future
            finally:
                try:
                    safe_remove(modal)
                except Exception:
                    pass
                self._selection_future = None
            return sel
        except Exception:
            return None

        # Test hook: if set, return the canned command id for tests
        if getattr(self, "_test_auto_palette", None):
            return getattr(self, "_test_auto_palette")

    def on_list_view_selected(self, event: ListView.Selected) -> None:  # type: ignore[override]
        action_id = event.item.id
        # If the selection is from the systems pane, handle specially
        if isinstance(action_id, str) and action_id in self._sys_id_map:
            sys_name = self._sys_id_map.get(action_id)
            # Normalize and set selected target
            try:
                tgt = self._resolve_system_target(sys_name)
                if tgt:
                    self._selected_system_target = tgt
                    self._log(f"Sistema selecionado: {sys_name} -> {tgt}")
                    # populate files view with files from the selected system
                    try:
                        files = _list_files_flat(tgt)
                    except Exception:
                        files = []
                    # build file items and id map
                    self._file_id_map.clear()
                    items = []
                    for i, f in enumerate(files[:500]):
                        fid = f"file_{i}"
                        self._file_id_map[fid] = f
                        items.append(ListItem(Label(f.name), id=fid))
                    # update files_view in a safe manner with simple pagination
                    if self.files_view:
                        try:
                            # store full list for paging and reset page index
                            self._current_file_list = files
                            self._files_page = 0
                            page_size = 100
                            page_items = items[:page_size]
                            safe_clear(self.files_view)
                            for it in page_items:
                                safe_append(self.files_view, it)
                            # add a More... item when more pages exist
                            if len(items) > page_size:
                                more = ListItem(Label("Mais..."), id="file_more")
                                safe_append(self.files_view, more)
                        except Exception:
                            try:
                                parent = self.files_view.parent
                                if parent:
                                    safe_remove(self.files_view)
                                    new_lv = ListView(*items)
                                    self.files_view = new_lv
                                    safe_mount(parent, new_lv)
                            except Exception:
                                pass
                    # Auto-trigger verify if configured
                    if getattr(self, "auto_verify_on_select", False):
                        try:
                            self.call_later(self._run_action_async, "verify")
                        except Exception:
                            pass
                else:
                    self._log(
                        f"Sistema selecionado, mas pasta não encontrada: {sys_name}"
                    )
            except Exception:
                self._log(f"Erro ao resolver sistema: {sys_name}")
            return

        # If the user selected the 'More...' item, load next page
        if action_id == "file_more":
            try:
                page_size = 100
                self._files_page = getattr(self, "_files_page", 0) + 1
                start = self._files_page * page_size
                end = start + page_size
                files = getattr(self, "_current_file_list", [])
                new_items = []
                for i, f in enumerate(files[start:end], start=start):
                    fid = f"file_{i}"
                    self._file_id_map[fid] = f
                    new_items.append(ListItem(Label(f.name), id=fid))
                # replace files_view contents
                if self.files_view:
                    try:
                        safe_clear(self.files_view)
                        for it in new_items:
                            safe_append(self.files_view, it)
                        if len(files) > end:
                            more_item = ListItem(Label("Mais..."), id="file_more")
                            safe_append(self.files_view, more_item)
                    except Exception:
                        pass
            except Exception:
                pass
            return

        # If a file was selected in files_view, prompt for per-file actions
        if isinstance(action_id, str) and action_id in self._file_id_map:
            fpath = self._file_id_map.get(action_id)
            if not fpath:
                return
            # Ask user which action to perform on this file
            try:
                act = asyncio.get_event_loop().run_until_complete(
                    self._prompt_file_actions(fpath)
                )
            except Exception:
                # If not possible to run sync, schedule on UI loop
                try:
                    self.call_later(
                        asyncio.create_task, self._prompt_file_actions(fpath)
                    )
                except Exception:
                    pass
                return
            if not act:
                return
            # Collect action-specific options (level, rm_originals, dry_run)
            try:
                opts = asyncio.get_event_loop().run_until_complete(
                    self._prompt_action_options(fpath, act)
                )
            except Exception:
                opts = {}
            # run the file action in background
            try:
                self.run_worker(
                    asyncio.to_thread(self._run_file_action_sync, fpath, act, opts),
                    exclusive=True,
                )
            except Exception:
                try:
                    # fallback: run synchronously
                    self._run_file_action_sync(fpath, act, opts)
                except Exception as e:
                    self._log(f"Erro executando ação de arquivo: {e}")
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

    def on_key(self, event) -> None:  # type: ignore[override]
        """Handle Enter key to confirm Input modals across textual versions.

        This is defensive: when a modal with an Input is shown we set
        `self._active_input_widget`. Pressing Enter will set the current
        selection future to the OK sentinel so the input modal behaves like
        pressing the OK button.
        """
        try:
            # Verify results modal gets its own keyboard shortcuts.
            try:
                if self._maybe_handle_verify_modal_key(event):
                    if hasattr(event, "stop"):
                        event.stop()
                    return
            except Exception:
                pass

            if getattr(self, "_active_input_widget", None) is None:
                return
            key = getattr(event, "key", None) or getattr(event, "key_name", None)
            if not key:
                return
            if str(key).lower() in ("enter", "\r"):
                if self._selection_future is not None:
                    if not self._selection_future.done():
                        try:
                            self._selection_future.set_result("_OPT_OK")
                        except Exception:
                            pass
                try:
                    if hasattr(event, "stop"):
                        event.stop()
                except Exception:
                    pass
        except Exception:
            pass

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

        # Some actions benefit from an explicit prompt for a target.
        if action_id == "add_rom":
            try:
                # headless-friendly prompt
                src = typer.prompt("Caminho do arquivo/pasta de ROMs", default="")
            except Exception:
                src = ""
            src = (src or "").strip()
            if not src:
                self._log("add-rom cancelado (sem caminho)")
                return
            self._pending_add_rom = Path(src)

        if action_id in ("compress", "decompress"):
            selected = await self._prompt_select_system()
            if not selected:
                self._log(f"{action_id} cancelado pelo usuário")
                return
            self._selected_system_target = selected

        # For destructive actions, ask for confirmation first
        destructive = {
            "init",
            "organize",
            "clean",
            "update_dats",
            "compress",
            "decompress",
        }
        if action_id in destructive:
            if getattr(self, "assume_yes", False):
                self._log(
                    f"Assumindo confirmação para ação '{action_id}' (assume_yes=True)"
                )
                try:
                    _log_action_decision(action_id, "tui", "assumed-yes")
                except Exception:
                    pass
            else:
                ok = await self._prompt_confirm(
                    "Confirmação necessária",
                    f"Deseja executar '{action_id}'? Esta ação pode alterar arquivos.",
                )
                if not ok:
                    self._log(f"Ação {action_id} cancelada pelo usuário")
                    return

        self.cancel_event.clear()
        self._reset_progress()
        self._log(f"Executando: {action_id}")
        # Run synchronous action in a thread so Textual's worker receives an awaitable
        worker = self.run_worker(
            asyncio.to_thread(self._run_action_sync, action_id), exclusive=True
        )
        await worker.wait()

    def _run_action_sync(self, action_id: str):
        try:
            dispatch = {
                "init": self._act_init,
                "list": self._act_list,
                "refresh_systems": self._act_refresh_systems,
                "scan": self._act_scan,
                "add_rom": self._act_add_rom,
                "organize": self._act_organize,
                "health": self._act_health,
                "compress": self._act_compress,
                "decompress": self._act_decompress,
                "verify": self._act_verify,
                "identify": self._act_identify,
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

    async def _prompt_confirm(self, title: str, message: str) -> bool:
        """Show a centered confirmation modal and return True when user confirms.

        Uses a simple ListView with Confirm / Cancel options and the same
        selection-future flow as other UI prompts.
        """
        try:
            from textual.containers import Vertical as _Vertical
            from textual.widgets import Static as _Static
        except Exception:
            _Vertical = Vertical  # type: ignore
            _Static = Label  # type: ignore

        # Build modal contents
        modal = _Vertical(id="modal_confirm")
        try:
            title_w = _Static(title)
            modal.mount(title_w)
        except Exception:
            try:
                modal.mount(Label(title))
            except Exception:
                pass

        try:
            modal.mount(Label(message))
        except Exception:
            pass

        # options
        yes = ListItem(Label("Confirmar"), id="_CONFIRM_YES")
        no = ListItem(Label("Cancelar"), id="_CONFIRM_NO")
        lv = ListView(yes, no)
        try:
            modal.mount(lv)
        except Exception:
            try:
                modal.mount(lv)
            except Exception:
                pass

        try:
            safe_mount(self, modal)
            safe_focus(lv)
        except Exception:
            # If we cannot mount the modal (headless or incompatible textual),
            # fall back to a console-based confirm to avoid blocking.
            try:
                safe_remove(modal)
            except Exception:
                pass
            # Use our confirm helper to ask on the console; record decision
            res = confirm_or_assume(
                message, default=False, action_name=title, source="tui-headless"
            )
            _log_action_decision(title, "tui-headless", "yes" if res else "no")
            return bool(res)

        loop = asyncio.get_event_loop()
        self._selection_future = loop.create_future()
        try:
            sel = await self._selection_future
        finally:
            try:
                safe_remove(modal)
            except Exception:
                pass
            self._selection_future = None

        accepted = bool(sel == "_CONFIRM_YES")
        # Log the user's decision for auditability
        _log_action_decision(title, "tui", "yes" if accepted else "no")
        return accepted

    # NOTE: help/palette prompt helpers are implemented earlier in the class.
    # The duplicate definitions that used to live here were removed to avoid
    # subtle behavior differences across runs.

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

        # Build new ListItem nodes using sanitized ids and update the id map
        self._sys_id_map.clear()
        new_items = []
        for s in updated:
            sid = f"sys_{re.sub(r'[^A-Za-z0-9_-]', '_', s)}"
            self._sys_id_map[sid] = s
            new_items.append(ListItem(Label(s), id=sid))

        # Try to update in-place using common Textual APIs. Be defensive
        try:
            # Preferred API: clear() then append (use compat helpers)
            safe_clear(self.systems_view)
            for it in new_items:
                safe_append(self.systems_view, it)
            # focus systems view for convenience
            try:
                safe_focus(self.systems_view)
            except Exception:
                pass
            self._log("Sistemas atualizados")
            return
        except Exception:
            pass

        try:
            # Alternative: remove_children / add (use compat helpers)
            if hasattr(self.systems_view, "remove_children"):
                try:
                    self.systems_view.remove_children()
                except Exception:
                    pass
            # append children one by one
            for it in new_items:
                try:
                    safe_mount(self.systems_view, it)
                except Exception:
                    try:
                        safe_append(self.systems_view, it)
                    except Exception:
                        pass
            try:
                safe_focus(self.systems_view)
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
                    safe_remove(self.systems_view)
                except Exception:
                    pass
                new_lv = ListView(*new_items)
                self.systems_view = new_lv
                try:
                    safe_mount(parent, new_lv)
                except Exception:
                    try:
                        safe_mount(parent, new_lv)
                    except Exception:
                        pass
                try:
                    safe_focus(new_lv)
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

    def _act_add_rom(self) -> None:
        """Add ROM files/folders into the library.

        The CLI has a dedicated `add-rom` command. In the TUI we store the chosen
        path in `_pending_add_rom` during `_run_action_async`.
        """

        src = getattr(self, "_pending_add_rom", None)
        if not src:
            self._log("Nenhum caminho definido para add-rom")
            return
        try:
            self._log(f"Adicionando ROM(s) de: {src}")
            manager.cmd_add_rom(self.base, src)
            self._log("add-rom concluído")
            # Refresh systems list after adding
            try:
                self._act_refresh_systems()
            except Exception:
                pass
        except Exception as e:
            self._log(f"Erro em add-rom: {e}")
        finally:
            try:
                self._pending_add_rom = None
            except Exception:
                pass

    def _act_compress(self) -> None:
        """Compress Switch content in the selected target."""

        target = self._selected_system_target or _switch_root(self.base)
        args = _common_args()
        args.compress = True
        switch_dir = target
        env = _switch_env(switch_dir, self.keys, args)
        res = worker_switch_compress(
            switch_dir,
            env,
            args,
            self._log,
            _list_files_flat,
            progress_cb=self._progress_cb,
        )
        self._log(str(res))

    def _act_decompress(self) -> None:
        """Decompress Switch content in the selected target."""

        target = self._selected_system_target or _switch_root(self.base)
        args = _common_args()
        args.decompress = True
        switch_dir = target
        env = _switch_env(switch_dir, self.keys, args)
        res = worker_switch_decompress(
            switch_dir,
            env,
            args,
            self._log,
            _list_files_flat,
            progress_cb=self._progress_cb,
        )
        self._log(str(res))

    def _act_identify(self) -> None:
        """Identify/label files based on ROM metadata."""

        target = self._selected_system_target or _roms_root(self.base)
        args = SimpleNamespace(
            progress_callback=self._progress_cb,
            cancel_event=self.cancel_event,
        )
        rep = worker_identify_all(target, args, self._log, _list_files_flat)
        try:
            self._log(str(rep))
        except Exception:
            pass

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
        # Keep last report around for table actions (export via hotkey).
        self._last_verify_report = rep
        self._last_verify_target = target
        # Reset selection so subsequent verifies start fresh
        self._selected_system_target = None

        # Try to present a DataTable modal when available; otherwise fall
        # back to the existing rich table text output.
        try:
            DT = data_table_class()
        except Exception:
            DT = None

        if DT is not None:
            # Build a modal with DataTable + action list (Export CSV / Close)
            try:
                from textual.containers import Vertical as _Vertical
                from textual.widgets import Static as _Static
            except Exception:
                _Vertical = Vertical  # type: ignore
                _Static = Label  # type: ignore

            modal = _Vertical(id="modal_verify_table")
            try:
                modal.mount(_Static(f"Verify results: {target}"))
            except Exception:
                try:
                    modal.mount(Label(f"Verify results: {target}"))
                except Exception:
                    pass

            try:
                table = DT()
                try:
                    table.cursor_type = "row"
                except Exception:
                    pass
                table.add_column("Arquivo")
                table.add_column("Status")
                table.add_column("Match")
                table.add_column("DAT")

                rows = []
                for r in rep.results:
                    rows.append(
                        (
                            str(getattr(r, "filename", "") or ""),
                            str(getattr(r, "status", "") or ""),
                            str(getattr(r, "match_name", "") or ""),
                            str(getattr(r, "dat_name", "") or ""),
                        )
                    )

                # Put a sane limit on initial rendering.
                for i, row in enumerate(rows[:2000]):
                    try:
                        table.add_row(*row)
                    except Exception:
                        pass

                try:
                    modal.mount(table)
                except Exception:
                    safe_append(modal, table)
            except Exception:
                # If DataTable construction fails, fall back to text output
                try:
                    self._log(self._render_verify_report(rep, target))
                except Exception:
                    self._log(rep.text or "Verificação concluída")
                return

            # action list
            export_item = ListItem(Label("Export CSV"), id="_EXPORT_CSV")
            close_item = ListItem(Label("Close"), id="_CLOSE_TABLE")
            actions_lv = ListView(export_item, close_item)
            try:
                modal.mount(actions_lv)
            except Exception:
                safe_append(modal, actions_lv)

            # Mount and focus; user can export with Enter or close.
            try:
                safe_mount(self, modal)
                safe_focus(table)
            except Exception:
                try:
                    self._log(self._render_verify_report(rep, target))
                except Exception:
                    self._log(rep.text or "Verificação concluída")
                try:
                    safe_remove(modal)
                except Exception:
                    pass
                return

            # Keep these around so key handlers can operate on the modal.
            self._verify_modal = modal
            self._verify_table = table
            self._verify_actions = actions_lv
            self._verify_rows = rows
            self._verify_filter = ""
            self._verify_sort_col = 0
            self._verify_sort_desc = False
            self._log(
                "Verify table: / filter, s sort, S reverse sort, e export, Esc close"
            )
            return

        # Render summary and table of results into the log view (fallback)
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
        """Show a centered modal selection UI and return the selected system Path.

        This mounts a small modal container above the main area so selection is
        clearer for the user. Uses the same selection future mechanism already
        handled by on_list_view_selected.
        """
        systems = manager.cmd_list_systems(self.base) or []
        if not systems:
            self._log("Nenhum sistema encontrado para verificar")
            return None

        # Build sanitized ids for modal items and map them to system names
        modal_items = []
        for idx, s in enumerate(systems):
            sid = f"modal_sys_{idx}"
            self._sys_id_map[sid] = s
            modal_items.append(ListItem(Label(s), id=sid))
        # add cancel option
        modal_items.append(ListItem(Label("Cancelar"), id="_VERIFY_CANCEL"))

        lv = ListView(*modal_items)

        # Create a simple modal container (vertical) to hold title + list
        try:
            from textual.containers import Vertical as _Vertical
            from textual.widgets import Static as _Static
        except Exception:
            _Vertical = Vertical  # type: ignore
            _Static = Label  # type: ignore

        modal = _Vertical(id="modal_select")
        try:
            title = _Static("Selecione sistema:")
            modal.mount(title)
        except Exception:
            try:
                modal.mount(Label("Selecione sistema:"))
            except Exception:
                pass
        try:
            modal.mount(lv)
        except Exception:
            try:
                modal.mount(lv)
            except Exception:
                pass

        # Mount modal centered over app and focus
        try:
            safe_mount(self, modal)
            safe_focus(lv)
        except Exception:
            self._log("Erro ao montar modal de seleção de sistemas")
            try:
                safe_remove(modal)
            except Exception:
                pass
            return None

        loop = asyncio.get_event_loop()
        self._selection_future = loop.create_future()
        try:
            sel_id = await self._selection_future
        finally:
            try:
                safe_remove(modal)
            except Exception:
                pass
            self._selection_future = None

        if not sel_id:
            return None

        # Resolve selected id back to system name and path
        sys_name = None
        if isinstance(sel_id, str) and sel_id.startswith("modal_sys_"):
            sys_name = self._sys_id_map.get(sel_id)
        elif isinstance(sel_id, str) and sel_id == "_VERIFY_CANCEL":
            return None
        else:
            # Unexpected id: treat as raw name
            sys_name = sel_id

        if not sys_name:
            return None

        tgt = _roms_root(self.base) / sys_name
        if tgt.exists():
            return tgt
        maybe = Path(sys_name)
        if maybe.exists():
            return maybe
        self._log(f"Pasta do sistema selecionado não encontrada: {tgt}")
        return None

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

    # --- Verify table helpers -------------------------------------------------

    def _verify_table_is_open(self) -> bool:
        return bool(getattr(self, "_verify_modal", None) is not None)

    def _verify_table_close(self) -> None:
        modal = getattr(self, "_verify_modal", None)
        if modal is None:
            return
        try:
            safe_remove(modal)
        except Exception:
            pass
        self._verify_modal = None
        self._verify_table = None
        self._verify_actions = None
        self._verify_rows = None
        self._verify_filter = ""
        self._verify_sort_col = 0
        self._verify_sort_desc = False

    def _verify_table_refresh(self) -> None:
        table = getattr(self, "_verify_table", None)
        rows = getattr(self, "_verify_rows", None) or []

        if table is None:
            return

        needle = (getattr(self, "_verify_filter", "") or "").strip().lower()
        filtered = (
            [
                r
                for r in rows
                if not needle or any(needle in (c or "").lower() for c in r)
            ]
            if rows
            else []
        )

        col = int(getattr(self, "_verify_sort_col", 0) or 0)
        desc = bool(getattr(self, "_verify_sort_desc", False))
        try:
            filtered.sort(key=lambda r: (r[col] or "").lower(), reverse=desc)
        except Exception:
            pass

        try:
            table.clear()
        except Exception:
            try:
                # some versions use clear(columns: bool, rows: bool)
                table.clear(columns=False)  # type: ignore
            except Exception:
                pass

        # Re-add columns if clear nuked them
        try:
            if getattr(table, "column_count", 0) == 0:
                table.add_column("Arquivo")
                table.add_column("Status")
                table.add_column("Match")
                table.add_column("DAT")
        except Exception:
            pass

        for row in filtered[:2000]:
            try:
                table.add_row(*row)
            except Exception:
                pass

        sort_dir = "desc" if desc else "asc"
        self._log(
            f"Verify table: {len(filtered)}/{len(rows)} rows "
            f"(filter='{needle}' sort={col} {sort_dir})"
        )

    def _maybe_handle_verify_modal_key(self, event) -> bool:
        """Handle keyboard shortcuts while the verify DataTable modal is open."""
        if not self._verify_table_is_open():
            return False

        key = getattr(event, "key", None)
        if key_matches(key, ("escape", "esc")):
            self._verify_table_close()
            return True
        if key_matches(key, "e"):
            try:
                rep = getattr(self, "_last_verify_report", None)
                tgt = getattr(self, "_last_verify_target", None)
                if rep is not None and tgt is not None:
                    out = self._export_verify_csv(rep, tgt)
                    self._log(f"CSV exported: {out}")
            except Exception as e:
                self._log(f"Failed to export CSV: {e}")
            return True
        if key_matches(key, "s"):
            try:
                self._verify_sort_col = (int(self._verify_sort_col) + 1) % 4
            except Exception:
                self._verify_sort_col = 0
            self._verify_table_refresh()
            return True
        if key_matches(key, "S"):
            self._verify_sort_desc = not bool(getattr(self, "_verify_sort_desc", False))
            self._verify_table_refresh()
            return True

        return False

    async def _prompt_file_actions(self, filepath: Path) -> Optional[str]:
        """Prompt the user with a modal to choose an action for a single file.

        Returns one of: 'compress', 'decompress', 'recompress', 'verify', or None
        if cancelled.
        """
        try:
            from textual.containers import Vertical as _Vertical
            from textual.widgets import Static as _Static
        except Exception:
            _Vertical = Vertical  # type: ignore
            _Static = Label  # type: ignore

        modal = _Vertical(id="modal_file_actions")
        try:
            title = _Static(f"Ações para: {filepath.name}")
            modal.mount(title)
        except Exception:
            try:
                modal.mount(Label(f"Ações para: {filepath.name}"))
            except Exception:
                pass

        actions = [
            ("compress", "Compress (NSZ)"),
            ("decompress", "Decompress"),
            ("recompress", "Recompress"),
            ("verify", "Verify (DAT)"),
            ("cancel", "Cancelar"),
        ]
        items = [ListItem(Label(label), id=f"fileact_{aid}") for aid, label in actions]
        lv = ListView(*items)
        try:
            modal.mount(lv)
        except Exception:
            try:
                modal.mount(lv)
            except Exception:
                pass

        try:
            safe_mount(self, modal)
            safe_focus(lv)
        except Exception:
            try:
                safe_remove(modal)
            except Exception:
                pass
            # fall back to console prompt
            choice = typer.prompt(
                f"Choose action for {filepath.name} "
                "(compress/decompress/recompress/verify)",
                default="cancel",
            )
            if choice not in ("compress", "decompress", "recompress", "verify"):
                return None
            return choice

        loop = asyncio.get_event_loop()
        self._selection_future = loop.create_future()
        try:
            sel = await self._selection_future
        finally:
            try:
                safe_remove(modal)
            except Exception:
                pass
            self._selection_future = None

        if not sel:
            return None
        if isinstance(sel, str) and sel.startswith("fileact_"):
            act = sel.split("fileact_", 1)[1]
            if act == "cancel":
                return None
            return act
        return None

    async def _prompt_action_options(self, filepath: Path, action: str) -> dict:
        """Collect action-specific options (level, rm_originals, dry_run).

        Strategy: try a simple confirm modal to use defaults; if user wants
        advanced options, or modal cannot be mounted, fall back to console
        prompts (typer.prompt / typer.confirm). Returns a dict of options.
        """
        # sensible defaults
        defaults = {"level": 3, "rm_originals": False, "dry_run": False}

        # Only compress/recompress need options for now
        if action not in ("compress", "recompress"):
            return defaults

        # Test hook: allow tests to inject automatic options to avoid
        # fragile modal timing in the Textual test harness. If the
        # attribute `_test_auto_options` is present on `self`, honor it.
        if hasattr(self, "_test_auto_options"):
            ao = getattr(self, "_test_auto_options") or {}
            try:
                lvl = int(ao.get("level", defaults["level"]))
            except Exception:
                lvl = defaults["level"]
            return {
                "level": lvl,
                "rm_originals": bool(ao.get("rm_originals", defaults["rm_originals"])),
                "dry_run": bool(ao.get("dry_run", defaults["dry_run"])),
            }

        # First ask whether to use defaults via the confirm modal
        try:
            prompt_msg = "Use default options for %s? (level=%s, rm_originals=%s)" % (
                action,
                defaults["level"],
                defaults["rm_originals"],
            )
            use_defaults = await self._prompt_confirm("Options", prompt_msg)
        except Exception:
            use_defaults = True

        if use_defaults:
            return defaults

        # Try to show a modal list of quick level choices (1,3,5,9,12,18,22)
        level_choices = [1, 3, 5, 9, 12, 18, 22]
        try:
            from textual.containers import Vertical as _Vertical
            from textual.widgets import Static as _Static
        except Exception:
            _Vertical = Vertical  # type: ignore
            _Static = Label  # type: ignore

        modal = _Vertical(id="modal_opts")
        try:
            title = _Static(f"Options for: {filepath.name}")
            modal.mount(title)
        except Exception:
            try:
                modal.mount(Label(f"Options for: {filepath.name}"))
            except Exception:
                pass

        # Build level choices as ListView
        items = []
        for lvl in level_choices:
            items.append(ListItem(Label(str(lvl)), id=f"lvl_{lvl}"))
        items.append(ListItem(Label("Custom..."), id="lvl_custom"))
        items.append(ListItem(Label("Cancelar"), id="lvl_cancel"))
        lv = ListView(*items)
        try:
            modal.mount(lv)
        except Exception:
            try:
                modal.mount(lv)
            except Exception:
                pass

        try:
            safe_mount(self, modal)
            safe_focus(lv)
        except Exception:
            try:
                safe_remove(modal)
            except Exception:
                pass
            # Fallback to console prompts
            try:
                level = int(
                    typer.prompt("NSZ level (1-22)", default=str(defaults["level"]))
                )
            except Exception:
                level = defaults["level"]

            try:
                rm = typer.confirm(
                    "Remove original after success?", default=defaults["rm_originals"]
                )
            except Exception:
                rm = defaults["rm_originals"]

            try:
                dr = typer.confirm(
                    "Dry-run (do not modify files)?", default=defaults["dry_run"]
                )
            except Exception:
                dr = defaults["dry_run"]

            return {"level": level, "rm_originals": bool(rm), "dry_run": bool(dr)}

        loop = asyncio.get_event_loop()
        self._selection_future = loop.create_future()
        try:
            sel = await self._selection_future
        finally:
            try:
                safe_remove(modal)
            except Exception:
                pass
            self._selection_future = None

        # Interpret selection
        if not sel:
            return defaults
        if isinstance(sel, str) and sel.startswith("lvl_"):
            if sel == "lvl_custom":
                # Try to mount an input modal to get a custom level
                try:
                    from textual.widgets import Input as _Input
                except Exception:
                    _Input = None  # type: ignore

                if _Input is not None:
                    try:
                        from textual.containers import Vertical as _Vertical
                        from textual.widgets import Static as _Static
                    except Exception:
                        _Vertical = Vertical  # type: ignore
                        _Static = Label  # type: ignore

                    modal2 = _Vertical(id="modal_lvl_input")
                    try:
                        title2 = _Static("Enter NSZ level:")
                        modal2.mount(title2)
                    except Exception:
                        try:
                            modal2.mount(Label("Enter NSZ level:"))
                        except Exception:
                            pass

                    try:
                        input_w = _Input(value=str(defaults["level"]))
                        modal2.mount(input_w)
                    except Exception:
                        input_w = None

                    ok = ListItem(Label("OK"), id="_OPT_OK")
                    cancel = ListItem(Label("Cancelar"), id="_OPT_CANCEL")
                    lv2 = ListView(ok, cancel)
                    try:
                        modal2.mount(lv2)
                    except Exception:
                        pass

                    try:
                        safe_mount(self, modal2)
                        # focus input if available, else focus list
                        try:
                            if input_w is not None:
                                safe_focus(input_w)
                            else:
                                safe_focus(lv2)
                        except Exception:
                            pass
                    except Exception:
                        try:
                            safe_remove(modal2)
                        except Exception:
                            pass
                        raise

                    loop2 = asyncio.get_event_loop()
                    self._selection_future = loop2.create_future()
                    # mark active input widget so Enter handler can confirm
                    try:
                        if input_w is not None:
                            self._active_input_widget = input_w
                    except Exception:
                        pass
                    try:
                        inner_sel = await self._selection_future
                    finally:
                        try:
                            safe_remove(modal2)
                        except Exception:
                            pass
                        # clear active input marker
                        try:
                            delattr(self, "_active_input_widget")
                        except Exception:
                            try:
                                if hasattr(self, "_active_input_widget"):
                                    del self._active_input_widget
                            except Exception:
                                pass
                        self._selection_future = None

                    if inner_sel == "_OPT_OK" and input_w is not None:
                        try:
                            val = getattr(input_w, "value", str(defaults["level"]))
                            level = int(val)
                        except Exception:
                            level = defaults["level"]
                    else:
                        level = defaults["level"]
                else:
                    try:
                        level = int(
                            typer.prompt(
                                "NSZ level (1-22)", default=str(defaults["level"])
                            )
                        )
                    except Exception:
                        level = defaults["level"]
            elif sel == "lvl_cancel":
                return defaults
            else:
                try:
                    level = int(sel.split("lvl_", 1)[1])
                except Exception:
                    level = defaults["level"]
        else:
            level = defaults["level"]

        # Booleans: present a small modal and use compat helpers to create
        # Checkbox-like widgets so this code works across textual versions.
        try:
            from textual.containers import Vertical as _Vertical
            from textual.widgets import Static as _Static
        except Exception:
            _Vertical = Vertical  # type: ignore
            _Static = Label  # type: ignore

        opts_modal = _Vertical(id="modal_opts_bools")
        try:
            try:
                title3 = _Static("Options flags:")
                opts_modal.mount(title3)
            except Exception:
                try:
                    opts_modal.mount(Label("Options flags:"))
                except Exception:
                    pass

            c_rm = create_checkbox("Remove original", defaults["rm_originals"])
            c_dr = create_checkbox("Dry-run", defaults["dry_run"])

            ok = ListItem(Label("OK"), id="_OPT_OK")
            cancel = ListItem(Label("Cancelar"), id="_OPT_CANCEL")
            lv3 = ListView(ok, cancel)

            try:
                opts_modal.mount(c_rm)
            except Exception:
                try:
                    safe_append(opts_modal, c_rm)
                except Exception:
                    pass
            try:
                opts_modal.mount(c_dr)
            except Exception:
                try:
                    safe_append(opts_modal, c_dr)
                except Exception:
                    pass
            try:
                opts_modal.mount(lv3)
            except Exception:
                try:
                    safe_append(opts_modal, lv3)
                except Exception:
                    pass

            try:
                safe_mount(self, opts_modal)
                try:
                    safe_focus(c_rm)
                except Exception:
                    try:
                        safe_focus(lv3)
                    except Exception:
                        pass
            except Exception:
                try:
                    safe_remove(opts_modal)
                except Exception:
                    pass
                # fallback to console prompts
                try:
                    rm = typer.confirm(
                        "Remove original after success?",
                        default=defaults["rm_originals"],
                    )
                except Exception:
                    rm = defaults["rm_originals"]
                try:
                    dr = typer.confirm(
                        "Dry-run (do not modify files)?",
                        default=defaults["dry_run"],
                    )
                except Exception:
                    dr = defaults["dry_run"]

                return {"level": level, "rm_originals": bool(rm), "dry_run": bool(dr)}
        except Exception:
            # Defensive outer catch: if building the modal fails entirely,
            # fall back to console prompts and avoid crashing the UI.
            try:
                safe_remove(opts_modal)
            except Exception:
                pass
            try:
                rm = typer.confirm(
                    "Remove original after success?",
                    default=defaults["rm_originals"],
                )
            except Exception:
                rm = defaults["rm_originals"]
            try:
                dr = typer.confirm(
                    "Dry-run (do not modify files)?",
                    default=defaults["dry_run"],
                )
            except Exception:
                dr = defaults["dry_run"]

            return {"level": level, "rm_originals": bool(rm), "dry_run": bool(dr)}

            loop3 = asyncio.get_event_loop()
            self._selection_future = loop3.create_future()
            try:
                sel3 = await self._selection_future
            finally:
                try:
                    safe_remove(opts_modal)
                except Exception:
                    pass
                self._selection_future = None

            if sel3 == "_OPT_OK":
                try:
                    rm_val = get_checkbox_value(c_rm)
                except Exception:
                    rm_val = defaults["rm_originals"]
                try:
                    dr_val = get_checkbox_value(c_dr)
                except Exception:
                    dr_val = defaults["dry_run"]

                return {
                    "level": level,
                    "rm_originals": bool(rm_val),
                    "dry_run": bool(dr_val),
                }

            return defaults

        # Fallback: plain console confirms
        try:
            rm = typer.confirm(
                "Remove original after success?",
                default=defaults["rm_originals"],
            )
        except Exception:
            rm = defaults["rm_originals"]

        try:
            dr = typer.confirm(
                "Dry-run (do not modify files)?",
                default=defaults["dry_run"],
            )
        except Exception:
            dr = defaults["dry_run"]

        return {
            "level": level,
            "rm_originals": bool(rm),
            "dry_run": bool(dr),
        }

    def _run_file_action_sync(
        self, filepath: Path, action: str, options: dict | None = None
    ):
        """Run a file-scoped action synchronously (called inside a thread)."""
        try:
            options = options or {}
            # Prepare args using any provided options (level, rm_originals, dry_run)
            args = _common_args(
                dry_run=bool(options.get("dry_run", False)),
                level=int(options.get("level", 3)),
                rm_originals=bool(options.get("rm_originals", False)),
            )
            # For Switch-specific ops we need switch env
            switch_dir = _switch_root(self.base)
            env = _switch_env(switch_dir, self.keys, args)
            if action == "compress":
                res = worker_compress_single(filepath, env, args, self._log)
                self._log(str(res))
            elif action == "decompress":
                res = worker_decompress_single(filepath, env, args, self._log)
                self._log(str(res))
            elif action == "recompress":
                res = worker_recompress_single(filepath, env, args, self._log)
                self._log(str(res))
            elif action == "verify":
                v_args = SimpleNamespace(
                    dat_path=None,
                    dats_roots=[self.dats_root or (self.base / "dats")],
                    progress_callback=self._progress_cb,
                    cancel_event=self.cancel_event,
                )
                # worker_hash_verify expects a directory root; run on parent and
                # filter results to the selected file for a per-file verify.
                if filepath.parent and filepath.parent.exists():
                    base_for_verify = filepath.parent
                else:
                    base_for_verify = filepath

                rep = worker_hash_verify(
                    base_for_verify, v_args, self._log, _list_files_flat
                )
                try:
                    # Filter results to this file only
                    filtered = [
                        r
                        for r in rep.results
                        if os.path.normpath(r.full_path) == str(filepath)
                        or r.filename == filepath.name
                    ]
                    if filtered:
                        # Build a small report-like text for the single file
                        lines = [f"File: {filepath}"]
                        for r in filtered:
                            tmp = "Status: " + str(r.status)
                            tmp += " | Match: " + str(r.match_name)
                            tmp += " | DAT: " + str(r.dat_name)
                            lines.append(tmp)
                        self._log("\n".join(lines))
                    else:
                        # If nothing matched, fall back to generic rep text
                        self._log(rep.text or "Verify complete (no matching results)")
                except Exception:
                    self._log(rep.text or "Verify complete")
            else:
                self._log(f"Ação desconhecida: {action}")
        except Exception as e:
            self._log(f"Erro ação arquivo: {e}")

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


def _collect_startup_diagnostics(
    base: Path,
    keys: Optional[Path],
    dats_root: Optional[Path],
    auto_verify: bool,
) -> dict:
    """Collect an environment diagnostics dictionary for debug output."""
    info: dict = {}
    info["python_version"] = sys.version.splitlines()[0]
    info["executable"] = sys.executable
    info["virtualenv"] = (
        os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_PREFIX") or "(none)"
    )
    info["path"] = os.environ.get("PATH", "")

    # Installed package versions (best-effort)
    pkgs = ["textual", "rich", "typer", "nsz", "requests"]
    pkg_versions: dict[str, Optional[str]] = {}
    for p in pkgs:
        try:
            pkg_versions[p] = importlib_metadata.version(p)
        except Exception:
            pkg_versions[p] = None
    info["packages"] = pkg_versions

    # Check presence of common external binaries
    bins = [
        "clamscan",
        "chdman",
        "dolphin-tool",
        "dolphin-emu",
        "hactool",
        "ctrtool",
        "3dsconv",
        "git",
        "wget",
    ]
    bin_locations: dict[str, Optional[str]] = {}
    for b in bins:
        try:
            bin_locations[b] = shutil.which(b)
        except Exception:
            bin_locations[b] = None
    info["binaries"] = bin_locations

    # Files/paths
    try:
        info["base_exists"] = Path(base).exists()
    except Exception:
        info["base_exists"] = False
    try:
        info["keys_exists"] = Path(keys).exists() if keys else False
    except Exception:
        info["keys_exists"] = False
    try:
        info["dats_exists"] = Path(dats_root).exists() if dats_root else False
    except Exception:
        info["dats_exists"] = False

    info["auto_verify_on_select"] = bool(auto_verify)
    return info


def _format_diagnostics(diag: dict) -> str:
    lines: list[str] = []
    lines.append("EmuManager TUI startup diagnostics")
    lines.append("---------------------------------")
    lines.append(f"Python: {diag.get('python_version')}")
    lines.append(f"Executable: {diag.get('executable')}")
    lines.append(f"Virtualenv: {diag.get('virtualenv')}")
    lines.append("")
    lines.append("Installed packages:")
    for p, v in diag.get("packages", {}).items():
        lines.append(f"  {p}: {v or '(not installed)'}")
    lines.append("")
    lines.append("Binaries (which):")
    for b, loc in diag.get("binaries", {}).items():
        lines.append(f"  {b}: {loc or '(not found)'}")
    lines.append("")
    lines.append(f"Base exists: {diag.get('base_exists')}")
    lines.append(f"Keys exists: {diag.get('keys_exists')}")
    lines.append(f"DATs root exists: {diag.get('dats_exists')}")
    lines.append(f"Auto-verify-on-select: {diag.get('auto_verify_on_select')}")
    lines.append("")
    # Truncate PATH to reasonable length
    path = diag.get("path", "")
    lines.append("PATH (first 400 chars):")
    lines.append(path[:400])
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Comandos principais
# ---------------------------------------------------------------------------


@app.callback()
def _configure(
    _ctx: typer.Context,
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Assume yes to all interactive prompts"
    ),
):
    """Configura logging cedo para alinhar comportamento com GUI."""
    global ASSUME_YES
    ASSUME_YES = bool(yes)
    # store in context object for possible downstream use
    try:
        _ctx.obj = _ctx.obj or {}
        _ctx.obj["assume_yes"] = ASSUME_YES
    except Exception:
        pass
    configure_logging()


@app.command("init")
def cmd_init(
    base: Path = typer.Option(Path(BASE_DEFAULT), help="Diretório base da biblioteca"),
    dry_run: bool = typer.Option(False, help="Simular sem alterar arquivos"),
):
    """Cria a estrutura padrão da biblioteca."""
    console.rule("Init da biblioteca")
    if not confirm_or_assume(
        "Init will create directories and may modify your library. Continue?",
        default=False,
        action_name="init",
        source="cli",
    ):
        console.print("Init canceled.")
        return
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
    if not confirm_or_assume(
        "Scan will read your library and update the internal database. Continue?",
        default=False,
        action_name="scan",
        source="cli",
    ):
        console.print("Scan canceled.")
        return
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
    standardize_names: bool = typer.Option(False, help="Renomear para padrão"),
    quarantine: bool = typer.Option(
        False, help="Mover arquivos corrompidos para _QUARANTINE"
    ),
    dry_run: bool = typer.Option(False, help="Simular sem alterar"),
    deep_verify: bool = typer.Option(False, help="Verificação profunda"),
):
    """Organiza arquivos: distribui raiz e roda organizer do Switch."""
    console.rule("Organização completa")
    if not confirm_or_assume(
        "Organize will move and modify files in your library. Continue?",
        default=False,
        action_name="organize",
        source="cli",
    ):
        console.print("Organize canceled.")
        return
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
    if not confirm_or_assume(
        "Health check will scan files and may quarantine suspicious files. Continue?",
        default=False,
        action_name="health_check",
        source="cli",
    ):
        console.print("Health check canceled.")
        return
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
    if not confirm_or_assume(
        "Verify will read many files and may take a long time. Continue?",
        default=False,
        action_name="verify",
        source="cli",
    ):
        console.print("Verify canceled.")
        return
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
    if not confirm_or_assume(
        "Clean will remove files and directories. This may delete data. Continue?",
        default=False,
        action_name="clean",
        source="cli",
    ):
        console.print("Clean canceled.")
        return
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
    if not confirm_or_assume(
        "Update DATs may download files and modify local DAT cache. Continue?",
        default=False,
        action_name="update_dats",
        source="cli",
    ):
        console.print("Update DATs canceled.")
        return
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
        "1": ("Inicializar biblioteca", lambda: cmd_init(base=base, dry_run=False)),
        "2": ("Listar sistemas", lambda: cmd_list_systems(base=base)),
        "3": ("Escanear biblioteca", lambda: cmd_scan(base=base)),
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
            "Verificar (DAT)",
            lambda: cmd_verify(target=roms, dat=None, dats_root=roms / "dats"),
        ),
        "6": (
            "Limpar arquivos temporários",
            lambda: cmd_clean(base=roms, dry_run=False),
        ),
        "7": ("Atualizar DATs", lambda: cmd_update_dats(base=base, source=None)),
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
    auto_verify: bool = typer.Option(
        True,
        "--auto-verify/--no-auto-verify",
        help=(
            "Auto-trigger verify when selecting a system. "
            "Use --no-auto-verify to disable."
        ),
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        "-d",
        help="Emitir trace de startup para stdout/log",
    ),
):
    # If debug enabled, emit a short startup trace to stdout and save to logs/
    if debug:
        console.rule("EmuManager TUI startup")
        diag = _collect_startup_diagnostics(base, keys, dats_root, auto_verify)
        for line in _format_diagnostics(diag).splitlines():
            console.print(line)
        # also write a tiny log file for non-interactive captures
        try:
            _logs = _Path("logs")
            _logs.mkdir(exist_ok=True)
            with open(_logs / "tui_startup.log", "w", encoding="utf-8") as fh:
                fh.write(_format_diagnostics(diag))
        except Exception:
            pass

    FullscreenTui(
        base,
        keys,
        dats_root,
        auto_verify_on_select=auto_verify,
        assume_yes=ASSUME_YES,
    ).run()


def main():
    # TUI-first: when invoked without any subcommand, launch the fullscreen
    # TUI by default so the application is interactive-first for users.
    try:
        # Prevent launching the interactive TUI in test or import contexts.
        # If running under pytest (or when the env var EMUMANAGER_SKIP_TUI_ON_IMPORT
        # is set), fall back to the CLI entry parsing to keep test runs headless.
        running_under_pytest = "PYTEST_CURRENT_TEST" in os.environ or any(
            name.startswith("pytest") for name in sys.modules
        )
        skip_auto = running_under_pytest or os.environ.get(
            "EMUMANAGER_SKIP_TUI_ON_IMPORT", ""
        ).lower() in ("1", "true", "yes", "y")

        if not skip_auto and len(sys.argv) <= 1:
            # Use defaults for base/keys/dats_root and auto-verify
            FullscreenTui(
                Path(BASE_DEFAULT),
                None,
                None,
                auto_verify_on_select=True,
                assume_yes=ASSUME_YES,
            ).run()
            return
    except Exception:
        # If anything goes wrong, fall back to CLI entry parsing
        pass

    app()


if __name__ == "__main__":
    main()
