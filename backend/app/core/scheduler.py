"""Inference gate.

SovereignAI runs exactly one loaded model per process, backed by one engine.
``active_engine`` is a single object and its weights, KV cache and sampler state
are all mutable — so two overlapping ``generate()`` / ``generate_stream()``
calls interleave on shared state. This gate admits one inference at a time and
keeps a queue count for observability.

Usage:
    async with app.state.inference_scheduler.slot():
        ...await engine.generate(...)

Both the streaming and non-streaming chat paths use it. For streaming the slot
is held for the lifetime of the async generator, so a slow stream still blocks
the next request — which is the point: the alternative is two streams sharing
one KV cache.

The previous implementation ran a ``while True: await asyncio.sleep(0.01)``
worker that polled ``PriorityQueue.empty()`` and spun the event loop at ~100 Hz
per idle process, set ``self.engine`` outside ``__init__``, and let a raising
engine silently kill the task with no error surface. None of that survives:
``asyncio.Semaphore`` blocks without polling, and the caller owns the await.
"""

import asyncio
import contextlib
import logging
from typing import AsyncIterator, Dict

logger = logging.getLogger("sovereign.core.scheduler")


class InferenceScheduler:
    """Serializes inference against the single active engine."""

    def __init__(self, max_concurrent: int = 1):
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be >= 1")
        self.max_concurrent = max_concurrent
        self._sem = asyncio.Semaphore(max_concurrent)
        self._queued = 0
        self._active = 0

    @contextlib.asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """Hold the inference slot for the duration of the block."""
        self._queued += 1
        try:
            await self._sem.acquire()
        finally:
            self._queued -= 1

        self._active += 1
        try:
            yield
        finally:
            self._active -= 1
            self._sem.release()

    def get_queue_size(self) -> int:
        """Requests waiting for a slot (excludes the one running)."""
        return self._queued

    def get_active_count(self) -> int:
        """Requests currently holding a slot."""
        return self._active

    def get_stats(self) -> Dict[str, int]:
        return {
            "queue_size": self._queued,
            "active_count": self._active,
            "max_concurrent": self.max_concurrent,
        }
