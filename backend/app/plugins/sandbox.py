"""Plugin Sandbox

NOTE: On Windows, ``resource`` module is unavailable — sandbox provides
timeout-only isolation (30s). No filesystem, network, or memory limits
are enforced. Plugins can read/write any file, make network calls, and
consume unlimited memory. This is a known limitation; full isolation
requires subprocess-based sandboxing (tracked in reviews/issues-21-8-2026.md
ISSUE-24).
"""
import asyncio
try:
    import resource
except ImportError:
    resource = None
from typing import Any, Dict
from concurrent.futures import ThreadPoolExecutor
import threading

from app.plugins.interface import PluginInterface


class PluginSandbox:
    """Sandbox for plugin execution"""
    
    def __init__(
        self,
        max_memory_mb: int = 512,
        max_time_seconds: int = 30
    ):
        self.max_memory_mb = max_memory_mb
        self.max_time_seconds = max_time_seconds
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def execute(
        self,
        plugin: PluginInterface,
        action: str,
        params: Dict[str, Any]
    ) -> Any:
        """Execute plugin action in sandbox"""
        
        # Create timeout wrapper
        try:
            result = await asyncio.wait_for(
                plugin.execute(action, params),
                timeout=self.max_time_seconds
            )
            return result
        except asyncio.TimeoutError:
            raise TimeoutError(f"Plugin execution timed out after {self.max_time_seconds}s")
    
    def _set_limits(self):
        """Set resource limits for plugin execution (Unix only)"""
        if resource is None:
            return  # Windows: no resource limits available
        try:
            soft, hard = resource.getrlimit(resource.RLIMIT_AS)
            resource.setrlimit(
                resource.RLIMIT_AS,
                (self.max_memory_mb * 1024 * 1024, hard)
            )
        except Exception:
            pass
