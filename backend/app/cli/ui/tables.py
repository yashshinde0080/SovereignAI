"""UI Tables"""
from rich.table import Table
from rich.console import Console
from typing import List, Dict, Any


def create_models_table(models: List[Dict[str, Any]]) -> Table:
    """Create models table"""
    table = Table(
        title="Installed Models",
        show_header=True,
        header_style="bold blue",
        border_style="dim"
    )
    
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Size", justify="right")
    table.add_column("Quant", justify="center")
    table.add_column("Family", justify="center")
    table.add_column("Modes", justify="center")
    
    for model in models:
        modes = ", ".join(model.get("modes_supported", []))
        table.add_row(
            model.get("name", "Unknown"),
            f"{model.get('size_gb', 0):.1f} GB",
            model.get("quant", "N/A"),
            model.get("family", "N/A"),
            modes
        )
    
    return table


def create_benchmark_table(runs: List[Dict[str, Any]]) -> Table:
    """Create benchmark results table"""
    table = Table(
        title="Benchmark Results",
        show_header=True,
        header_style="bold cyan"
    )
    
    table.add_column("Run", justify="center")
    table.add_column("Tokens", justify="right")
    table.add_column("Time (s)", justify="right")
    table.add_column("TPS", justify="right", style="green")
    
    for run in runs:
        table.add_row(
            str(run.get("iteration", "")),
            str(run.get("tokens", 0)),
            f"{run.get('time_seconds', 0):.3f}",
            f"{run.get('tokens_per_second', 0):.2f}"
        )
    
    return table


def create_plugins_table(plugins: List[Dict[str, Any]]) -> Table:
    """Create plugins table"""
    table = Table(
        title="Plugins",
        show_header=True,
        header_style="bold magenta"
    )
    
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Version", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Type", justify="center")
    
    for plugin in plugins:
        status = "[green]Enabled[/green]" if plugin.get("enabled") else "[red]Disabled[/red]"
        plugin_type = "[dim]Builtin[/dim]" if plugin.get("builtin") else "User"
        
        table.add_row(
            plugin.get("id", ""),
            plugin.get("name", ""),
            plugin.get("version", ""),
            status,
            plugin_type
        )
    
    return table