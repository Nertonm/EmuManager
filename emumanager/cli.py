"""
EmuManager CLI - The Next Generation Control Interface.
Industrial-grade automation for emulation library management.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .manager import get_orchestrator
from .config import BASE_DEFAULT

app = typer.Typer(
    help="🚀 EmuManager: Gestão Industrial e Automatizada de Acervos de Emulação.",
    rich_markup_mode="rich",
    add_completion=False
)
console = Console()

HELP_ACERVO_DIR = "Diretoria do acervo."

@app.callback()
def global_options(
    profile: bool = typer.Option(False, "--profile", help="Gera um relatório de performance (cProfile).")
):
    if profile:
        import cProfile
        import pstats
        import io
        pr = cProfile.Profile()
        pr.enable()
        
        # Registamos o fecho do profile para o fim da execução
        import atexit
        def exit_handler():
            pr.disable()
            s = io.StringIO()
            ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
            ps.print_stats(30) # Top 30 funções mais pesadas
            console.print("\n[bold yellow]📊 RELATÓRIO DE PERFORMANCE (Top 30)[/]")
            console.print(s.getvalue())
        atexit.register(exit_handler)

def _get_orch(base: Path):

    from .core.session import Session
    from .core.orchestrator import Orchestrator
    return Orchestrator(Session(base))

def _print_banner():
    console.print(Panel.fit(
        "[bold cyan]EmuManager Core Engine v3.0[/bold cyan]\n"
        "[dim]Clean Architecture | Multiprocessing | DAT Validation[/dim]",
        border_style="blue"
    ))

@app.command("init")
def cmd_init(
    base: Path = typer.Option(Path(BASE_DEFAULT), help="Diretoria raiz onde o acervo será construído."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simula a criação da estrutura sem alterar o disco.")
):
    """
    [bold green]🏗  Inicializar Acervo[/bold green]
    
    Cria a hierarquia de pastas padrão e injeta guias técnicos (_INFO_TECNICA.txt) 
    em cada consola suportada pelo sistema.
    """
    _print_banner()
    orch = _get_orch(base)
    with console.status("[bold blue]A arquitetar diretórios..."):
        orch.initialize_library(dry_run=dry_run)
    console.print(f"\n[bold green]✔[/bold green] Arquitetura industrial preparada em: [bold white]{base}[/bold white]")

@app.command("scan")
def cmd_scan(
    base: Path = typer.Option(Path(BASE_DEFAULT), help="Diretoria a auditar.")
):
    """
    [bold magenta]🔍 Auditoria Global[/bold magenta]
    
    Varre o acervo, extrai metadados binários e valida cada jogo contra 
    as bases de dados oficiais No-Intro e Redump via Hash (CRC32/SHA1).
    """
    _print_banner()
    orch = _get_orch(base)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Auditoria em curso...", total=100)
        
        def prog_wrapper(p, m):
            progress.update(task, completed=p*100, description=f"Auditando: {m}")
            
        stats = orch.scan_library(progress_cb=prog_wrapper)
    
    console.print("\n[bold green]✔ Auditoria Finalizada[/bold green]")
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Métrica", style="dim")
    table.add_column("Valor", justify="right")
    for k, v in stats.items():
        table.add_row(k.capitalize(), str(v))
    console.print(table)

@app.command("organize")
def cmd_organize(
    base: Path = typer.Option(Path(BASE_DEFAULT), help=HELP_ACERVO_DIR),
    dry_run: bool = typer.Option(False, "--dry-run", help="Modo simulação: não renomeia ficheiros.")
):
    """
    [bold blue]📂 Organização de Nomes[/bold blue]
    
    Workflow Mestre: Move ficheiros da raiz para pastas de sistema e renomeia tudo 
    para o padrão canónico utilizando a inteligência dos SystemProviders.
    """
    _print_banner()
    orch = _get_orch(base)
    stats = orch.full_organization_flow(dry_run=dry_run)
    console.print(f"\n[bold blue]✔[/bold blue] Organização concluída. [dim]({stats})[/dim]")

@app.command("maintain")
def cmd_maintain(
    base: Path = typer.Option(Path(BASE_DEFAULT), help=HELP_ACERVO_DIR),
    dry_run: bool = typer.Option(False, "--dry-run", help="Modo simulação.")
):
    """
    [bold yellow]⚙  Manutenção de Sanidade[/bold yellow]
    
    Executa rotinas de limpeza: isola ficheiros corrompidos na pasta [bold]_QUARANTINE[/bold] 
    e remove duplicados físicos baseados em hash SHA1.
    """
    _print_banner()
    orch = _get_orch(base)
    stats = orch.maintain_integrity(dry_run=dry_run)
    console.print(f"\n[bold yellow]✔[/bold yellow] Manutenção finalizada. [dim]({stats})[/dim]")

@app.command("transcode")
def cmd_transcode(
    base: Path = typer.Option(Path(BASE_DEFAULT), help=HELP_ACERVO_DIR),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simula o transcoding paralelo.")
):
    """
    [bold red]⏩ Transcoding Paralelo[/bold red]
    
    Converte formatos legados (ISO/BIN) para formatos modernos e comprimidos 
    (CHD/RVZ) utilizando todos os núcleos do seu CPU.
    """
    _print_banner()
    orch = _get_orch(base)
    stats = orch.bulk_transcode(dry_run=dry_run)
    console.print(f"\n[bold red]✔[/bold red] Modernização terminada. [dim]({stats})[/dim]")

@app.command("report")
def cmd_report(
    base: Path = typer.Option(Path(BASE_DEFAULT), help=HELP_ACERVO_DIR),
    out: str = typer.Option("report.csv", help="Caminho do ficheiro CSV.")
):
    """
    [bold white]📊 Relatório de Conformidade[/bold white]
    
    Gera um inventário detalhado de toda a biblioteca, incluindo status 
    de verificação e hashes, em formato CSV.
    """
    orch = _get_orch(base)
    if orch.generate_compliance_report(Path(out)):
        console.print(f"[bold green]✔[/bold green] Relatório exportado: [underline]{out}[/underline]")
    else:
        console.print("[bold red]✘[/bold red] Erro ao exportar relatório.")
        sys.exit(1)

def main():
    app()

if __name__ == "__main__":
    main()
