"""Memory-mapped checkpoint loader with budget control.

Loads model weights from GGUF via mmap. Tensor data stays in the OS page
cache until explicitly read. A bounded LRU cache holds recently-accessed
tensors in RAM. When the budget is exceeded, least-recently-used tensors
are evicted (freed from Python, re-faultable from mmap).

Tensor categories:
    - Pinned (never evicted): embed, lm_head, norms — small, hot, always needed
    - Budgeted (evictable): transformer layer weights — large, streamed on demand
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np

from .gguf import GGUFParser, GGUFData, TensorInfo
from .memory import MemoryManager


# Patterns for pinned (always-resident) tensors
_PINNED_PATTERNS = ("token_embd.", "output.", "output_norm.")


def _is_pinned(name: str) -> bool:
    """Check if a tensor should be pinned (never evicted)."""
    return any(name.startswith(p) for p in _PINNED_PATTERNS)


class CheckpointLoader:
    """Load model weights from GGUF via mmap with configurable memory budget.

    budget_mb=0 → unlimited (tensors cached permanently after first load)
    budget_mb>0 → LRU eviction when budget exceeded; only pinned tensors stay

    Usage:
        loader = CheckpointLoader("model.gguf", budget_mb=512)
        w = loader.load_tensor("blk.0.attn_norm.weight")  # loads from mmap
        w = loader.load_tensor("blk.0.attn_norm.weight")  # cache hit
        loader.evict_all_layers()                           # free layer memory
        loader.stats()                                      # memory usage report
    """

    def __init__(self, gguf_path: str | Path, budget_mb: float = 0):
        self.parser = GGUFParser(gguf_path)
        self.parser.load()
        self.data: GGUFData = self.parser.data
        self.memory = MemoryManager(budget_mb)

        # Cache: name → numpy array (for tensors we've read from mmap)
        self._cache: dict[str, np.ndarray] = {}
        # Access timestamps for LRU within the loader
        self._access_time: dict[str, float] = {}

    # ── Core API ────────────────────────────────────────────────────

    def load_tensor(self, name: str) -> np.ndarray:
        """Load a tensor by name. Returns from cache if available, else reads from mmap.

        For budgeted tensors, enforces LRU eviction when the budget is exceeded.
        """
        if name in self._cache:
            self._touch(name)
            return self._cache[name]

        # Read from mmap
        arr = self.parser.get_tensor(name)
        nbytes = arr.nbytes
        pinned = _is_pinned(name)

        # Track in memory manager
        self.memory.track(name, nbytes, pinned=pinned)

        # If not pinned and we'd exceed budget, evict LRU layers first
        if not pinned and self.memory.needs_eviction(nbytes):
            self.memory.evict_until(nbytes)
            # Also remove evicted tensors from our local cache
            for evicted_name in self.memory.component_names():
                pass  # memory manager already removed them
            # Clean up cache entries for evicted tensors
            self._sync_cache()

        # Cache the tensor
        self._cache[name] = arr
        self._touch(name)

        return arr

    def has_tensor(self, name: str) -> bool:
        """Check if a tensor exists in the GGUF file."""
        return any(t.name == name for t in self.data.tensors)

    def tensor_info(self, name: str) -> TensorInfo | None:
        """Get metadata for a tensor without loading it."""
        for t in self.data.tensors:
            if t.name == name:
                return t
        return None

    def layer_names(self) -> list[str]:
        """Get all transformer layer tensor names, sorted by layer index."""
        names = []
        for t in self.data.tensors:
            if t.name.startswith("blk."):
                names.append(t.name)
        # Sort: blk.0.* before blk.1.* before ...
        def _sort_key(n: str) -> tuple[int, str]:
            parts = n.split(".")
            return (int(parts[1]), parts[2] if len(parts) > 2 else "")
        return sorted(names, key=_sort_key)

    def layer_groups(self) -> dict[int, list[str]]:
        """Group tensor names by layer index."""
        groups: dict[int, list[str]] = {}
        for name in self.layer_names():
            parts = name.split(".")
            idx = int(parts[1])
            groups.setdefault(idx, []).append(name)
        return groups

    def n_layers(self) -> int:
        """Number of transformer layers."""
        return max(
            (int(t.name.split(".")[1]) for t in self.data.tensors if t.name.startswith("blk.")),
            default=0,
        ) + 1

    def layer_bytes(self) -> dict[int, int]:
        """Estimate bytes per layer (sum of all tensors in that layer)."""
        groups = self.layer_groups()
        result = {}
        for idx, names in groups.items():
            total = 0
            for name in names:
                ti = self.tensor_info(name)
                if ti:
                    total += ti.nbytes
            result[idx] = total
        return result

    # ── Eviction ────────────────────────────────────────────────────

    def evict_layer(self, layer_idx: int) -> None:
        """Evict all tensors for a specific layer."""
        groups = self.layer_groups()
        if layer_idx in groups:
            for name in groups[layer_idx]:
                self._cache.pop(name, None)
                self.memory.untrack(name)
                self._access_time.pop(name, None)

    def evict_all_layers(self) -> int:
        """Evict all non-pinned tensors. Returns number of tensors evicted."""
        evicted = 0
        pinned_names = set()
        for name in list(self._cache.keys()):
            if _is_pinned(name):
                pinned_names.add(name)
            else:
                del self._cache[name]
                self.memory.untrack(name)
                self._access_time.pop(name, None)
                evicted += 1
        return evicted

    def evict_lru(self, count: int = 1) -> list[str]:
        """Evict the N least-recently-used non-pinned tensors."""
        # Get evictable names sorted by access time
        evictable = [
            (name, self._access_time.get(name, 0.0))
            for name in self._cache
            if not _is_pinned(name)
        ]
        evictable.sort(key=lambda x: x[1])

        evicted = []
        for name, _ in evictable[:count]:
            if name in self._cache:
                del self._cache[name]
                self.memory.untrack(name)
                self._access_time.pop(name, None)
                evicted.append(name)

        return evicted

    # ── Stats ───────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "cached_tensors": len(self._cache),
            "cached_mb": sum(a.nbytes for a in self._cache.values()) / (1024 * 1024),
            "budget_mb": self.memory.budget_bytes / (1024 * 1024) if self.memory.budget_bytes else 0,
            "n_tensors": self.data.n_tensors,
            "n_layers": self.n_layers(),
            **self.memory.stats(),
        }

    # ── Lifecycle ───────────────────────────────────────────────────

    def close(self) -> None:
        self._cache.clear()
        self._access_time.clear()
        self.parser.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ── Internal ────────────────────────────────────────────────────

    def _touch(self, name: str) -> None:
        self._access_time[name] = time.monotonic()
        self.memory.touch(name)

    def _sync_cache(self) -> None:
        """Remove cache entries for tensors no longer tracked by memory manager."""
        tracked = set(self.memory.component_names())
        to_remove = [n for n in self._cache if n not in tracked and not _is_pinned(n)]
        for name in to_remove:
            del self._cache[name]
            self._access_time.pop(name, None)
