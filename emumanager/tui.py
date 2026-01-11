"""
Cockpit TUI v5.5 - Achievements & Intelligence Edition.
Explorador de Biblioteca, Inspector de Metadados, Telemetria e RetroAchievements.
"""

from __future__ import annotations

import asyncio
import re
import threading
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

import typer
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container, ScrollableContainer
from textual.widgets import (
    Footer, Header, Label, ListItem, ListView, ProgressBar, RichLog, Static, Input, Switch, Button, DataTable
)
from textual.screen import ModalScreen
from textual import work, on
from textual.message import Message

from .manager import get_orchestrator
from .config import BASE_DEFAULT
from .common.events import bus, CoreEvent
from .core.config_manager import ConfigManager

# --- Componente de Telemetria ---

class TelemetryPanel(Static):
    def on_mount(self) -> None:
        self.set_interval(1.0, self.update_stats)

    def update_stats(self) -> None:
        try:
            stats = self.app.orchestrator.get_telemetry()
            self.update(
                f"[bold cyan]SISTEMA[/]\n"
                f"[dim]Vazão:[/]  [yellow]{stats['speed']}[/]\n"
                f"[dim]RAM:[/]    [green]{stats['memory']}[/]"
            )
        except Exception: pass

# --- App Principal ---

class AsyncFeedbackTui(App):
    TITLE = "EmuManager Cockpit v5.5"
    
    CSS = """
    Screen { layout: vertical; background: $surface; }
    #header_area { height: auto; padding: 1; background: $accent; color: $text; border-bottom: tall $primary; }
    #body { height: 1fr; }
    #sidebar { width: 30; border-right: tall $primary; background: $surface; }
    #rom_explorer { width: 1fr; border-right: tall $primary; padding: 0 1; }
    #inspector { width: 45; padding: 1; background: $boost; }
    
    .section_title { text-style: bold; color: $accent; margin: 1 0; border-bottom: solid $primary; }
    TelemetryPanel { padding: 1; background: $boost; border: solid $primary; height: 5; margin-top: 1; }
    
    RichLog { background: $boost; height: 6; border-top: double $secondary; }
    ProgressBar { width: 100%; margin-top: 1; }

    .meta_label { color: cyan; text-style: dim; }
    .meta_value { color: $text; text-style: bold; margin-bottom: 1; }
    
    DataTable { height: 1fr; border: none; margin-top: 1; }
    .config_row { height: auto; padding: 0 1; margin-bottom: 1; align: left middle; }
    .config_row Label { width: 15; }
    
    /* Estilos semânticos */
    .status_verified { color: green; text-style: bold; }
    .status_suggestion { color: yellow; text-style: italic; }
    .status_corrupt { color: red; text-style: bold; }
    """
    
    BINDINGS = [
        ("q", "quit", "Sair"), 
        ("c", "cancel", "Interromper"), 
        ("d", "toggle_dry_run", "Simulação"),
        ("f", "focus_search", "Filtrar"),
        ("r", "refresh_list", "Refresh")
    ]

    def __init__(self, base: Path) -> None:
        super().__init__()
        self.config_mgr = ConfigManager()
        self.base = Path(self.config_mgr.get("base_dir")).resolve()
        self.orchestrator = get_orchestrator(self.base)
        self.cancel_event = threading.Event()
        self._dry_run = False
        self._sys_id_map: dict[str, str] = {}
        self._rom_path_map: dict[str, str] = {}
        self._selected_system: Optional[str] = None
        self._selected_rom_path: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="header_area"):
            yield Label(f"📂 [bold]ACERVO:[/ ] [cyan]{self.base}[/]")
        
        with Horizontal(id="body"):
            with Vertical(id="sidebar"):
                yield Label("🚀 OPERAÇÕES", classes="section_title")
                self.nav = ListView(
                    ListItem(Label("🔍 Auditoria Global"), id="scan"),
                    ListItem(Label("📂 Organizar Nomes"), id="organize"),
                    ListItem(Label("⏩ Transcode Auto"), id="transcode"),
                    ListItem(Label("🌐 Atualizar DATs"), id="update_dats"),
                )
                yield self.nav
                
                yield Label("\n⚙ CONFIGURAÇÕES", classes="section_title")
                with Horizontal(classes="config_row"):
                    yield Label("Dry Run:")
                    yield Switch(value=self._dry_run, id="sw_dry_run")
                
                yield Label("\n🎮 SISTEMAS", classes="section_title")
                self.systems_view = ListView(id="list_systems")
                yield self.systems_view
                
                yield TelemetryPanel()

            with Vertical(id="rom_explorer"):
                yield Label("BIBLIOTECA", classes="section_title")
                yield Input(placeholder="🔍 Pesquisar...", id="rom_filter")
                self.roms_table = DataTable(zebra_stripes=True, cursor_type="row")
                yield self.roms_table

            with Vertical(id="inspector"):
                yield Label("INSPECTOR", classes="section_title")
                self.meta_panel = ScrollableContainer(id="meta_content")
                with self.meta_panel:
                    yield Label("[dim]Selecione um jogo.[/]")

        self.progress_bar = ProgressBar(total=100, show_eta=True)
        yield self.progress_bar
        self.console_log = RichLog(highlight=True, markup=True)
        yield self.console_log
        yield Footer()

    async def on_mount(self) -> None:
        self.roms_table.add_columns("Ficheiro", "Estado", "Compat. RA")
        bus.subscribe("progress_update", self._handle_progress)
        bus.subscribe("task_started", self._handle_task_start)
        await self._refresh_systems()

    # --- Handlers de UI ---

    def action_toggle_dry_run(self) -> None:
        sw = self.query_one("#sw_dry_run", Switch)
        sw.value = not sw.value
        self._dry_run = sw.value
        self.console_log.write(f"Dry Run: {'[bold green]ON[/]' if self._dry_run else '[bold red]OFF[/]'}")

    @on(Switch.Changed, "#sw_dry_run")
    def on_dry_run_changed(self, event: Switch.Changed) -> None:
        self._dry_run = event.value
        self.console_log.write(f"Dry Run: {'[bold green]ON[/]' if self._dry_run else '[bold red]OFF[/]'}")

    def action_refresh_list(self) -> None:
        self.run_worker(self._refresh_systems())
        self.roms_table.clear()
        self.console_log.write("[blue]Refrescando biblioteca...[/]")

    def action_focus_search(self) -> None:
        self.query_one("#rom_filter").focus()

    async def _refresh_systems(self) -> None:
        from .manager import cmd_list_systems
        systems = await asyncio.to_thread(cmd_list_systems, self.base)
        await self.systems_view.clear()
        self._sys_id_map.clear()
        for s in systems:
            sid = f"sys_{re.sub(r'[^a-zA-Z0-9]', '_', s.lower())}"
            self._sys_id_map[sid] = s
            await self.systems_view.append(ListItem(Label(f"🎮 {s}"), id=sid))

    async def _load_roms_to_table(self, system: str) -> None:
        self._selected_system = system
        entries = await asyncio.to_thread(self.orchestrator.db.get_entries_by_system, system)
        self.roms_table.clear()
        self._rom_path_map.clear()
        
        for i, entry in enumerate(entries):
            fname = Path(entry.path).name
            status = entry.status
            # Lógica RetroAchievements: ícone de troféu se compatível
            ra_icon = "🏆" if entry.extra_metadata.get("ra_compatible") else ""
            
            row_key = self.roms_table.add_row(fname, status, ra_icon)
            self._rom_path_map[str(row_key)] = entry.path

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_rom_path = self._rom_path_map.get(str(event.row_key))
        if self._selected_rom_path:
            self._show_inspector(self._selected_rom_path)

    def _show_inspector(self, path_str: str) -> None:
        entry = self.orchestrator.db.get_entry(path_str)
        if not entry: return
        self.meta_panel.remove_children()
        
        # Estilos semânticos para o status
        status_style = f"status_{entry.status.lower()}"
        
        # Info RA
        ra_info = "Compatível 🏆" if entry.extra_metadata.get("ra_compatible") else "Incompatível ou não testado"

        self.meta_panel.mount(
            Label("TÍTULO:", classes="meta_label"),
            Label(entry.match_name or "Desconhecido", classes="meta_value"),
            Label("ACHIEVEMENTS (RA):", classes="meta_label"),
            Label(ra_info, classes="meta_value"),
            Label("STATUS:", classes="meta_label"),
            Label(entry.status, classes=f"meta_value {status_style}"),
            Label("SHA1 / ID:", classes="meta_label"),
            Label(entry.dat_name or "N/A", classes="meta_value"),
            Label("CAMINHO:", classes="meta_label"),
            Label(entry.path, classes="meta_value")
        )

    # --- Handlers de Eventos ---

    def _handle_progress(self, event: CoreEvent):
        p = event.payload.get("percent", 0)
        self.call_from_thread(lambda: setattr(self.progress_bar, "progress", int(p * 100)))

    def _handle_task_start(self, event: CoreEvent):
        self.call_from_thread(self.console_log.write, f"[yellow]▶[/] {event.payload.get('name')}" "iniciado...")

    @work(exclusive=True, thread=True)
    def run_workflow(self, aid: str):
        self.cancel_event.clear()
        self.orchestrator._start_time = time.time()
        self.orchestrator._items_processed = 0
        
        dispatch = {
            "scan": lambda: self.orchestrator.scan_library(self._progress_cb, self.cancel_event),
            "organize": lambda: self.orchestrator.full_organization_flow(self._dry_run, self._progress_cb),
            "transcode": lambda: self.orchestrator.bulk_transcode(self._dry_run, self._progress_cb),
            "update_dats": lambda: self.orchestrator.update_dats(self._progress_cb),
        }
        
        if aid in dispatch:
            try:
                res = dispatch[aid]()
                self.call_from_thread(self.console_log.write, f"[bold green]✔[/] Workflow finalizado: {res}")
                
                # Relatório HTML Automático
                report_path = self.orchestrator.finalize_task(res)
                if report_path:
                    self.call_from_thread(self.console_log.write, f"[bold cyan]📊 Relatório gerado:[/] [underline]{report_path}[/]")
            except Exception as e:
                self.call_from_thread(self.console_log.write, f"[bold red]✘ Erro:[/] {e}")
            finally:
                self.call_from_thread(self._refresh_systems)

    def _progress_cb(self, p, m):
        self.orchestrator._items_processed += 1
        self.call_from_thread(lambda: setattr(self.progress_bar, "progress", int(p*100)))

    @on(ListView.Selected)
    async def handle_selection(self, event: ListView.Selected):
        aid = event.item.id
        if aid.startswith("sys_"):
            await self._load_roms_to_table(self._sys_id_map[aid])
        else: self.run_workflow(aid)

def main():
    cm = ConfigManager()
    app = AsyncFeedbackTui(Path(cm.get("base_dir")))
    app.run()

if __name__ == "__main__":
    main()
