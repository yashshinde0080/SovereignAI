"""Plugin sandbox containment test.

The sandbox enforces a hard execution timeout; that is the one containment
property that works cross-platform (resource limits are POSIX-only and
unused). This pins it: a runaway plugin gets killed, not hung.

Known gap (documented in the 08-12 review): no filesystem/network sandboxing
and no memory limits on Windows — user plugins run with the same privileges as
the server. Containment today = timeout only.
"""
import asyncio

import pytest

from app.plugins.interface import PluginInterface
from app.plugins.sandbox import PluginSandbox


class _SlowPlugin(PluginInterface):
    """Plugin that sleeps longer than the sandbox allows."""

    id = "slow-test"
    name = "Slow Test"
    version = "0.0.1"
    description = "sleeps forever"
    enabled = True

    async def execute(self, action: str, params: dict):
        await asyncio.sleep(60)
        return "never"

    async def initialize(self):
        pass

    async def cleanup(self):
        pass

    def get_actions(self):
        return ["run"]

    def get_info(self):
        return {"id": self.id, "name": self.name, "version": self.version,
                "description": self.description}


def test_sandbox_kills_runaway_plugin():
    sandbox = PluginSandbox(max_time_seconds=1)
    with pytest.raises(TimeoutError):
        asyncio.run(sandbox.execute(_SlowPlugin(), "run", {}))
