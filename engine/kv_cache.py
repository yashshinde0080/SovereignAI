"""KV-cache for autoregressive generation.

Pre-allocated numpy arrays. Simple and correct — no ring buffer or
paged attention for v1.
"""

from __future__ import annotations

import numpy as np


class KVCache:
    """Pre-allocated key/value cache for transformer decode."""

    def __init__(
        self,
        n_layers: int,
        n_heads: int,
        head_dim: int,
        max_seq_len: int = 2048,
        dtype: type = np.float32,
    ):
        self.n_layers = n_layers
        self.n_heads = n_heads
        self.head_dim = head_dim
        self.max_seq_len = max_seq_len
        self.cur_len = 0

        # Pre-allocate: [n_layers, max_seq_len, n_heads, head_dim]
        self.k = np.zeros((n_layers, max_seq_len, n_heads, head_dim), dtype=dtype)
        self.v = np.zeros((n_layers, max_seq_len, n_heads, head_dim), dtype=dtype)

    def append(self, layer_idx: int, k: np.ndarray, v: np.ndarray) -> None:
        """Append new k/v for one layer at current position.

        k, v shapes: [n_heads, head_dim] or [1, n_heads, head_dim]
        """
        seq_len = k.shape[0] if k.ndim >= 2 else 1
        if k.ndim == 2:
            k = k[np.newaxis, ...]
            v = v[np.newaxis, ...]

        start = self.cur_len
        end = start + seq_len
        if end > self.max_seq_len:
            raise ValueError(
                f"KV cache overflow: cur_len={self.cur_len} + new={seq_len} "
                f"> max={self.max_seq_len}"
            )
        self.k[layer_idx, start:end] = k
        self.v[layer_idx, start:end] = v

    def get(self, layer_idx: int) -> tuple[np.ndarray, np.ndarray]:
        """Get full k/v for one layer (all positions up to cur_len)."""
        return self.k[layer_idx, :self.cur_len], self.v[layer_idx, :self.cur_len]

    def advance(self, n: int = 1) -> None:
        """Advance cursor by n positions (call after appending)."""
        self.cur_len += n

    def clear(self) -> None:
        self.cur_len = 0

    @property
    def size_bytes(self) -> int:
        return self.k.nbytes + self.v.nbytes

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)
