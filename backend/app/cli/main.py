#!/usr/bin/env python3
"""SovereignAI CLI Entry Point"""
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import httpx
import asyncio
import os
import sys

app = typer.Typer(
    name="sovereign",
    help="SovereignAI Edge - Portable Offline AI Platform",
    add_completion=False
)

console = Console()
API_BASE = "http://localhost:8000/v1"


@app.command()
def version():
    """Show version information"""
    console.print(Panel(
        "[bold blue]SovereignAI Edge[/bold blue] v1.0.0\n"
        "Portable Offline AI Platform",
        title="Version"
    ))


@app.command()
def system():
    """Show system information"""
    async def _get_system():
        async with httpx.AsyncClient() as client:
            try:
                hw = await client.get(f"{API_BASE}/system/hardware")
                status = await client.get(f"{API_BASE}/system/status")
                
                if hw.status_code == 200:
                    data = hw.json()
                    console.print(Panel(
                        f"[bold]CPU:[/bold] {data.get('cpu_name', 'Unknown')}\n"
                        f"[bold]Cores:[/bold] {data.get('cpu_cores', 0)}\n"
                        f"[bold]RAM:[/bold] {data.get('ram_total_gb', 0):.1f} GB\n"
                        f"[bold]GPU:[/bold] {data.get('gpu_name', 'None')}",
                        title="[bold blue]Hardware Profile[/bold blue]"
                    ))
                
                if status.status_code == 200:
                    data = status.json()
                    console.print(Panel(
                        f"[bold]Model Loaded:[/bold] {data.get('model_loaded', False)}\n"
                        f"[bold]Current Model:[/bold] {data.get('current_model', 'None')}\n"
                        f"[bold]Mode:[/bold] {data.get('current_mode', 'N/A')}\n"
                        f"[bold]RAM Used:[/bold] {data.get('ram_used_gb', 0):.1f} GB",
                        title="[bold cyan]Status[/bold cyan]"
                    ))
            except httpx.ConnectError:
                console.print("[red]Error: Cannot connect to server[/red]")
                console.print("Make sure the backend is running")
    
    asyncio.run(_get_system())


@app.command(name="list")
def list_models():
    """List installed models"""
    async def _list():
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{API_BASE}/models/")
                
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    
                    if not models:
                        console.print("[dim]No models installed[/dim]")
                        console.print("Use 'sovereign pull <model>' to download")
                        return
                    
                    table = Table(title="Installed Models")
                    table.add_column("Name", style="cyan")
                    table.add_column("Size", justify="right")
                    table.add_column("Quant")
                    table.add_column("Modes")
                    
                    for model in models:
                        modes = ", ".join(model.get("modes_supported", []))
                        table.add_row(
                            model.get("name", ""),
                            f"{model.get('size_gb', 0):.1f} GB",
                            model.get("quant", ""),
                            modes
                        )
                    
                    console.print(table)
            except httpx.ConnectError:
                console.print("[red]Error: Cannot connect to server[/red]")
    
    asyncio.run(_list())


@app.command()
def pull(
    model: str = typer.Argument(..., help="Model to download (e.g., llama3:8b)"),
    quant: str = typer.Option("Q4_K_M", "--quant", "-q", help="Quantization")
):
    """Download a model"""
    async def _pull():
        console.print(f"[bold]Pulling model:[/bold] {model}")
        console.print(f"[bold]Quantization:[/bold] {quant}")
        
        async with httpx.AsyncClient(timeout=600) as client:
            try:
                # Start download
                response = await client.post(
                    f"{API_BASE}/models/pull",
                    json={"model": model, "quant": quant}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if result["status"] == "exists":
                        console.print(f"[green]✓ Model already exists[/green]")
                        return
                    
                    console.print("[yellow]Download started...[/yellow]")
                    
                    # Poll for progress
                    while True:
                        status_resp = await client.get(
                            f"{API_BASE}/models/pull/status/{model}"
                        )
                        
                        if status_resp.status_code == 200:
                            status = status_resp.json()
                            
                            if status["status"] == "complete":
                                console.print(f"[green]✓ Download complete[/green]")
                                break
                            elif status["status"] == "error":
                                console.print(f"[red]Error: {status.get('error')}[/red]")
                                break
                            else:
                                progress = status.get("progress", 0)
                                console.print(f"Progress: {progress:.1f}%", end="\r")
                        
                        await asyncio.sleep(2)
                else:
                    console.print(f"[red]Error: {response.text}[/red]")
                    
            except httpx.ConnectError:
                console.print("[red]Error: Cannot connect to server[/red]")
    
    asyncio.run(_pull())


@app.command()
def run(
    model: str = typer.Argument(..., help="Model to run"),
    mode: str = typer.Option("auto", "--mode", "-m", help="Execution mode")
):
    """Run a model and start interactive chat"""
    async def _run():
        async with httpx.AsyncClient(timeout=300) as client:
            try:
                # Load model
                console.print(f"[bold]Loading model:[/bold] {model}")
                console.print(f"[bold]Mode:[/bold] {mode}")
                
                response = await client.post(
                    f"{API_BASE}/models/load",
                    json={"model": model, "mode": mode}
                )
                
                if response.status_code != 200:
                    error_data = response.json()
                    error = error_data.get("detail", "Unknown error")
                    console.print(f"[red]Error: {error}[/red]")
                    return
                
                result = response.json()
                console.print(Panel(
                    f"[green]✓ Model loaded[/green]\n\n"
                    f"Model: {result.get('model')}\n"
                    f"Mode: {result.get('mode')}\n"
                    f"RAM: {result.get('ram_usage', {}).get('ram_used_gb', 0):.1f} GB",
                    title="Ready"
                ))
                
                # Interactive chat loop
                console.print("\n[dim]Type your message. Use 'exit' to quit.[/dim]\n")
                
                messages = []
                
                while True:
                    try:
                        user_input = console.input("[bold cyan]You > [/bold cyan]")
                        
                        if user_input.lower() in ['exit', 'quit', '/exit']:
                            console.print("[dim]Goodbye![/dim]")
                            break
                        
                        if not user_input.strip():
                            continue
                        
                        messages.append({"role": "user", "content": user_input})
                        
                        # Get response
                        console.print("[bold green]Assistant > [/bold green]", end="")
                        
                        chat_response = await client.post(
                            f"{API_BASE}/chat/completions",
                            json={
                                "messages": messages,
                                "stream": False,
                                "max_tokens": 512
                            }
                        )
                        
                        if chat_response.status_code == 200:
                            data = chat_response.json()
                            content = data["choices"][0]["message"]["content"]
                            console.print(content)
                            messages.append({"role": "assistant", "content": content})
                        else:
                            console.print("[red]Error getting response[/red]")
                        
                        console.print()
                        
                    except KeyboardInterrupt:
                        console.print("\n[dim]Use 'exit' to quit[/dim]")
                        
            except httpx.ConnectError:
                console.print("[red]Error: Cannot connect to server[/red]")
                console.print("Make sure backend is running: python -m uvicorn app.main:app")
    
    asyncio.run(_run())


@app.command()
def benchmark(
    iterations: int = typer.Option(3, "--iterations", "-n"),
    tokens: int = typer.Option(100, "--tokens", "-t")
):
    """Run inference benchmark"""
    async def _benchmark():
        async with httpx.AsyncClient(timeout=300) as client:
            try:
                # Check if model is loaded
                status = await client.get(f"{API_BASE}/system/status")
                if status.status_code == 200:
                    data = status.json()
                    if not data.get("model_loaded"):
                        console.print("[red]No model loaded. Use 'sovereign run <model>' first[/red]")
                        return
                
                console.print("[bold]Running benchmark...[/bold]")
                
                response = await client.post(
                    f"{API_BASE}/benchmark/run",
                    json={"iterations": iterations, "max_tokens": tokens}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Results table
                    table = Table(title="Benchmark Results")
                    table.add_column("Iteration")
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
                    
                    console.print(table)
                    
                    # Summary
                    summary = result.get("summary", {})
                    console.print(Panel(
                        f"[bold]Average TPS:[/bold] [green]{summary.get('average_tokens_per_second', 0):.2f}[/green]\n"
                        f"[bold]Total Tokens:[/bold] {summary.get('total_tokens', 0)}\n"
                        f"[bold]Peak RAM:[/bold] {summary.get('peak_ram_gb', 0):.2f} GB",
                        title="Summary"
                    ))
                else:
                    console.print(f"[red]Error: {response.text}[/red]")
                    
            except httpx.ConnectError:
                console.print("[red]Error: Cannot connect to server[/red]")
    
    asyncio.run(_benchmark())


@app.command()
def remove(
    model: str = typer.Argument(..., help="Model to remove"),
    force: bool = typer.Option(False, "--force", "-f")
):
    """Remove a model"""
    async def _remove():
        if not force:
            confirm = typer.confirm(f"Remove model '{model}'?")
            if not confirm:
                console.print("[dim]Cancelled[/dim]")
                return
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(f"{API_BASE}/models/{model}")
                
                if response.status_code == 200:
                    console.print(f"[green]✓ Model removed: {model}[/green]")
                elif response.status_code == 404:
                    console.print(f"[red]Model not found: {model}[/red]")
                else:
                    console.print(f"[red]Error: {response.text}[/red]")
                    
            except httpx.ConnectError:
                console.print("[red]Error: Cannot connect to server[/red]")
    
    asyncio.run(_remove())


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h"),
    port: int = typer.Option(8000, "--port", "-p")
):
    """Start the API server"""
    import subprocess
    
    console.print(f"[bold]Starting server at {host}:{port}[/bold]")
    
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", host,
        "--port", str(port)
    ])


if __name__ == "__main__":
    app()
