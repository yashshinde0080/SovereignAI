"""Pull Command"""
import typer
import asyncio
import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
import time

console = Console()
API_BASE = "http://127.0.0.1:8000/v1"


def pull(
    model: str = typer.Argument(..., help="Model to pull (e.g., llama3:8b)"),
    quant: str = typer.Option("Q4_K_M", "--quant", "-q", help="Quantization level"),
    port: int = typer.Option(8000, "--port", "-p", help="API server port")
):
    """Pull/download a model"""
    global API_BASE
    API_BASE = f"http://127.0.0.1:{port}/v1"
    
    asyncio.run(_pull_model(model, quant))


async def _pull_model(model: str, quant: str):
    """Pull model async"""
    console.print(f"\n[bold]Pulling model:[/bold] {model}")
    console.print(f"[bold]Quantization:[/bold] {quant}\n")
    
    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            # Start download
            response = await client.post(
                f"{API_BASE}/models/pull",
                json={"model": model, "quant": quant}
            )
            
            if response.status_code != 200:
                error = response.json().get("detail", "Unknown error")
                console.print(f"[red]Error:[/red] {error}")
                return
            
            result = response.json()
            
            if result["status"] == "exists":
                console.print(f"[green]✓[/green] Model already exists: {model}")
                return
            
            if result["status"] == "already_downloading":
                console.print(f"[yellow]![/yellow] Model is already downloading: {model}")
            
            # Poll for progress
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task = progress.add_task(f"Downloading {model}", total=100)
                
                while True:
                    status_response = await client.get(
                        f"{API_BASE}/models/pull/status/{model}"
                    )
                    
                    if status_response.status_code != 200:
                        break
                    
                    status = status_response.json()
                    
                    if status["status"] == "complete":
                        progress.update(task, completed=100)
                        break
                    
                    elif status["status"] == "error":
                        console.print(f"\n[red]Error:[/red] {status.get('error', 'Unknown error')}")
                        return
                    
                    elif status["status"] == "downloading":
                        progress.update(
                            task,
                            completed=status.get("progress", 0),
                            description=f"Downloading ({status.get('downloaded_gb', 0):.2f} GB)"
                        )
                    
                    elif status["status"] == "verifying":
                        progress.update(task, description="Verifying checksum...")
                    
                    elif status["status"] == "encrypting":
                        progress.update(task, description="Encrypting model...")
                    
                    await asyncio.sleep(1)
            
            console.print(f"\n[green]✓[/green] Model downloaded successfully: {model}")
            
        except httpx.ConnectError:
            console.print("[red]Error:[/red] Cannot connect to SovereignAI server.")
            console.print("Make sure the server is running.")
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")