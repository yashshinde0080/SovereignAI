"""Shared utility functions.

Tensor math ops (all numpy, no PyTorch), timing helpers, memory stats.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import numpy as np


# ── Tensor math ops ─────────────────────────────────────────────────

def matmul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Matrix multiply: C = A × B. numpy uses BLAS under the hood."""
    return np.matmul(a, b)


def rmsnorm(x: np.ndarray, weight: np.ndarray, eps: float = 1e-5) -> np.ndarray:
    """RMSNorm: x / sqrt(mean(x²) + eps) * weight.

    Args:
        x: input tensor [..., dim]
        weight: norm weight [dim]
    """
    return x * weight / np.sqrt(np.mean(x ** 2, axis=-1, keepdims=True) + eps)


def rope(x: np.ndarray, pos: int, theta: float = 10000.0) -> np.ndarray:
    """Rotary Position Embedding (in-place style, returns new tensor).

    Args:
        x: [seq_len, n_heads, head_dim] or [seq_len, head_dim]
        pos: starting position
        theta: base frequency
    """
    dim = x.shape[-1]
    seq_len = x.shape[0]
    freqs = 1.0 / (theta ** (np.arange(0, dim, 2, dtype=np.float32) / dim))
    t = np.arange(pos, pos + seq_len, dtype=np.float32)
    freqs = np.outer(t, freqs)  # [seq_len, dim//2]
    cos = np.cos(freqs)
    sin = np.sin(freqs)

    # Reshape for broadcasting
    if x.ndim == 3:
        cos = cos[:, np.newaxis, :]
        sin = sin[:, np.newaxis, :]

    # Split into pairs and apply rotation
    x1 = x[..., 0::2]
    x2 = x[..., 1::2]
    out = np.empty_like(x)
    out[..., 0::2] = x1 * cos - x2 * sin
    out[..., 1::2] = x2 * cos + x1 * sin
    return out


def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    """Numerically stable softmax."""
    e = np.exp(x - np.max(x, axis=axis, keepdims=True))
    return e / np.sum(e, axis=axis, keepdims=True)


def silu(x: np.ndarray) -> np.ndarray:
    """SiLU activation: x * sigmoid(x)."""
    return x / (1.0 + np.exp(-x))


def gelu(x: np.ndarray) -> np.ndarray:
    """GELU approximation: 0.5 * x * (1 + tanh(sqrt(2/π) * (x + 0.044715 * x³)))."""
    return 0.5 * x * (1.0 + np.tanh(0.7978845608 * (x + 0.044715 * x ** 3)))


# ── Sampling ────────────────────────────────────────────────────────

def sample_token(
    logits: np.ndarray,
    temperature: float = 0.7,
    top_p: float = 0.9,
    top_k: int = 0,
) -> int:
    """Sample one token from logits. temperature=0 → greedy argmax."""
    if temperature <= 0.0:
        return int(np.argmax(logits))

    logits = logits / temperature

    # Top-K filter
    if top_k > 0:
        indices_to_remove = logits < np.sort(logits)[-top_k]
        logits[indices_to_remove] = -np.inf

    # Top-P (nucleus) filter
    if top_p < 1.0:
        sorted_indices = np.argsort(-logits)
        sorted_logits = logits[sorted_indices]
        cum_probs = np.cumsum(softmax(sorted_logits))
        # Keep tokens with cumulative probability <= top_p
        mask = cum_probs - softmax(sorted_logits) >= top_p
        sorted_logits[mask] = -np.inf
        logits[sorted_indices] = sorted_logits

    probs = softmax(logits)
    return int(np.random.choice(len(probs), p=probs))


# ── Memory stats ────────────────────────────────────────────────────

def get_peak_rss_mb() -> float:
    """Peak RSS in MB (cross-platform)."""
    try:
        import resource
        # Unix: getrusage returns peak RSS in KB
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return usage.ru_maxrss / 1024.0
    except ImportError:
        pass

    # Windows: use psutil if available
    try:
        import psutil
        return psutil.Process().memory_info().peak_wset / (1024 * 1024)
    except (ImportError, AttributeError):
        pass

    # Fallback: current RSS
    try:
        import psutil
        return psutil.Process().memory_info().rss / (1024 * 1024)
    except ImportError:
        return 0.0


def get_current_rss_mb() -> float:
    """Current RSS in MB."""
    try:
        import psutil
        return psutil.Process().memory_info().rss / (1024 * 1024)
    except ImportError:
        return 0.0


# ── Timing context manager ──────────────────────────────────────────

@dataclass
class Timer:
    """Simple wall-clock timer."""
    elapsed: float = 0.0
    _start: float = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.elapsed = time.perf_counter() - self._start

    @property
    def ms(self) -> float:
        return self.elapsed * 1000.0


# ── Generation result ───────────────────────────────────────────────

@dataclass
class GenerationResult:
    """Result of a text generation call."""
    text: str
    token_ids: list[int]
    n_prompt_tokens: int
    n_generated_tokens: int
    elapsed_s: float
    tokens_per_second: float
    peak_rss_mb: float
    kv_cache_mb: float
