"""Transformer model: config, weights, forward pass.

Pure numpy. No PyTorch. Loads weights on-demand via CheckpointLoader.

Architecture: Llama-style transformer with GQA (grouped-query attention),
RMSNorm, RoPE, and SiLU-gated FFN.
"""

from __future__ import annotations

import numpy as np

from .config import ModelConfig
from .loader import CheckpointLoader
from .kv_cache import KVCache
from .utils import rmsnorm, rope, softmax, silu, matmul


def _attention(
    q: np.ndarray,
    k: np.ndarray,
    v: np.ndarray,
    kv_cache: KVCache | None,
    layer_idx: int,
) -> np.ndarray:
    """Compute attention with KV-cache.

    Args:
        q: [seq_len, n_heads, head_dim]
        k: [seq_len, n_kv_heads, head_dim]
        v: [seq_len, n_kv_heads, head_dim]
        kv_cache: KV-cache (None during tests without cache)
        layer_idx: layer index for cache lookup

    Returns:
        [seq_len, n_heads, head_dim]
    """
    n_heads = q.shape[1]
    n_kv_heads = k.shape[1]
    head_dim = q.shape[2]
    seq_len = q.shape[0]

    # Append new k/v to cache
    if kv_cache is not None:
        kv_cache.append(layer_idx, k, v)
        # Read back full k/v: cached[:cur_len+seq_len]
        # (advance is called once in forward(), not here)
        kv_end = kv_cache.cur_len + seq_len
        k_full = kv_cache.k[layer_idx, :kv_end]
        v_full = kv_cache.v[layer_idx, :kv_end]
    else:
        k_full = k
        v_full = v

    kv_len = k_full.shape[0]

    # GQA: repeat k/v heads if n_kv_heads < n_heads
    if n_kv_heads < n_heads:
        repeat_factor = n_heads // n_kv_heads
        k_full = np.repeat(k_full, repeat_factor, axis=1)  # [kv_len, n_heads, head_dim]
        v_full = np.repeat(v_full, repeat_factor, axis=1)

    # Attention scores: [seq_len, n_heads, kv_len]
    scale = 1.0 / np.sqrt(head_dim)
    scores = np.einsum("qhd,khd->hqk", q, k_full) * scale

    # Causal mask: prevent attending to future positions
    # For prefill: query positions [0..seq_len-1] can attend to [0..kv_len-1]
    # but each position i can only attend to positions <= i + (kv_len - seq_len)
    if kv_len > seq_len:
        # Decode: single query attending to all cached keys
        # No mask needed (all positions are in the past)
        pass
    else:
        # Prefill: causal mask
        mask = np.full((seq_len, kv_len), -np.inf, dtype=np.float32)
        for i in range(seq_len):
            mask[i, : i + 1] = 0.0
        scores = scores + mask[np.newaxis, :, :]  # broadcast over n_heads

    attn_weights = softmax(scores, axis=-1)  # [seq_len, n_heads, kv_len]

    # Weighted sum of values
    attn_out = np.einsum("hqk,khd->qhd", attn_weights, v_full)  # [seq_len, n_heads, head_dim]

    return attn_out  # [seq_len, n_heads, head_dim]


def _ffn(
    x: np.ndarray,
    gate_weight: np.ndarray,
    up_weight: np.ndarray,
    down_weight: np.ndarray,
) -> np.ndarray:
    """SiLU-gated feed-forward network.

    out = silu(x @ Wgate) * (x @ Wup) @ Wdown
    """
    gate = silu(matmul(x, gate_weight.T))  # [seq, hidden_dim]
    up = matmul(x, up_weight.T)            # [seq, hidden_dim]
    return matmul(gate * up, down_weight.T) # [seq, dim]


class TransformerModel:
    """Transformer model for inference.

    Weights are loaded on-demand from the CheckpointLoader.
    Embedding + lm_head are always resident. Layer weights are loaded
    per forward pass (budget-aware eviction in Phase 2).
    """

    def __init__(self, config: ModelConfig, loader: CheckpointLoader):
        self.config = config
        self.loader = loader
        self._embed: np.ndarray | None = None
        self._lm_head: np.ndarray | None = None
        self._norm: np.ndarray | None = None

    @property
    def embed(self) -> np.ndarray:
        if self._embed is None:
            self._embed = self.loader.load_tensor("token_embd.weight").astype(np.float32)
        return self._embed

    @property
    def lm_head(self) -> np.ndarray:
        if self._lm_head is None:
            if self.loader.has_tensor("output.weight"):
                self._lm_head = self.loader.load_tensor("output.weight").astype(np.float32)
            else:
                self._lm_head = self.embed  # tied weights
        return self._lm_head

    @property
    def norm(self) -> np.ndarray:
        if self._norm is None:
            self._norm = self.loader.load_tensor("output_norm.weight").astype(np.float32)
        return self._norm

    def forward(
        self,
        token_ids: np.ndarray,
        kv_cache: KVCache | None = None,
    ) -> np.ndarray:
        """Run forward pass. Returns logits [seq_len, vocab_size].

        Supports both prefill (seq_len > 1) and decode (seq_len == 1) modes.
        KV-cache is populated during prefill and reused during decode.
        """
        config = self.config

        # Embed tokens: [seq_len] → [seq_len, dim]
        x = self.embed[token_ids].astype(np.float32)

        # Determine starting position for RoPE
        pos = 0
        if kv_cache is not None and kv_cache.cur_len > 0:
            pos = kv_cache.cur_len

        # Transformer layers
        for i in range(config.n_layers):
            x = self._forward_layer(x, i, pos, kv_cache)

        # Advance KV-cache cursor once (not per layer)
        if kv_cache is not None:
            kv_cache.advance(len(token_ids))

        # Final norm + lm_head
        x = rmsnorm(x, self.norm)
        logits = matmul(x, self.lm_head.T)  # [seq_len, vocab_size]
        return logits

    def _forward_layer(
        self,
        x: np.ndarray,
        layer_idx: int,
        pos: int,
        kv_cache: KVCache | None,
    ) -> np.ndarray:
        """Forward pass through one transformer layer."""
        config = self.config
        seq_len = x.shape[0]

        # ── Attention block ─────────────────────────────────────────
        residual = x

        # Attention norm
        attn_norm_w = self.loader.load_tensor(f"blk.{layer_idx}.attn_norm.weight").astype(np.float32)
        x = rmsnorm(x, attn_norm_w)

        # Project to Q, K, V
        q_w = self.loader.load_tensor(f"blk.{layer_idx}.attn_q.weight").astype(np.float32)
        k_w = self.loader.load_tensor(f"blk.{layer_idx}.attn_k.weight").astype(np.float32)
        v_w = self.loader.load_tensor(f"blk.{layer_idx}.attn_v.weight").astype(np.float32)

        q = matmul(x, q_w.T)  # [seq_len, n_heads * head_dim]
        k = matmul(x, k_w.T)  # [seq_len, n_kv_heads * head_dim]
        v = matmul(x, v_w.T)  # [seq_len, n_kv_heads * head_dim]

        # Reshape to multi-head: [seq_len, n_heads, head_dim]
        q = q.reshape(seq_len, config.n_heads, config.head_dim)
        k = k.reshape(seq_len, config.n_kv_heads, config.head_dim)
        v = v.reshape(seq_len, config.n_kv_heads, config.head_dim)

        # Apply RoPE
        q = rope(q, pos, config.rope_theta)
        k = rope(k, pos, config.rope_theta)

        # Attention with KV-cache
        attn_out = _attention(q, k, v, kv_cache, layer_idx)

        # Flatten heads: [seq_len, n_heads, head_dim] → [seq_len, n_heads * head_dim]
        attn_out = attn_out.reshape(seq_len, -1)

        # Output projection
        o_w = self.loader.load_tensor(f"blk.{layer_idx}.attn_output.weight").astype(np.float32)
        attn_out = matmul(attn_out, o_w.T)  # [seq_len, dim]

        x = residual + attn_out

        # ── FFN block ───────────────────────────────────────────────
        residual = x

        # FFN norm (some models use separate norm, others share)
        ffn_norm_name = f"blk.{layer_idx}.ffn_norm.weight"
        if self.loader.has_tensor(ffn_norm_name):
            ffn_norm_w = self.loader.load_tensor(ffn_norm_name).astype(np.float32)
            x = rmsnorm(x, ffn_norm_w)
        else:
            # Models without separate ffn_norm (re-use attn_norm)
            x = rmsnorm(x, attn_norm_w)

        # FFN projections
        gate_w = self.loader.load_tensor(f"blk.{layer_idx}.ffn_gate.weight").astype(np.float32)
        up_w = self.loader.load_tensor(f"blk.{layer_idx}.ffn_up.weight").astype(np.float32)
        down_w = self.loader.load_tensor(f"blk.{layer_idx}.ffn_down.weight").astype(np.float32)

        ffn_out = _ffn(x, gate_w, up_w, down_w)

        x = residual + ffn_out
        return x

    def n_params(self) -> int:
        """Estimate total parameter count from config."""
        c = self.config
        embed = c.vocab_size * c.dim
        per_layer = (
            4 * c.dim * c.dim  # Q, K, V, O projections
            + 2 * c.dim * c.hidden_dim  # gate, up projections
            + c.hidden_dim * c.dim  # down projection
            + 4 * c.dim  # norms (attn_norm + ffn_norm, but some share)
        )
        total = embed + c.n_layers * per_layer + c.dim + c.vocab_size * c.dim
        return total

    def size_gb(self) -> float:
        """Estimate model size in GB (FP32)."""
        return self.n_params() * 4 / (1024 ** 3)
