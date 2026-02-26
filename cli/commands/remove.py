"""Remove Command"""
import typer
import asyncio
import httpx
from rich.console import Console
from rich.prompt import Confirm

console = Console()
API_BASE = "http://127.0.0.1:8000/v1"


def remove(
    model: str = typer.Argument(..., help="Model to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    port: int = typer.Option(8000, "--port", "-p", help="API server port")
):
    """Remove a model"""
    global API_BASE
    API_BASE = f"http://127.0.0.1:{port}/v1"
    
    asyncio.run(_remove_model(model, force))


async def _remove_model(model: str, force: bool):
    """Remove model async"""
    if not force:
        confirm = Confirm.ask(f"Are you sure you want to remove [bold]{model}[/bold]?")
        if not confirm:
            console.print("[dim]Cancelled[/dim]")
            return
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.delete(f"{API_BASE}/models/{model}")
            
            if response.status_code == 200:
                console.print(f"[green]✓[/green] Model removed: {model}")
            elif response.status_code == 400:
                error = response.json().get("detail", "")
                console.print(f"[red]Error:[/red] {error}")
            elif response.status_code == 404:
                console.print(f"[red]Error:[/red] Model not found: {model}")
            else:
                console.print(f"[red]Error:[/red] Failed to remove model")
                
        except httpx.ConnectError:
            console.print("[red]Error:[/red] Cannot connect to SovereignAI server.")
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")