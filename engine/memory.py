"""Memory budget manager.

Tracks memory usage per component (embed, lm_head, layers, kv_cache),
enforces configurable budgets, and manages LRU eviction of layer weights.

Components:
    - Pinned (never evicted): embed, lm_head, norms, config
    - Budgeted (evictable): transformer layer weights, KV cache
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ComponentStats:
    name: str
    nbytes: int
    pinned: bool
    last_access: float = field(default_factory=time.monotonic)


class MemoryManager:
    """Track and enforce memory budgets across model components.

    budget_mb=0 → unlimited
    budget_mb>0 → total RAM for all components capped at budget.
                  Pinned components (embed, lm_head, norms) always fit.
                  Evictable components (layers, KV cache) use remaining budget.
    """

    def __init__(self, budget_mb: float = 0):
        self.budget_bytes = int(budget_mb * 1024 * 1024) if budget_mb > 0 else 0
        self._components: dict[str, ComponentStats] = {}
        self._evict_order: list[str] = []  # LRU order (oldest first)
        self._evictions = 0

    # ── Tracking ────────────────────────────────────────────────────

    def track(self, name: str, nbytes: int, pinned: bool = False) -> None:
        """Register or update a component's memory usage."""
        if name in self._components:
            self._components[name].nbytes = nbytes
            self._components[name].last_access = time.monotonic()
        else:
            self._components[name] = ComponentStats(
                name=name, nbytes=nbytes, pinned=pinned,
            )
            if not pinned and name not in self._evict_order:
                self._evict_order.append(name)

    def untrack(self, name: str) -> None:
        """Remove a component from tracking."""
        self._components.pop(name, None)
        if name in self._evict_order:
            self._evict_order.remove(name)

    def touch(self, name: str) -> None:
        """Update access time (for LRU ordering)."""
        if name in self._components:
            self._components[name].last_access = time.monotonic()

    # ── Queries ─────────────────────────────────────────────────────

    @property
    def used_bytes(self) -> int:
        return sum(c.nbytes for c in self._components.values())

    @property
    def pinned_bytes(self) -> int:
        return sum(c.nbytes for c in self._components.values() if c.pinned)

    @property
    def evictable_bytes(self) -> int:
        return sum(c.nbytes for c in self._components.values() if not c.pinned)

    @property
    def available_bytes(self) -> int:
        """Bytes remaining in budget for evictable components."""
        if self.budget_bytes == 0:
            return float("inf")
        return max(0, self.budget_bytes - self.pinned_bytes)

    def can_fit(self, nbytes: int) -> bool:
        """Check if nbytes more can be added within budget."""
        if self.budget_bytes == 0:
            return True
        return self.used_bytes + nbytes <= self.budget_bytes

    def needs_eviction(self, nbytes: int) -> bool:
        """Check if adding nbytes would exceed budget."""
        if self.budget_bytes == 0:
            return False
        return self.used_bytes + nbytes > self.budget_bytes

    # ── Eviction ────────────────────────────────────────────────────

    def evict_until(self, needed_bytes: int) -> list[str]:
        """Evict LRU non-pinned components until needed_bytes can fit.

        Returns list of evicted component names.
        """
        evicted: list[str] = []
        while self.needs_eviction(needed_bytes) and self._evict_order:
            # Find the least recently used evictable component
            lru_name = min(
                self._evict_order,
                key=lambda n: self._components[n].last_access
                if n in self._components else float("inf"),
            )
            if lru_name not in self._components:
                self._evict_order.remove(lru_name)
                continue

            nbytes = self._components[lru_name].nbytes
            del self._components[lru_name]
            self._evict_order.remove(lru_name)
            self._evictions += 1
            evicted.append(lru_name)

        return evicted

    def evict_lru(self, count: int = 1) -> list[str]:
        """Evict the N least recently used non-pinned components."""
        evicted: list[str] = []
        for _ in range(count):
            if not self._evict_order:
                break
            lru_name = min(
                self._evict_order,
                key=lambda n: self._components[n].last_access
                if n in self._components else float("inf"),
            )
            if lru_name not in self._components:
                self._evict_order.remove(lru_name)
                continue

            del self._components[lru_name]
            self._evict_order.remove(lru_name)
            self._evictions += 1
            evicted.append(lru_name)

        return evicted

    # ── Stats ───────────────────────────────────────────────────────

    @property
    def total_evictions(self) -> int:
        return self._evictions

    def stats(self) -> dict[str, Any]:
        return {
            "budget_mb": self.budget_bytes / (1024 * 1024) if self.budget_bytes else 0,
            "used_mb": self.used_bytes / (1024 * 1024),
            "pinned_mb": self.pinned_bytes / (1024 * 1024),
            "evictable_mb": self.evictable_bytes / (1024 * 1024),
            "n_components": len(self._components),
            "n_pinned": sum(1 for c in self._components.values() if c.pinned),
            "n_evictable": sum(1 for c in self._components.values() if not c.pinned),
            "n_evictions": self._evictions,
        }

    def component_names(self) -> list[str]:
        return list(self._components.keys())
