#!/usr/bin/env python3
"""SovereignAI CLI Entry Point"""
import typer
from rich.console import Console

from cli.commands import run, pull, list_cmd, remove, benchmark, system

app = typer.Typer(
    name="sovereign",
    help="SovereignAI Edge - Portable Offline AI Platform",
    add_completion=False
)

console = Console()

# Register commands
app.add_typer(run.app, name="run")
app.command(name="pull")(pull.pull)
app.command(name="list")(list_cmd.list_models)
app.command(name="remove")(remove.remove)
app.command(name="benchmark")(benchmark.benchmark)
app.command(name="system")(system.system_info)


@app.callback()
def callback():
    """
    SovereignAI Edge - Portable Offline AI Platform
    
    Run AI models locally without internet connection.
    """
    pass


@app.command()
def version():
    """Show version information"""
    from cli import __version__
    console.print(f"[bold blue]SovereignAI Edge[/bold blue] v{__version__}")


if __name__ == "__main__":
    app()