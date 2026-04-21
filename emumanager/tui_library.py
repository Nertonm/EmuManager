from __future__ import annotations

import asyncio
import re

from textual import on
from textual.widgets import DataTable, Input, Label, ListItem, ListView, Switch

from emumanager.application import RomBrowserRow


class TuiLibraryMixin:
    def action_toggle_dry_run(self) -> None:
        sw = self.query_one("#sw_dry_run", Switch)
        sw.value = not sw.value
        self._dry_run = sw.value
        self.console_log.write(
            f"Dry Run: {'[bold green]ON[/]' if self._dry_run else '[bold red]OFF[/]'}"
        )

    def action_cancel_workflow(self) -> None:
        if self._workflow_in_progress and not self.cancel_event.is_set():
            self.cancel_event.set()
            self.console_log.write("[bold yellow]⚠[/] Solicitação de cancelamento enviada...")
        else:
            self.console_log.write("[dim]Nenhuma operação em andamento[/]")

    @on(Switch.Changed, "#sw_dry_run")
    def on_dry_run_changed(self, event: Switch.Changed) -> None:
        self._dry_run = event.value
        self.console_log.write(
            f"Dry Run: {'[bold green]ON[/]' if self._dry_run else '[bold red]OFF[/]'}"
        )

    def action_refresh_list(self) -> None:
        self.run_worker(self._refresh_systems())
        self.roms_table.clear()
        self._loaded_rom_rows.clear()
        self.console_log.write("[blue]Refrescando biblioteca...[/]")

    def action_focus_search(self) -> None:
        self.rom_filter_input.focus()

    @on(Input.Changed, "#rom_filter")
    async def on_rom_filter_changed(self, event: Input.Changed) -> None:
        filter_text = event.value.lower().strip()
        if not filter_text:
            self._render_rom_rows(self._loaded_rom_rows)
            return

        filtered_rows = [
            row for row in self._loaded_rom_rows if filter_text in row.filename.lower()
        ]
        self._render_rom_rows(filtered_rows)

    async def _refresh_systems(self) -> None:
        try:
            from .manager import cmd_list_systems

            systems = await asyncio.to_thread(cmd_list_systems, self.base)
            await self.systems_view.clear()
            self._sys_id_map.clear()

            if not systems:
                self.console_log.write(
                    "[yellow]⚠[/] Nenhum sistema encontrado. Execute 'Auditoria Global' primeiro."
                )
                return

            for system in systems:
                system_id = f"sys_{re.sub(r'[^a-zA-Z0-9]', '_', system.lower())}"
                self._sys_id_map[system_id] = system
                await self.systems_view.append(ListItem(Label(f"🎮 {system}"), id=system_id))

            self.console_log.write(f"[green]✓[/] {len(systems)} sistema(s) carregado(s)")
        except Exception as e:
            self.console_log.write(f"[red]✘ Erro ao carregar sistemas:[/] {e}")

    async def _load_roms_to_table(self, system: str) -> None:
        self._selected_system = system
        rows = await asyncio.to_thread(
            self.library_insights.get_system_rom_rows,
            system,
            include_quality=True,
        )
        self._loaded_rom_rows = rows
        self._render_rom_rows(rows)

    def _render_rom_rows(self, rows: list[RomBrowserRow]) -> None:
        self.roms_table.clear()
        self._rom_path_map.clear()
        for row in rows:
            ra_icon = "🏆" if row.ra_compatible else ""
            row_key = self.roms_table.add_row(
                row.quality_markup,
                row.filename,
                row.status,
                ra_icon,
            )
            self._rom_path_map[str(row_key)] = row.path

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_rom_path = self._rom_path_map.get(str(event.row_key))
        if self._selected_rom_path:
            self._show_inspector(self._selected_rom_path)

    def _show_inspector(self, path_str: str) -> None:
        inspection = self.library_insights.get_rom_inspection(path_str)
        if not inspection:
            return

        self.meta_panel.remove_children()

        widgets = [
            Label("TÍTULO:", classes="meta_label"),
            Label(inspection.title, classes="meta_value"),
            Label("QUALIDADE:", classes="meta_label"),
            Label(inspection.quality_label, classes="meta_value"),
            Label("SCORE:", classes="meta_label"),
            Label(inspection.quality_score, classes="meta_value"),
            Label("RESUMO:", classes="meta_label"),
            Label(inspection.quality_summary, classes="meta_value"),
        ]

        if inspection.issues:
            widgets.append(Label("PROBLEMAS:", classes="meta_label"))
            for issue in inspection.issues:
                severity_color = {
                    "critical": "red",
                    "high": "yellow",
                    "medium": "cyan",
                    "low": "dim",
                }.get(issue.severity, "white")
                widgets.append(
                    Label(
                        f"[{severity_color}]• {issue.description}[/]",
                        classes="meta_value",
                    )
                )

        widgets.extend(
            [
                Label("ACHIEVEMENTS (RA):", classes="meta_label"),
                Label(inspection.ra_label, classes="meta_value"),
                Label("STATUS:", classes="meta_label"),
                Label(inspection.status, classes=f"meta_value {inspection.status_style}"),
                Label("SHA1 / ID:", classes="meta_label"),
                Label(inspection.dat_name, classes="meta_value"),
                Label("CAMINHO:", classes="meta_label"),
                Label(inspection.path, classes="meta_value"),
            ]
        )

        self.meta_panel.mount(*widgets)

    @on(ListView.Selected)
    async def handle_selection(self, event: ListView.Selected):
        aid = event.item.id
        if aid.startswith("sys_"):
            await self._load_roms_to_table(self._sys_id_map[aid])
        else:
            self.run_workflow(aid)
