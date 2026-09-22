"""Plugin Sandbox

NOTE: On Windows, ``resource`` module is unavailable — sandbox provides
timeout-only isolation (30s). No filesystem, network, or memory limits
are enforced. Plugins can read/write any file, make network calls, and
consume unlimited memory. This is a known limitation; full isolation
requires subprocess-based sandboxing (tracked in reviews/issues-21-8-2026.md
ISSUE-24).
"""
import asyncio
from typing import Any, Dict

from app.plugins.interface import PluginInterface


class PluginSandbox:
    """Sandbox for plugin execution — timeout only, see module docstring.

    Deliberately has no memory knob: nothing here can enforce one, and a
    ``max_memory_mb`` argument that silently does nothing is worse than none.
    """

    def __init__(self, max_time_seconds: int = 30):
        self.max_time_seconds = max_time_seconds

    async def execute(
        self,
        plugin: PluginInterface,
        action: str,
        params: Dict[str, Any]
    ) -> Any:
        """Execute plugin action, cancelling it if it exceeds the timeout."""
        try:
            return await asyncio.wait_for(
                plugin.execute(action, params),
                timeout=self.max_time_seconds
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Plugin execution timed out after {self.max_time_seconds}s")
