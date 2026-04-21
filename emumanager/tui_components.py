from __future__ import annotations

from textual.widgets import Static


TUI_CSS = """
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

.status_verified { color: green; text-style: bold; }
.status_suggestion { color: yellow; text-style: italic; }
.status_corrupt { color: red; text-style: bold; }
"""

TUI_BINDINGS = [
    ("q", "quit", "Sair"),
    ("c", "cancel_workflow", "Interromper"),
    ("d", "toggle_dry_run", "Simulação"),
    ("f", "focus_search", "Filtrar"),
    ("r", "refresh_list", "Refresh"),
]


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
        except Exception:
            pass
