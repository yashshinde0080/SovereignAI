"""Benchmark Command"""
import typer
import asyncio
import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()
API_BASE = "http://127.0.0.1:8000/v1"


def benchmark(
    iterations: int = typer.Option(3, "--iterations", "-n", help="Number of iterations"),
    max_tokens: int = typer.Option(100, "--tokens", "-t", help="Max tokens per iteration"),
    port: int = typer.Option(8000, "--port", "-p", help="API server port")
):
    """Run inference benchmark"""
    global API_BASE
    API_BASE = f"http://127.0.0.1:{port}/v1"
    
    asyncio.run(_run_benchmark(iterations, max_tokens))


async def _run_benchmark(iterations: int, max_tokens: int):
    """Run benchmark async"""
    console.print("\n[bold]Running benchmark...[/bold]\n")
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            # Check if model is loaded
            status_response = await client.get(f"{API_BASE}/system/status")
            if status_response.status_code != 200:
                console.print("[red]Error:[/red] Cannot get system status")
                return
            
            status = status_response.json()
            if not status.get("model_loaded"):
                console.print("[red]Error:[/red] No model loaded. Use 'sovereign run <model>' first.")
                return
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Running benchmark...", total=None)
                
                response = await client.post(
                    f"{API_BASE}/benchmark/run",
                    json={
                        "iterations": iterations,
                        "max_tokens": max_tokens
                    }
                )
            
            if response.status_code != 200:
                error = response.json().get("detail", "Unknown error")
                console.print(f"[red]Error:[/red] {error}")
                return
            
            result = response.json()
            
            # Display results
            console.print(Panel(
                f"[bold]Model:[/bold] {result['model']}\n"
                f"[bold]Mode:[/bold] {result['mode']}\n"
                f"[bold]Iterations:[/bold] {result['iterations']}",
                title="[bold blue]Benchmark Configuration[/bold blue]",
                border_style="blue"
            ))
            
            # Runs table
            table = Table(title="Benchmark Runs", show_header=True, header_style="bold cyan")
            table.add_column("Iteration", justify="center")
            table.add_column("Tokens", justify="right")
            table.add_column("Time (s)", justify="right")
            table.add_column("TPS", justify="right", style="green")
            
            for run in result.get("runs", []):
                table.add_row(
                    str(run["iteration"]),
                    str(run["tokens"]),
                    f"{run['time_seconds']:.3f}",
                    f"{run['tokens_per_second']:.2f}"
                )
            
            console.print()
            console.print(table)
            
            # Summary
            summary = result.get("summary", {})
            console.print(Panel(
                f"[bold]Total Tokens:[/bold] {summary.get('total_tokens', 0)}\n"
                f"[bold]Total Time:[/bold] {summary.get('total_time_seconds', 0):.3f}s\n"
                f"[bold]Average TPS:[/bold] [green]{summary.get('average_tokens_per_second', 0):.2f}[/green]\n"
                f"[bold]Peak RAM:[/bold] {summary.get('peak_ram_gb', 0):.2f} GB",
                title="[bold green]Summary[/bold green]",
                border_style="green"
            ))
            console.print()
            
        except httpx.ConnectError:
            console.print("[red]Error:[/red] Cannot connect to SovereignAI server.")
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")