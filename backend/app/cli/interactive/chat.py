"""Interactive Chat Mode"""
import asyncio
from typing import List, Dict, Any, Optional, Callable
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from pathlib import Path

from cli.interactive.commands import SlashCommandHandler


class InteractiveChat:
    """Interactive chat session"""
    
    def __init__(
        self,
        api_client,
        model: str,
        mode: str,
        console: Optional[Console] = None
    ):
        self.client = api_client
        self.model = model
        self.mode = mode
        self.console = console or Console()
        
        self.messages: List[Dict[str, str]] = []
        self.history_path = Path.home() / ".sovereign_history"
        
        self.session = PromptSession(
            history=FileHistory(str(self.history_path)),
            auto_suggest=AutoSuggestFromHistory(),
            key_bindings=self._create_key_bindings()
        )
        
        self.command_handler = SlashCommandHandler(self)
        self.running = True
    
    def _create_key_bindings(self) -> KeyBindings:
        """Create key bindings"""
        kb = KeyBindings()
        
        @kb.add('c-c')
        def _(event):
            """Handle Ctrl+C"""
            event.app.exit()
        
        @kb.add('c-d')
        def _(event):
            """Handle Ctrl+D"""
            self.running = False
            event.app.exit()
        
        return kb
    
    async def run(self):
        """Run interactive session"""
        self.console.print("\n[dim]Type your message. Use /help for commands.[/dim]\n")
        
        while self.running:
            try:
                # Get input
                user_input = await self._get_input()
                
                if not user_input or not user_input.strip():
                    continue
                
                # Handle commands
                if user_input.startswith("/"):
                    should_continue = await self.command_handler.handle(user_input)
                    if not should_continue:
                        break
                    continue
                
                # Send message
                await self._send_message(user_input)
                
            except KeyboardInterrupt:
                self.console.print("\n[dim]Use /exit to quit[/dim]")
            except EOFError:
                break
    
    async def _get_input(self) -> str:
        """Get user input"""
        return await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.session.prompt("You > ")
        )
    
    async def _send_message(self, content: str):
        """Send message and get response"""
        self.messages.append({"role": "user", "content": content})
        
        self.console.print("\n[bold blue]Assistant >[/bold blue] ", end="")
        
        full_response = ""
        
        try:
            async with self.client.stream(
                "POST",
                "/v1/chat/completions",
                json={
                    "messages": self.messages,
                    "stream": True,
                    "max_tokens": 512,
                    "temperature": 0.7
                }
            ) as response:
                import json
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        
                        try:
                            chunk = json.loads(data)
                            token = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if token:
                                self.console.print(token, end="")
                                full_response += token
                        except:
                            pass
            
            self.console.print("\n")
            self.messages.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            self.console.print(f"\n[red]Error: {e}[/red]\n")
    
    def clear_history(self):
        """Clear conversation history"""
        self.messages.clear()
        self.console.clear()
        self.console.print("[dim]Conversation cleared[/dim]\n")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get session stats"""
        return {
            "messages": len(self.messages),
            "model": self.model,
            "mode": self.mode
        }