"""System Command"""
import typer
import asyncio
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
API_BASE = "http://127.0.0.1:8000/v1"


def system_info(
    port: int = typer.Option(8000, "--port", "-p", help="API server port")
):
    """Show system information"""
    global API_BASE
    API_BASE = f"http://127.0.0.1:{port}/v1"
    
    asyncio.run(_show_system_info())


async def _show_system_info():
    """Show system info async"""
    async with httpx.AsyncClient() as client:
        try:
            # Get hardware info
            hw_response = await client.get(f"{API_BASE}/system/hardware")
            status_response = await client.get(f"{API_BASE}/system/status")
            rec_response = await client.get(f"{API_BASE}/system/recommendation")
            
            if hw_response.status_code != 200:
                console.print("[red]Error fetching system info[/red]")
                return
            
            hw = hw_response.json()
            status = status_response.json() if status_response.status_code == 200 else {}
            rec = rec_response.json() if rec_response.status_code == 200 else {}
            
            # Hardware Panel
            gpu_info = f"{hw.get('gpu_name', 'None')}"
            if hw.get('gpu_vram_gb'):
                gpu_info += f" ({hw['gpu_vram_gb']} GB)"
            
            console.print(Panel(
                f"[bold]CPU:[/bold] {hw.get('cpu_name', 'Unknown')}\n"
                f"[bold]Cores:[/bold] {hw.get('cpu_cores', 0)} ({hw.get('cpu_threads', 0)} threads)\n"
                f"[bold]AVX2:[/bold] {'✓' if hw.get('has_avx2') else '✗'} | "
                f"[bold]AVX512:[/bold] {'✓' if hw.get('has_avx512') else '✗'}\n"
                f"[bold]RAM:[/bold] {hw.get('ram_total_gb', 0):.1f} GB\n"
                f"[bold]GPU:[/bold] {gpu_info}\n"
                f"[bold]Disk:[/bold] {hw.get('disk_type', 'Unknown')} ({hw.get('disk_speed_mb_s', 0):.0f} MB/s)",
                title="[bold blue]Hardware Profile[/bold blue]",
                border_style="blue"
            ))
            
            # Status Panel
            model_status = "[green]Loaded[/green]" if status.get('model_loaded') else "[dim]None[/dim]"
            console.print(Panel(
                f"[bold]Model:[/bold] {status.get('current_model', 'None')} ({model_status})\n"
                f"[bold]Mode:[/bold] {status.get('current_mode', 'N/A')}\n"
                f"[bold]RAM Used:[/bold] {status.get('ram_used_gb', 0):.2f} / {status.get('ram_total_gb', 0):.1f} GB\n"
                f"[bold]Disk Free:[/bold] {status.get('disk_free_gb', 0):.1f} GB",
                title="[bold cyan]Current Status[/bold cyan]",
                border_style="cyan"
            ))
            
            # Recommendations
            recommendations = rec.get('recommendations', [])
            if recommendations:
                table = Table(title="Recommended Models", show_header=True, header_style="bold green")
                table.add_column("Model", style="cyan")
                table.add_column("Mode", justify="center")
                table.add_column("Confidence", justify="center")
                
                for r in recommendations[:5]:
                    conf_style = "green" if r['confidence'] == 'high' else "yellow"
                    table.add_row(
                        r['model'],
                        r['mode'],
                        f"[{conf_style}]{r['confidence']}[/{conf_style}]"
                    )
                
                console.print()
                console.print(table)
            
            console.print()
            
        except httpx.ConnectError:
            console.print("[red]Error:[/red] Cannot connect to SovereignAI server.")
            console.print("\n[dim]Showing local hardware info...[/dim]\n")
            
            # Show local info without server
            import psutil
            import platform
            
            memory = psutil.virtual_memory()
            
            console.print(Panel(
                f"[bold]Platform:[/bold] {platform.system()} {platform.release()}\n"
                f"[bold]Processor:[/bold] {platform.processor()}\n"
                f"[bold]CPU Cores:[/bold] {psutil.cpu_count(logical=False)} ({psutil.cpu_count()} threads)\n"
                f"[bold]RAM:[/bold] {memory.total / (1024**3):.1f} GB total, {memory.available / (1024**3):.1f} GB available",
                title="[bold blue]Local Hardware[/bold blue]",
                border_style="blue"
            ))
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")