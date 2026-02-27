"""Run Command"""
import typer
import asyncio
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.markdown import Markdown
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from pathlib import Path

from cli.ui.panels import create_status_panel, create_chat_panel
from cli.ui.theme import THEME

app = typer.Typer()
console = Console()

API_BASE = "http://127.0.0.1:8000/v1"


@app.callback(invoke_without_command=True)
def run(
    model: str = typer.Argument(..., help="Model to run (e.g., llama3:8b)"),
    mode: str = typer.Option("auto", "--mode", "-m", help="Execution mode: fullram, layerstream, auto"),
    interactive: bool = typer.Option(True, "--interactive", "-i", help="Interactive chat mode"),
    port: int = typer.Option(8000, "--port", "-p", help="API server port")
):
    """Run a model"""
    global API_BASE
    API_BASE = f"http://127.0.0.1:{port}/v1"
    
    asyncio.run(_run_model(model, mode, interactive))


async def _run_model(model: str, mode: str, interactive: bool):
    """Run model async"""
    console.print(f"\n[bold blue]Loading model:[/bold blue] {model}")
    console.print(f"[bold blue]Mode:[/bold blue] {mode}\n")
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        # Load model
        try:
            response = await client.post(
                f"{API_BASE}/models/load",
                json={"model": model, "mode": mode}
            )
            
            if response.status_code != 200:
                error = response.json().get("detail", "Unknown error")
                console.print(f"[red]Error loading model:[/red] {error}")
                return
            
            result = response.json()
            
            # Display status
            console.print(Panel(
                f"[green]✓[/green] Model loaded successfully\n\n"
                f"[bold]Model:[/bold] {result['model']}\n"
                f"[bold]Mode:[/bold] {result['mode']}\n"
                f"[bold]RAM Usage:[/bold] {result.get('ram_usage', {}).get('ram_used_gb', 'N/A')} GB",
                title="[bold green]Ready[/bold green]",
                border_style="green"
            ))
            
        except httpx.ConnectError:
            console.print("[red]Error:[/red] Cannot connect to SovereignAI server.")
            console.print("Make sure the server is running: [bold]python -m backend.app.main[/bold]")
            return
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            return
        
        if interactive:
            await _interactive_chat(client, model, mode)


async def _interactive_chat(client: httpx.AsyncClient, model: str, mode: str):
    """Interactive chat session"""
    console.print("\n[dim]Type your message and press Enter. Use /help for commands.[/dim]\n")
    
    # Setup prompt session with history
    history_path = Path.home() / ".sovereign_history"
    session = PromptSession(history=FileHistory(str(history_path)))
    
    messages = []
    
    while True:
        try:
            # Get user input
            user_input = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: session.prompt("You > ")
            )
            
            if not user_input.strip():
                continue
            
            # Handle commands
            if user_input.startswith("/"):
                if await _handle_command(client, user_input, model, mode):
                    continue
                else:
                    break
            
            # Add user message
            messages.append({"role": "user", "content": user_input})
            
            # Stream response
            console.print("\n[bold blue]Assistant >[/bold blue] ", end="")
            
            full_response = ""
            
            async with client.stream(
                "POST",
                f"{API_BASE}/chat/completions",
                json={
                    "messages": messages,
                    "stream": True,
                    "max_tokens": 512,
                    "temperature": 0.7
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        
                        try:
                            import json
                            chunk = json.loads(data)
                            token = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if token:
                                console.print(token, end="")
                                full_response += token
                        except:
                            pass
            
            console.print("\n")
            
            # Add assistant response
            messages.append({"role": "assistant", "content": full_response})
            
        except KeyboardInterrupt:
            console.print("\n\n[dim]Use /exit to quit[/dim]")
        except EOFError:
            break


async def _handle_command(client: httpx.AsyncClient, command: str, model: str, mode: str) -> bool:
    """Handle slash commands. Returns True to continue, False to exit."""
    cmd = command.lower().strip()
    
    if cmd == "/exit" or cmd == "/quit":
        console.print("\n[dim]Goodbye![/dim]\n")
        return False
    
    elif cmd == "/help":
        console.print(Panel(
            "[bold]/help[/bold] - Show this help\n"
            "[bold]/stats[/bold] - Show current stats\n"
            "[bold]/clear[/bold] - Clear conversation\n"
            "[bold]/mode <mode>[/bold] - Switch mode (fullram/layerstream)\n"
            "[bold]/exit[/bold] - Exit chat",
            title="Commands",
            border_style="blue"
        ))
    
    elif cmd == "/stats":
        response = await client.get(f"{API_BASE}/system/status")
        if response.status_code == 200:
            stats = response.json()
            console.print(Panel(
                f"[bold]Model:[/bold] {stats.get('current_model', 'None')}\n"
                f"[bold]Mode:[/bold] {stats.get('current_mode', 'None')}\n"
                f"[bold]RAM:[/bold] {stats.get('ram_used_gb', 0):.2f} / {stats.get('ram_total_gb', 0):.2f} GB\n"
                f"[bold]Disk:[/bold] {stats.get('disk_free_gb', 0):.2f} GB free",
                title="System Stats",
                border_style="cyan"
            ))
    
    elif cmd == "/clear":
        console.clear()
        console.print("[dim]Conversation cleared[/dim]\n")
    
    elif cmd.startswith("/mode "):
        new_mode = cmd.split(" ", 1)[1]
        if new_mode in ["fullram", "layerstream", "auto"]:
            response = await client.post(
                f"{API_BASE}/chat/mode/switch",
                params={"mode": new_mode}
            )
            if response.status_code == 200:
                console.print(f"[green]Switched to {new_mode} mode[/green]")
            else:
                console.print(f"[red]Failed to switch mode[/red]")
        else:
            console.print("[red]Invalid mode. Use: fullram, layerstream, auto[/red]")
    
    else:
        console.print(f"[red]Unknown command: {command}[/red]")
    
    return True