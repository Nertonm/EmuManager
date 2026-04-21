from __future__ import annotations

import asyncio
import time

from textual import work

from emumanager.application import CORE_WORKFLOWS, execute_core_workflow


class TuiWorkflowMixin:
    def _handle_progress(self, event):
        payload = event.payload if hasattr(event, "payload") else event
        percent = payload.get("percent", 0) if isinstance(payload, dict) else 0
        self.call_from_thread(
            lambda: setattr(self.progress_bar, "progress", int(percent * 100))
        )

    def _handle_task_start(self, event):
        payload = event.payload if hasattr(event, "payload") else event
        task_name = payload.get("name", "Tarefa") if isinstance(payload, dict) else "Tarefa"
        self.call_from_thread(
            self.console_log.write,
            f"[yellow]▶[/] {task_name} iniciado...",
        )

    @work(exclusive=True, thread=True)
    def run_workflow(self, aid: str):
        self.cancel_event.clear()
        self._workflow_in_progress = True
        self.orchestrator._start_time = time.time()
        self.orchestrator._items_processed = 0
        self.call_from_thread(lambda: setattr(self.progress_bar, "progress", 0))

        dispatch = {
            workflow_id: (
                lambda selected_workflow=workflow_id: execute_core_workflow(
                    self.orchestrator,
                    selected_workflow,
                    dry_run=self._dry_run,
                    progress_cb=self._progress_cb,
                    cancel_event=self.cancel_event,
                )
            )
            for workflow_id in ("scan", "organize", "transcode", "update_dats")
        }
        dispatch.update(
            {
                "advanced_dedup": lambda: self._render_report(
                    self.collection_reports.build_advanced_dedup_report
                ),
                "analytics": lambda: self._render_report(
                    self.collection_reports.build_analytics_report
                ),
                "quality_check": lambda: self._render_report(
                    self.collection_reports.build_quality_report
                ),
            }
        )

        if aid in dispatch:
            try:
                self.call_from_thread(
                    self.console_log.write,
                    f"[bold yellow]▶[/] Iniciando {aid}...",
                )
                res = dispatch[aid]()
                self.call_from_thread(
                    self.console_log.write,
                    f"[bold green]✔[/] Workflow finalizado: {res}",
                )

                workflow_spec = CORE_WORKFLOWS.get(aid)
                if workflow_spec and workflow_spec.refresh_library:
                    self._sync_library_views()

                try:
                    report_path = self.orchestrator.finalize_task(res)
                    if report_path:
                        self.call_from_thread(
                            self.console_log.write,
                            f"[bold cyan]📊 Relatório:[/] [underline]{report_path}[/]",
                        )
                except Exception as e:
                    self.call_from_thread(
                        self.console_log.write,
                        f"[dim]Relatório não gerado: {e}[/]",
                    )

            except KeyboardInterrupt:
                self.call_from_thread(
                    self.console_log.write,
                    "[bold yellow]⚠[/] Operação cancelada pelo usuário",
                )
            except Exception as e:
                import traceback

                error_details = traceback.format_exc()
                self.call_from_thread(
                    self.console_log.write,
                    f"[bold red]✘ Erro:[/] {e}",
                )
                self.call_from_thread(self.console_log.write, f"[dim]{error_details}[/]")
            finally:
                self._workflow_in_progress = False
                self.call_from_thread(lambda: setattr(self.progress_bar, "progress", 0))
                self.call_from_thread(lambda: self.run_worker(self._refresh_systems()))

    def _progress_cb(self, p, m):
        del m
        self.orchestrator._items_processed += 1
        self.call_from_thread(lambda: setattr(self.progress_bar, "progress", int(p * 100)))

    def _sync_library_views(self):
        try:
            self.call_from_thread(self.console_log.write, "[cyan]🔄 Sincronizando dados...[/]")
            asyncio.run(self._refresh_systems())

            if self._selected_system:
                self.call_from_thread(
                    self.console_log.write,
                    f"[cyan]🔄 Atualizando {self._selected_system}...[/]",
                )
                asyncio.run(self._load_roms_to_table(self._selected_system))

            if self._selected_rom_path:
                self.call_from_thread(
                    self.console_log.write,
                    "[cyan]🔄 Atualizando inspector...[/]",
                )
                self._show_inspector(self._selected_rom_path)

            self.call_from_thread(self.console_log.write, "[green]✓ Dados sincronizados![/]")
        except Exception as e:
            self.call_from_thread(
                self.console_log.write,
                f"[yellow]⚠ Erro ao sincronizar: {e}[/]",
            )

    def _render_report(self, builder):
        report = builder()
        for line in report.lines:
            self.call_from_thread(self.console_log.write, line)
        return report.summary
