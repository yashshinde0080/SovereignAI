"""Slash Commands"""
from typing import TYPE_CHECKING
from rich.panel import Panel

if TYPE_CHECKING:
    from cli.interactive.chat import InteractiveChat


class SlashCommandHandler:
    """Handle slash commands"""
    
    def __init__(self, chat: "InteractiveChat"):
        self.chat = chat
        self.console = chat.console
    
    async def handle(self, command: str) -> bool:
        """Handle command. Returns True to continue, False to exit."""
        cmd = command.lower().strip()
        parts = cmd.split(" ", 1)
        cmd_name = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        
        handlers = {
            "/help": self._help,
            "/exit": self._exit,
            "/quit": self._exit,
            "/clear": self._clear,
            "/stats": self._stats,
            "/mode": self._mode,
            "/model": self._model,
            "/history": self._history,
        }
        
        handler = handlers.get(cmd_name)
        
        if handler:
            return await handler(args)
        else:
            self.console.print(f"[red]Unknown command: {cmd_name}[/red]")
            self.console.print("[dim]Use /help to see available commands[/dim]")
            return True
    
    async def _help(self, args: str) -> bool:
        """Show help"""
        self.console.print(Panel(
            "[bold]/help[/bold] - Show this help\n"
            "[bold]/exit[/bold] - Exit chat\n"
            "[bold]/clear[/bold] - Clear conversation\n"
            "[bold]/stats[/bold] - Show session stats\n"
            "[bold]/mode <mode>[/bold] - Switch mode (fullram/layerstream/auto)\n"
            "[bold]/model <name>[/bold] - Switch model\n"
            "[bold]/history[/bold] - Show conversation history",
            title="[bold blue]Commands[/bold blue]",
            border_style="blue"
        ))
        return True
    
    async def _exit(self, args: str) -> bool:
        """Exit chat"""
        self.console.print("\n[dim]Goodbye![/dim]\n")
        return False
    
    async def _clear(self, args: str) -> bool:
        """Clear conversation"""
        self.chat.clear_history()
        return True
    
    async def _stats(self, args: str) -> bool:
        """Show stats"""
        stats = self.chat.get_stats()
        
        try:
            response = await self.chat.client.get("/v1/system/status")
            if response.status_code == 200:
                system = response.json()
                self.console.print(Panel(
                    f"[bold]Model:[/bold] {stats['model']}\n"
                    f"[bold]Mode:[/bold] {stats['mode']}\n"
                    f"[bold]Messages:[/bold] {stats['messages']}\n"
                    f"[bold]RAM:[/bold] {system.get('ram_used_gb', 0):.2f} / {system.get('ram_total_gb', 0):.1f} GB",
                    title="[bold cyan]Session Stats[/bold cyan]",
                    border_style="cyan"
                ))
        except:
            self.console.print(Panel(
                f"[bold]Model:[/bold] {stats['model']}\n"
                f"[bold]Mode:[/bold] {stats['mode']}\n"
                f"[bold]Messages:[/bold] {stats['messages']}",
                title="[bold cyan]Session Stats[/bold cyan]",
                border_style="cyan"
            ))
        
        return True
    
    async def _mode(self, args: str) -> bool:
        """Switch mode"""
        if not args:
            self.console.print("[red]Usage: /mode <fullram|layerstream|auto>[/red]")
            return True
        
        mode = args.strip()
        if mode not in ["fullram", "layerstream", "auto"]:
            self.console.print("[red]Invalid mode. Use: fullram, layerstream, auto[/red]")
            return True
        
        try:
            response = await self.chat.client.post(
                "/v1/chat/mode/switch",
                params={"mode": mode}
            )
            if response.status_code == 200:
                self.chat.mode = mode
                self.console.print(f"[green]Switched to {mode} mode[/green]")
            else:
                self.console.print("[red]Failed to switch mode[/red]")
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
        
        return True
    
    async def _model(self, args: str) -> bool:
        """Switch model"""
        if not args:
            self.console.print("[red]Usage: /model <model_name>[/red]")
            return True
        
        model = args.strip()
        self.console.print(f"[yellow]Switching to {model}...[/yellow]")
        
        try:
            response = await self.chat.client.post(
                "/v1/models/load",
                json={"model": model, "mode": self.chat.mode}
            )
            if response.status_code == 200:
                self.chat.model = model
                self.chat.clear_history()
                self.console.print(f"[green]Switched to {model}[/green]")
            else:
                error = response.json().get("detail", "Unknown error")
                self.console.print(f"[red]Failed: {error}[/red]")
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
        
        return True
    
    async def _history(self, args: str) -> bool:
        """Show history"""
        messages = self.chat.messages[-10:]  # Last 10
        
        if not messages:
            self.console.print("[dim]No messages in history[/dim]")
            return True
        
        for msg in messages:
            role = msg["role"]
            content = msg["content"][:200]
            if len(msg["content"]) > 200:
                content += "..."
            
            if role == "user":
                self.console.print(f"[cyan]You:[/cyan] {content}")
            else:
                self.console.print(f"[green]AI:[/green] {content}")
        
        return True