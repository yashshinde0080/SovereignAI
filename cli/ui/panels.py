"""UI Panels"""
from rich.panel import Panel
from rich.table import Table
from rich.console import Console, Group
from rich.text import Text
from typing import Dict, Any, Optional


def create_status_panel(
    model: str,
    mode: str,
    ram_used: float,
    ram_total: float,
    tps: Optional[float] = None
) -> Panel:
    """Create status panel"""
    content = Text()
    content.append("Model: ", style="bold")
    content.append(f"{model}\n", style="cyan")
    content.append("Mode: ", style="bold")
    content.append(f"{mode}\n", style="yellow")
    content.append("RAM: ", style="bold")
    
    ram_percent = (ram_used / ram_total * 100) if ram_total > 0 else 0
    ram_style = "green" if ram_percent < 70 else "yellow" if ram_percent < 90 else "red"
    content.append(f"{ram_used:.1f}/{ram_total:.1f} GB", style=ram_style)
    
    if tps is not None:
        content.append("\nTPS: ", style="bold")
        content.append(f"{tps:.1f}", style="green")
    
    return Panel(
        content,
        title="[bold]SovereignAI Edge[/bold]",
        border_style="blue"
    )


def create_chat_panel(messages: list) -> Panel:
    """Create chat history panel"""
    content = []
    
    for msg in messages[-10:]:  # Last 10 messages
        role = msg["role"]
        text = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
        
        if role == "user":
            content.append(Text(f"You: {text}", style="cyan"))
        else:
            content.append(Text(f"AI: {text}", style="green"))
    
    return Panel(
        Group(*content) if content else Text("[dim]No messages yet[/dim]"),
        title="Chat History",
        border_style="dim"
    )


def create_metrics_panel(metrics: Dict[str, Any]) -> Panel:
    """Create metrics panel"""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    
    table.add_row("CPU", f"{metrics.get('cpu_percent', 0):.1f}%")
    table.add_row("RAM", f"{metrics.get('ram_percent', 0):.1f}%")
    table.add_row("Disk Read", f"{metrics.get('disk_read_mb', 0):.1f} MB/s")
    table.add_row("Disk Write", f"{metrics.get('disk_write_mb', 0):.1f} MB/s")
    
    return Panel(table, title="Resources", border_style="cyan")


def create_progress_panel(
    stage: str,
    progress: float,
    details: Optional[str] = None
) -> Panel:
    """Create progress panel"""
    # Create progress bar
    bar_width = 30
    filled = int(bar_width * progress / 100)
    bar = "█" * filled + "░" * (bar_width - filled)
    
    content = Text()
    content.append(f"{stage}\n\n", style="bold")
    content.append(f"[{bar}] {progress:.1f}%\n", style="cyan")
    
    if details:
        content.append(f"\n{details}", style="dim")
    
    return Panel(content, border_style="blue")