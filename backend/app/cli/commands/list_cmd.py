"""List Command"""
import typer
import asyncio
import httpx
from rich.console import Console
from rich.table import Table

console = Console()
API_BASE = "http://127.0.0.1:8000/v1"


def list_models(
    port: int = typer.Option(8000, "--port", "-p", help="API server port")
):
    """List installed models"""
    global API_BASE
    API_BASE = f"http://127.0.0.1:{port}/v1"
    
    asyncio.run(_list_models())


async def _list_models():
    """List models async"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE}/models/")
            
            if response.status_code != 200:
                console.print("[red]Error fetching models[/red]")
                return
            
            data = response.json()
            models = data.get("models", [])
            
            if not models:
                console.print("\n[dim]No models installed.[/dim]")
                console.print("[dim]Use 'sovereign pull <model>' to download a model.[/dim]\n")
                return
            
            # Create table
            table = Table(title="Installed Models", show_header=True, header_style="bold blue")
            table.add_column("Name", style="cyan")
            table.add_column("Size", justify="right")
            table.add_column("Quant", justify="center")
            table.add_column("Modes", justify="center")
            
            for model in models:
                modes = ", ".join(model.get("modes_supported", []))
                table.add_row(
                    model["name"],
                    f"{model.get('size_gb', 0):.1f} GB",
                    model.get("quant", "N/A"),
                    modes
                )
            
            console.print()
            console.print(table)
            console.print()
            
        except httpx.ConnectError:
            console.print("[red]Error:[/red] Cannot connect to SovereignAI server.")
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")