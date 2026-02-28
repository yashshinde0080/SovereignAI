import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import httpx

console = Console()
app = typer.Typer(help="SovereignAI Edge CLI", no_args_is_help=True)
API_BASE = "http://127.0.0.1:8000/v1"

@app.command()
def run(model: str, mode: str = typer.Option("auto", help="Execution mode: fullram, layerstream, auto")):
    """Run interactive computation session for a model."""
    panel = Panel(
        f"[bold blue]SovereignAI Edge[/bold blue]\n"
        f"Model: {model} | Mode: {mode.upper()}",
        expand=False,
    )
    console.print(panel)

    # Mocking check for model
    try:
        resp = httpx.get(f"{API_BASE}/models", timeout=2.0)
        models = resp.json()
        if model not in models or not models[model].get("downloaded"):
             console.print(f"[bold red]Error:[/bold red] Model {model} is not downloaded or not found.")
             console.print(f"Use `sovereign pull {model}` to download it.")
             raise typer.Exit(1)

        # Simulate chat start
        while True:
            prompt = console.input("[bold green]User >[/bold green] ")
            if prompt.strip() == "/exit":
                break
            console.print(f"[bold blue]Assistant >[/bold blue] Computed: {prompt} (Mock response)", style="italic")

    except httpx.RequestError as e:
        console.print(f"[bold red]Error:[/bold red] Could not connect to backend server. Is it running? ({e})")
        raise typer.Exit(1)

@app.command()
def pull(model: str):
    """Download and register a model."""
    console.print(f"Pulling model {model}...")
    try:
        resp = httpx.post(f"{API_BASE}/models/pull", json={"name": model}, timeout=2.0)
        if resp.status_code == 200:
            console.print(f"[bold green]✓[/bold green] Download started. Watch server logs or UI for progress.")
        else:
            console.print(f"[bold red]Error:[/bold red] {resp.text}")
    except httpx.RequestError as e:
        console.print(f"[bold red]Error:[/bold red] Could not connect to backend server. ({e})")

@app.command()
def list():
    """List all installed models."""
    try:
        resp = httpx.get(f"{API_BASE}/models", timeout=2.0)
        models = resp.json()
        table = Table("Name", "Size (GB)", "Quant", "Downloaded", "Modes")
        for name, data in models.items():
             modes = ", ".join(data.get("modes", []))
             downloaded = "[green]Yes[/green]" if data.get("downloaded") else "[yellow]No[/yellow]"
             table.add_row(name, str(data.get("size_gb", "?")), data.get("quant", "?"), downloaded, modes)

        console.print(table)
    except httpx.RequestError as e:
        console.print(f"[bold red]Error:[/bold red] Could not connect to backend server. ({e})")

@app.command()
def system():
    """Show hardware profile."""
    try:
        resp = httpx.get(f"{API_BASE}/system", timeout=2.0)
        data = resp.json()
        table = Table(show_header=False)
        table.add_row("CPU Cores", str(data.get("cpu_cores")))
        table.add_row("RAM", f"{data.get('ram_total_gb')} GB")
        table.add_row("Disk Speed", f"{data.get('disk_speed_mb_s')} MB/s")
        table.add_row("GPU", str(data.get("gpu")))

        console.print(Panel(table, title="Hardware Profile"))
    except httpx.RequestError as e:
        console.print(f"[bold red]Error:[/bold red] Could not connect to backend server. ({e})")

@app.command()
def benchmark(model: str):
    """Run performance benchmark."""
    console.print(f"Benchmarking model {model}...")
    try:
        resp = httpx.post(f"{API_BASE}/benchmark", json={"model": model}, timeout=2.0)
        if resp.status_code == 200:
            data = resp.json()
            console.print(f"[bold green]Benchmark Complete[/bold green]")
            console.print(f"Tokens/Sec: {data['tokens_per_sec']}")
            console.print(f"Peak RAM: {data['peak_ram_gb']} GB")
        else:
             console.print(f"[bold red]Error:[/bold red] {resp.text}")
    except httpx.RequestError as e:
        console.print(f"[bold red]Error:[/bold red] Could not connect to backend server. ({e})")

if __name__ == "__main__":
    app()
