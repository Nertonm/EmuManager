from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    ProgressBar,
    RichLog,
    Switch,
)

from .common.events import bus
from .tui_components import TelemetryPanel


class TuiLayoutMixin:
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
                    ListItem(Label("🔎 Advanced Duplicates"), id="advanced_dedup"),
                    ListItem(Label("📊 Analytics Dashboard"), id="analytics"),
                    ListItem(Label("🏥 Quality Check"), id="quality_check"),
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
                self.rom_filter_input = Input(placeholder="🔍 Pesquisar...", id="rom_filter")
                yield self.rom_filter_input
                self.roms_table = DataTable(zebra_stripes=True, cursor_type="row")
                yield self.roms_table

            with Vertical(id="inspector"):
                yield Label("INSPECTOR", classes="section_title")
                self.meta_panel = ScrollableContainer(id="meta_content")
                with self.meta_panel:
                    yield Label("[dim]Selecione um jogo.[/]")

        self.progress_bar = ProgressBar(total=100, show_eta=True)
        yield self.progress_bar
        self.console_log = RichLog(highlight=True, markup=True, max_lines=self.MAX_LOG_LINES)
        yield self.console_log
        yield Footer()

    async def on_mount(self) -> None:
        self.roms_table.add_columns("Qualidade", "Ficheiro", "Estado", "Compat. RA")
        bus.subscribe("progress_update", self._handle_progress)
        bus.subscribe("task_started", self._handle_task_start)
        await self._refresh_systems()
