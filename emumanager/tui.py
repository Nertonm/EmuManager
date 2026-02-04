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
from .common.events import bus
from .core.config_manager import ConfigManager
from .deduplication import AdvancedDeduplication
from .analytics import AnalyticsDashboard
from .quality import QualityController

try:
    from .common.events import CoreEvent
except ImportError:
    # Fallback se CoreEvent não existir
    class CoreEvent:
        def __init__(self, event_type: str, payload: dict):
            self.event_type = event_type
            self.payload = payload

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
        ("c", "cancel_workflow", "Interromper"), 
        ("d", "toggle_dry_run", "Simulação"),
        ("f", "focus_search", "Filtrar"),
        ("r", "refresh_list", "Refresh")
    ]

    MAX_LOG_LINES = 1000  # Limite para evitar crescimento infinito

    def __init__(self, base: Path) -> None:
        super().__init__()
        self.config_mgr = ConfigManager()
        self.base = Path(self.config_mgr.get("base_dir")).resolve()
        self.orchestrator = get_orchestrator(self.base)
        self.cancel_event = threading.Event()
        self._dry_run = False
        self._workflow_in_progress = False
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

    # --- Handlers de UI ---

    def action_toggle_dry_run(self) -> None:
        sw = self.query_one("#sw_dry_run", Switch)
        sw.value = not sw.value
        self._dry_run = sw.value
        self.console_log.write(f"Dry Run: {'[bold green]ON[/]' if self._dry_run else '[bold red]OFF[/]'}")

    def action_cancel_workflow(self) -> None:
        """Cancela o workflow atual."""
        if self._workflow_in_progress and not self.cancel_event.is_set():
            self.cancel_event.set()
            self.console_log.write("[bold yellow]⚠[/] Solicitação de cancelamento enviada...")
        else:
            self.console_log.write("[dim]Nenhuma operação em andamento[/]")

    @on(Switch.Changed, "#sw_dry_run")
    def on_dry_run_changed(self, event: Switch.Changed) -> None:
        self._dry_run = event.value
        self.console_log.write(f"Dry Run: {'[bold green]ON[/]' if self._dry_run else '[bold red]OFF[/]'}")

    def action_refresh_list(self) -> None:
        self.run_worker(self._refresh_systems())
        self.roms_table.clear()
        self.console_log.write("[blue]Refrescando biblioteca...[/]")

    def action_focus_search(self) -> None:
        self.rom_filter_input.focus()

    @on(Input.Changed, "#rom_filter")
    async def on_rom_filter_changed(self, event: Input.Changed) -> None:
        """Filtra a tabela de ROMs em tempo real."""
        filter_text = event.value.lower()
        if not filter_text:
            # Recarregar todos os ROMs do sistema selecionado
            if self._selected_system:
                await self._load_roms_to_table(self._selected_system)
            return
        
        # Filtrar linhas visíveis
        for row_key in list(self.roms_table.rows.keys()):
            row_data = self.roms_table.get_row(row_key)
            if row_data and len(row_data) > 0:
                filename = str(row_data[0]).lower()
                # Ocultar/mostrar baseado no filtro (workaround: remover e re-adicionar)
                # Textual não tem hide/show nativo para rows
                if filter_text not in filename:
                    try:
                        path = self._rom_path_map.pop(str(row_key), None)
                    except Exception as e:
                        self.console_log.write(f"[dim red]Erro ao filtrar ROM: {e}[/]")

    async def _refresh_systems(self) -> None:
        """Atualiza a lista de sistemas disponíveis na sidebar."""
        try:
            from .manager import cmd_list_systems
            systems = await asyncio.to_thread(cmd_list_systems, self.base)
            await self.systems_view.clear()
            self._sys_id_map.clear()
            
            if not systems:
                self.console_log.write("[yellow]⚠[/] Nenhum sistema encontrado. Execute 'Auditoria Global' primeiro.")
                return
            
            for s in systems:
                sid = f"sys_{re.sub(r'[^a-zA-Z0-9]', '_', s.lower())}"
                self._sys_id_map[sid] = s
                await self.systems_view.append(ListItem(Label(f"🎮 {s}"), id=sid))
            
            self.console_log.write(f"[green]✓[/] {len(systems)} sistema(s) carregado(s)")
        except Exception as e:
            self.console_log.write(f"[red]✘ Erro ao carregar sistemas:[/] {e}")

    async def _load_roms_to_table(self, system: str) -> None:
        self._selected_system = system
        entries = await asyncio.to_thread(self.orchestrator.db.get_entries_by_system, system)
        self.roms_table.clear()
        self._rom_path_map.clear()
        
        # Executar quality check em background
        quality_controller = QualityController(self.orchestrator.db)
        
        for i, entry in enumerate(entries):
            fname = Path(entry.path).name
            status = entry.status
            
            # Quality check
            try:
                quality = await asyncio.to_thread(quality_controller.analyze_rom, entry)
                quality_indicator = f"[{quality.color}]{quality.icon}[/]"
            except Exception:
                quality_indicator = "[dim]?[/]"
            
            # Lógica RetroAchievements: ícone de troféu se compatível
            ra_icon = "🏆" if entry.extra_metadata.get("ra_compatible") else ""
            
            row_key = self.roms_table.add_row(quality_indicator, fname, status, ra_icon)
            self._rom_path_map[str(row_key)] = entry.path

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_rom_path = self._rom_path_map.get(str(event.row_key))
        if self._selected_rom_path:
            self._show_inspector(self._selected_rom_path)

    def _show_inspector(self, path_str: str) -> None:
        entry = self.orchestrator.db.get_entry(path_str)
        if not entry:
            return
        
        self.meta_panel.remove_children()
        
        # Executar quality check
        quality_controller = QualityController(self.orchestrator.db)
        try:
            quality = quality_controller.analyze_rom(entry)
            quality_info = f"[{quality.color}]{quality.icon} {quality.quality_level.value}[/]"
            quality_summary = quality.get_summary()
            quality_score = f"{quality.score}/100"
        except Exception as e:
            quality_info = "[dim]? UNKNOWN[/]"
            quality_summary = f"Erro: {str(e)}"
            quality_score = "N/A"
        
        # Estilos semânticos para o status
        status_style = f"status_{entry.status.lower()}"
        
        # Info RA
        ra_info = "Compatível 🏆" if entry.extra_metadata.get("ra_compatible") else "Incompatível ou não testado"

        widgets = [
            Label("TÍTULO:", classes="meta_label"),
            Label(entry.match_name or "Desconhecido", classes="meta_value"),
            Label("QUALIDADE:", classes="meta_label"),
            Label(quality_info, classes="meta_value"),
            Label("SCORE:", classes="meta_label"),
            Label(quality_score, classes="meta_value"),
            Label("RESUMO:", classes="meta_label"),
            Label(quality_summary, classes="meta_value"),
        ]
        
        # Mostrar issues se existirem
        if hasattr(quality, 'issues') and quality.issues:
            widgets.append(Label("PROBLEMAS:", classes="meta_label"))
            for issue in quality.issues[:5]:  # Primeiros 5
                severity_color = {
                    'critical': 'red',
                    'high': 'yellow',
                    'medium': 'cyan',
                    'low': 'dim'
                }.get(issue.severity, 'white')
                
                issue_text = f"[{severity_color}]• {issue.description}[/]"
                widgets.append(Label(issue_text, classes="meta_value"))
        
        widgets.extend([
            Label("ACHIEVEMENTS (RA):", classes="meta_label"),
            Label(ra_info, classes="meta_value"),
            Label("STATUS:", classes="meta_label"),
            Label(entry.status, classes=f"meta_value {status_style}"),
            Label("SHA1 / ID:", classes="meta_label"),
            Label(entry.dat_name or "N/A", classes="meta_value"),
            Label("CAMINHO:", classes="meta_label"),
            Label(entry.path, classes="meta_value")
        ])
        
        self.meta_panel.mount(*widgets)

    # --- Handlers de Eventos ---

    def _handle_progress(self, event):
        """Handler para eventos de progresso."""
        payload = event.payload if hasattr(event, 'payload') else event
        p = payload.get("percent", 0) if isinstance(payload, dict) else 0
        self.call_from_thread(lambda: setattr(self.progress_bar, "progress", int(p * 100)))

    def _handle_task_start(self, event):
        """Handler para eventos de início de tarefa."""
        payload = event.payload if hasattr(event, 'payload') else event
        task_name = payload.get('name', 'Tarefa') if isinstance(payload, dict) else 'Tarefa'
        self.call_from_thread(self.console_log.write, f"[yellow]▶[/] {task_name} iniciado...")

    @work(exclusive=True, thread=True)
    def run_workflow(self, aid: str):
        """Executa um workflow do orchestrator em background."""
        self.cancel_event.clear()
        self._workflow_in_progress = True
        self.orchestrator._start_time = time.time()
        self.orchestrator._items_processed = 0
        
        # Reset progress bar
        self.call_from_thread(lambda: setattr(self.progress_bar, "progress", 0))
        
        dispatch = {
            "scan": lambda: self.orchestrator.scan_library(self._progress_cb, self.cancel_event),
            "organize": lambda: self.orchestrator.full_organization_flow(self._dry_run, self._progress_cb),
            "transcode": lambda: self.orchestrator.bulk_transcode(self._dry_run, self._progress_cb),
            "update_dats": lambda: self.orchestrator.update_dats(self._progress_cb),
            "advanced_dedup": lambda: self._run_advanced_dedup(),
            "analytics": lambda: self._show_analytics_dashboard(),
            "quality_check": lambda: self._run_quality_check(),
        }
        
        if aid in dispatch:
            try:
                self.call_from_thread(self.console_log.write, f"[bold yellow]▶[/] Iniciando {aid}...")
                res = dispatch[aid]()
                self.call_from_thread(self.console_log.write, f"[bold green]✔[/] Workflow finalizado: {res}")
                
                # Sincronizar dados após scan ou organize
                if aid in ("scan", "organize"):
                    self._sync_inspector_after_scan()
                
                # Relatório HTML Automático
                try:
                    report_path = self.orchestrator.finalize_task(res)
                    if report_path:
                        self.call_from_thread(self.console_log.write, f"[bold cyan]📊 Relatório:[/] [underline]{report_path}[/]")
                except Exception as e:
                    self.call_from_thread(self.console_log.write, f"[dim]Relatório não gerado: {e}[/]")
                    
            except KeyboardInterrupt:
                self.call_from_thread(self.console_log.write, f"[bold yellow]⚠[/] Operação cancelada pelo usuário")
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                self.call_from_thread(self.console_log.write, f"[bold red]✘ Erro:[/] {e}")
                self.call_from_thread(self.console_log.write, f"[dim]{error_details}[/]")
            finally:
                self._workflow_in_progress = False
                # Reset progress bar ao finalizar
                self.call_from_thread(lambda: setattr(self.progress_bar, "progress", 0))
                self.call_from_thread(self._refresh_systems)

    def _progress_cb(self, p, m):
        self.orchestrator._items_processed += 1
        self.call_from_thread(lambda: setattr(self.progress_bar, "progress", int(p*100)))

    def _sync_inspector_after_scan(self):
        """Sincroniza dados do inspector após scan ou organize."""
        try:
            # Recarregar lista de sistemas
            self.call_from_thread(self.console_log.write, "[cyan]🔄 Sincronizando dados...[/]")
            asyncio.run(self._refresh_systems())
            
            # Se houver sistema selecionado, recarregar a tabela de ROMs
            if self._selected_system:
                self.call_from_thread(self.console_log.write, f"[cyan]🔄 Atualizando {self._selected_system}...[/]")
                asyncio.run(self._load_roms_to_table(self._selected_system))
            
            # Se houver ROM selecionada, atualizar o inspector
            if self._selected_rom_path:
                self.call_from_thread(self.console_log.write, "[cyan]🔄 Atualizando inspector...[/]")
                self._show_inspector(self._selected_rom_path)
            
            self.call_from_thread(self.console_log.write, "[green]✓ Dados sincronizados![/]")
        except Exception as e:
            self.call_from_thread(self.console_log.write, f"[yellow]⚠ Erro ao sincronizar: {e}[/]")

    @on(ListView.Selected)
    async def handle_selection(self, event: ListView.Selected):
        aid = event.item.id
        if aid.startswith("sys_"):
            await self._load_roms_to_table(self._sys_id_map[aid])
        else:
            self.run_workflow(aid)
    
    def _run_advanced_dedup(self):
        """Executa análise avançada de duplicados."""
        try:
            dedup = AdvancedDeduplication(self.orchestrator.db)
            
            self.call_from_thread(self.console_log.write, "[bold cyan]🔎 Analisando duplicados...[/]")
            
            # Encontrar todos os duplicados
            all_duplicates = dedup.find_all_duplicates()
            stats = dedup.get_statistics()
            
            # Relatório
            self.call_from_thread(self.console_log.write, f"[green]✓ Análise completa![/]")
            self.call_from_thread(self.console_log.write, f"  Total de grupos: {stats['total_groups']}")
            self.call_from_thread(self.console_log.write, f"  Espaço desperdiçado: {stats['total_wasted_gb']:.2f} GB")
            
            # Detalhes por tipo
            for dtype, type_stats in stats['by_type'].items():
                count = type_stats['count']
                wasted_gb = type_stats['wasted_bytes'] / (1024**3)
                self.call_from_thread(
                    self.console_log.write, 
                    f"  [{dtype}]: {count} grupos, {wasted_gb:.2f} GB"
                )
            
            # Mostrar detalhes dos top 10 grupos
            sorted_groups = sorted(all_duplicates, key=lambda g: g.space_savings, reverse=True)
            
            self.call_from_thread(self.console_log.write, "\n[bold yellow]TOP 10 DUPLICADOS:[/]")
            
            for i, group in enumerate(sorted_groups[:10], 1):
                self.call_from_thread(
                    self.console_log.write,
                    f"  {i}. [{group.duplicate_type}] {group.key[:50]}... "
                    f"({group.count} files, {group.space_savings/(1024**2):.1f} MB)"
                )
                
                if group.recommended_keep:
                    reason = group.get_recommendation_reason()
                    self.call_from_thread(
                        self.console_log.write,
                        f"     [green]→ Keep:[/] {Path(group.recommended_keep).name}"
                    )
                    if reason:
                        self.call_from_thread(
                            self.console_log.write,
                            f"     [dim]{reason}[/]"
                        )
            
            return f"Found {stats['total_groups']} duplicate groups"
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.call_from_thread(self.console_log.write, f"[bold red]✘ Erro na deduplicação:[/] {e}")
            self.call_from_thread(self.console_log.write, f"[dim]{error_details}[/]")
            return f"Error: {e}"
    
    def _show_analytics_dashboard(self):
        """Mostra dashboard de analytics."""
        try:
            dashboard = AnalyticsDashboard(self.orchestrator.db)
            
            self.call_from_thread(self.console_log.write, "[bold cyan]📊 Gerando relatório...[/]")
            
            # Gerar relatório completo
            report = dashboard.generate_text_report()
            
            # Mostrar no console
            for line in report.split('\n'):
                self.call_from_thread(self.console_log.write, line)
            
            # Gráficos ASCII
            analytics = dashboard.generate_full_report()
            
            # Gráfico de completion
            completion_data = {
                sys: stats.completion_percent 
                for sys, stats in analytics.systems.items()
            }
            
            if completion_data:
                chart = dashboard.generate_ascii_chart(
                    completion_data, 
                    "\n📈 COMPLETION BY SYSTEM", 
                    width=60
                )
                for line in chart.split('\n'):
                    self.call_from_thread(self.console_log.write, line)
            
            # Gráfico de verification
            verification_data = {
                sys: stats.verification_percent 
                for sys, stats in analytics.systems.items()
            }
            
            if verification_data:
                chart = dashboard.generate_ascii_chart(
                    verification_data, 
                    "\n✓ VERIFICATION BY SYSTEM", 
                    width=60
                )
                for line in chart.split('\n'):
                    self.call_from_thread(self.console_log.write, line)
            
            return f"Analytics complete: {analytics.total_systems} systems, {analytics.total_roms} ROMs"
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.call_from_thread(self.console_log.write, f"[bold red]✘ Erro no analytics:[/] {e}")
            self.call_from_thread(self.console_log.write, f"[dim]{error_details}[/]")
            return f"Error: {e}"
    
    def _run_quality_check(self):
        """Executa verificação de qualidade completa."""
        try:
            quality_controller = QualityController(self.orchestrator.db)
            
            self.call_from_thread(self.console_log.write, "[bold cyan]🏥 Verificando qualidade das ROMs...[/]")
            
            # Obter estatísticas de qualidade
            stats = quality_controller.get_quality_statistics()
            
            # Relatório geral
            self.call_from_thread(self.console_log.write, f"[green]✓ Análise completa![/]")
            self.call_from_thread(self.console_log.write, f"  Total analisado: {stats['total']} ROMs")
            self.call_from_thread(self.console_log.write, f"  Score médio: {stats['average_score']:.1f}/100")
            self.call_from_thread(self.console_log.write, f"  Jogáveis: {stats['playable']} ({stats['playable']/stats['total']*100:.1f}%)")
            self.call_from_thread(self.console_log.write, f"  Danificadas: {stats['damaged']} ({stats['damaged']/stats['total']*100:.1f}%)")
            
            # Breakdown por nível
            self.call_from_thread(self.console_log.write, "\n[bold yellow]DISTRIBUIÇÃO DE QUALIDADE:[/]")
            
            level_names = {
                'PERFECT': '✓✓ Perfect',
                'GOOD': '✓ Good',
                'QUESTIONABLE': '⚠ Questionable',
                'DAMAGED': '✗ Damaged',
                'CORRUPT': '✗✗ Corrupt',
                'UNKNOWN': '? Unknown'
            }
            
            for level, count in stats['by_level'].items():
                percent = (count / stats['total'] * 100) if stats['total'] > 0 else 0
                level_display = level_names.get(level, level)
                self.call_from_thread(
                    self.console_log.write,
                    f"  {level_display:20} {count:4} ({percent:5.1f}%)"
                )
            
            # Top issues
            if stats['issues_by_type']:
                self.call_from_thread(self.console_log.write, "\n[bold yellow]TOP PROBLEMAS ENCONTRADOS:[/]")
                
                issue_names = {
                    'INVALID_HEADER': 'Header inválido',
                    'INVALID_CHECKSUM': 'Checksum inválido',
                    'TRUNCATED_FILE': 'Arquivo truncado',
                    'ZERO_BYTES': 'Bytes nulos',
                    'HEADER_CORRUPTION': 'Header corrompido',
                    'SUSPICIOUS_SIZE': 'Tamanho suspeito',
                    'METADATA_MISSING': 'Metadados ausentes',
                }
                
                sorted_issues = sorted(stats['issues_by_type'].items(), key=lambda x: x[1], reverse=True)
                
                for issue_type, count in sorted_issues[:10]:
                    issue_display = issue_names.get(issue_type, issue_type)
                    self.call_from_thread(
                        self.console_log.write,
                        f"  {issue_display:30} {count:4}"
                    )
            
            # Encontrar ROMs mais problemáticas
            self.call_from_thread(self.console_log.write, "\n[bold red]ATENÇÃO - ROMs CORROMPIDAS:[/]")
            
            results = quality_controller.analyze_library()
            damaged_roms = [
                (path, quality) for path, quality in results.items()
                if quality.quality_level in ['DAMAGED', 'CORRUPT']
            ]
            
            if damaged_roms:
                for path, quality in damaged_roms[:10]:
                    fname = Path(path).name
                    self.call_from_thread(
                        self.console_log.write,
                        f"  [{quality.color}]{quality.icon}[/] {fname[:60]}"
                    )
                    
                    # Mostrar primeiro issue crítico
                    critical = quality.get_critical_issues()
                    if critical and len(critical) > 0:
                        self.call_from_thread(
                            self.console_log.write,
                            f"     → {critical[0].description}"
                        )
                
                if len(damaged_roms) > 10:
                    self.call_from_thread(
                        self.console_log.write,
                        f"  ... e mais {len(damaged_roms) - 10} ROMs com problemas"
                    )
            else:
                self.call_from_thread(
                    self.console_log.write,
                    "  [green]Nenhuma ROM corrompida encontrada! ✓[/]"
                )
            
            return f"Quality check complete: {stats['total']} ROMs analyzed"
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.call_from_thread(self.console_log.write, f"[bold red]✘ Erro no quality check:[/] {e}")
            self.call_from_thread(self.console_log.write, f"[dim]{error_details}[/]")
            return f"Error: {e}"

def main():
    cm = ConfigManager()
    app = AsyncFeedbackTui(Path(cm.get("base_dir")))
    app.run()

if __name__ == "__main__":
    main()
