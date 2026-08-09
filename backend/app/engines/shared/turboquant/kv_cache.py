import math
import torch
from typing import Optional, Tuple, List
from dataclasses import dataclass

from .config import TurboQuantConfig
from .codebook import get_lloyd_max_centroids, quantize_polar
from .polarquant import get_rotation_matrix, apply_rotation, inverse_rotation
from .qjl import get_qjl_projection, qjl_encode, qjl_decode, pack_qjl_bits, unpack_qjl_bits


def _per_word_for(levels: int) -> int:
    """How many base-``levels`` digits fit into one uint32 word.

    At 3.5 bits/coord there are 11 levels, and 11**9 = 2.36e9 < 2**32, so 9
    codes pack per word (9 * log2(11) = 31.13 bits <= 32) — the paper's
    packing. Generalizes to any level count (e.g. 4-bit => 8/word, 2-bit =>
    32/word). Returns 1 when no packing is possible (levels < 2).
    """
    if levels < 2:
        return 1
    per_word = int(32 // math.log2(levels))
    while per_word > 1 and levels**per_word > 2**32:
        per_word -= 1
    return max(1, per_word)


def pack_indices(
    indices: torch.Tensor, levels: int, per_word: Optional[int] = None
) -> torch.Tensor:
    """Pack integer centroid indices into uint32 words, ``per_word`` per word.

    Little-endian base-``levels`` digits: word = d0 + d1*L + d2*L**2 + ...
    Returns uint32 ``[ceil(n / per_word)]`` where n = indices.numel(). The
    tail is zero-padded; callers recover the original count from their own
    metadata (seq_len/head_dim/num_heads). Falls back to returning the input
    unchanged when ``per_word < 2``.
    """
    if per_word is None:
        per_word = _per_word_for(levels)
    if per_word < 2:
        return indices.contiguous()
    flat = indices.reshape(-1).to(torch.int64)
    n = flat.numel()
    pad = (-n) % per_word
    if pad:
        flat = torch.cat([flat, flat.new_zeros(pad)])
    x = flat.reshape(-1, per_word)
    weights = levels ** torch.arange(per_word, dtype=torch.int64, device=flat.device)
    return (x * weights).sum(dim=1).to(torch.uint32)


def unpack_indices(
    packed: torch.Tensor, levels: int, n: int, per_word: Optional[int] = None
) -> torch.Tensor:
    """Inverse of :func:`pack_indices`: recover ``n`` indices as int64."""
    if per_word is None:
        per_word = _per_word_for(levels)
    if per_word < 2:
        return packed.reshape(-1).to(torch.int64)[:n]
    # Vectorized base conversion: digit i = (word // L**i) % L, little-endian.
    # Row-major flatten matches pack_indices' word-major layout.
    x = packed.to(torch.int64)
    weights = levels ** torch.arange(per_word, dtype=torch.int64, device=x.device)
    return ((x.unsqueeze(-1) // weights) % levels).reshape(-1)[:n]


@dataclass
class QuantizedKVCache:
    """Compressed KV cache entry for one chunk of one layer."""

    # PolarQuant indices. If ``packed``: uint32 [ceil(n/per_word)] word list;
    # else unpacked [num_heads, chunk_seq_len, head_dim] (uint8/int32).
    # NOTE: the v_cache entry reuses this field to hold the V indices
    # (pre-existing naming quirk, kept to minimize churn).
    k_indices: torch.Tensor
    v_indices: Optional[torch.Tensor] = None  # unused; kept for API compat
    # QJL residual codes: [num_heads, chunk_seq_len, qjl_dim]
    k_qjl: Optional[torch.Tensor] = None
    v_qjl: Optional[torch.Tensor] = None
    # Per-vector scale factors (norm before normalization): [num_heads, chunk_seq_len, 1]
    k_scale: Optional[torch.Tensor] = None
    v_scale: Optional[torch.Tensor] = None
    # Metadata
    seq_len: int = 0
    head_dim: int = 0
    num_heads: int = 0
    levels: int = 0  # codebook size at pack time (unpack base)
    packed: bool = False


class TurboQuantKVCacheManager:
    """Drop-in for KVCacheManager with TurboQuant compression.

    Compresses K/V to ~3.3-4.1x vs FP16 (measured, hd=64-128): indices
    BIT-PACKED (9 x 3.5-bit codes per uint32 word => ~0.44 B/coord) + QJL
    codes packed to 1 bit each (32 per uint32 word) + fp16 per-vector scales.
    The paper's
    ~6x assumes the full 3.5 bits total (2.5-bit PolarQuant + 1-bit QJL)
    with no per-vector scale; reaching it here means codebooks that absorb
    magnitudes directly, not more packing. See
    reviews/autoplan-report-2026-08-09.md.

    Storage is INCREMENTAL with a raw-token hot buffer: ``update()`` appends
    raw K/V to a per-layer buffer (O(chunk) work) and flushes it to a
    quantized chunk when it reaches ``chunk_size``. History is NEVER
    re-quantized, so every token is quantized exactly once and incremental
    updates are bit-exact with a one-shot update — no error compounding, no
    O(n^2) requantize-everything (the bug this replaces). Chunk count stays
    O(n / chunk_size); ``get()`` dequantizes chunks and appends the
    (still-raw) hot buffer.
    """

    _CHUNK_SIZE = 64  # raw-token hot buffer flush size

    def __init__(
        self,
        config: TurboQuantConfig,
        num_layers: int,
        num_heads: int,
        head_dim: int,
        device: str = "cpu",
        chunk_size: int = _CHUNK_SIZE,
    ):
        self.config = config
        self.num_layers = num_layers
        # Kept for API compatibility; rotation/QJL/codebook matrices are
        # derived from the actual tensor shapes at quantize time.
        self.num_heads = num_heads
        self.head_dim = head_dim
        self.device = torch.device(device)
        self._chunk_size = max(1, int(chunk_size))

        # Per-layer quantized chunks (one QuantizedKVCache per flush).
        self.k_cache: List[Optional[List[QuantizedKVCache]]] = [None] * num_layers
        self.v_cache: List[Optional[List[QuantizedKVCache]]] = [None] * num_layers
        # Per-layer raw hot buffers (uncompressed, pending flush).
        self._k_buf: List[List[torch.Tensor]] = [[] for _ in range(num_layers)]
        self._v_buf: List[List[torch.Tensor]] = [[] for _ in range(num_layers)]
        # For compatibility with models that expect conv_states and recurrent_states
        self.conv_states: List[Optional[torch.Tensor]] = [None] * num_layers
        self.recurrent_states: List[Optional[torch.Tensor]] = [None] * num_layers

        # Runtime
        self.seq_length = 0

    def _quantize_kv(
        self, k: torch.Tensor, v: torch.Tensor
    ) -> Tuple[QuantizedKVCache, QuantizedKVCache]:
        """Quantize K and V tensors for one layer/chunk.

        Normalizes each K/V vector to unit length before rotation/quantization
        so centroids (designed for [-1, 1]) match the actual data distribution.
        Scale factors are stored and reapplied on dequantize. Indices are
        bit-packed into uint32 words unless ``config.bit_pack`` is False.

        Derives rotation/QJL/codebook matrices from the actual tensor head_dim
        (not self.head_dim) to support models where K/V head_dim differs from
        hidden_size // num_attention_heads (e.g. Qwen3.5 MLA).
        """
        batch, nh, seq, hd = k.shape
        # ponytail: batch > 1 not handled — add if multi-batch inference needed
        if batch != 1:
            raise ValueError(f"Batch > 1 not supported, got batch={batch}")

        # Flatten for vector ops: [num_heads * seq_len, head_dim]
        k_flat = k.squeeze(0).reshape(-1, hd)
        v_flat = v.squeeze(0).reshape(-1, hd)

        # Derive matrices from actual tensor head_dim (not self.head_dim)
        # All getters are @lru_cache'd — free on repeat calls.
        R_k = get_rotation_matrix(hd, self.device)
        R_v = get_rotation_matrix(hd, self.device, seed=43)
        centroids = get_lloyd_max_centroids(hd, self.config.bits_per_coord, self.device)

        # Normalize to unit vectors so centroids (designed for [-1, 1]) match data
        k_norm = k_flat.norm(dim=-1, keepdim=True).clamp(min=1e-8)
        v_norm = v_flat.norm(dim=-1, keepdim=True).clamp(min=1e-8)
        k_unit = k_flat / k_norm
        v_unit = v_flat / v_norm

        # Stage 1: PolarQuant — rotate + quantize
        k_rot = apply_rotation(k_unit, R_k)
        v_rot = apply_rotation(v_unit, R_v)
        k_indices, k_quant = quantize_polar(k_rot, centroids)
        v_indices, v_quant = quantize_polar(v_rot, centroids)

        # Stage 2: QJL residual correction
        if self.config.enable_qjl:
            qjl_dim = self.config.qjl_dim or hd
            P_k = get_qjl_projection(hd, qjl_dim, self.device)
            P_v = get_qjl_projection(hd, qjl_dim, self.device, seed=456)
            k_qjl = qjl_encode(k_rot - k_quant, P_k)
            v_qjl = qjl_encode(v_rot - v_quant, P_v)
        else:
            k_qjl = v_qjl = None

        # Reshape back
        k_indices = k_indices.reshape(nh, seq, hd)
        v_indices = v_indices.reshape(nh, seq, hd)
        k_scale = k_norm.reshape(nh, seq, 1)
        v_scale = v_norm.reshape(nh, seq, 1)
        if k_qjl is not None:
            k_qjl = k_qjl.reshape(nh, seq, -1)
            v_qjl = v_qjl.reshape(nh, seq, -1)

        # Bit-pack indices (base-`levels` into uint32 words) unless disabled.
        # When packing, QJL codes go to 1 bit each (32/word) and scales to fp16.
        levels = len(centroids)
        use_pack = self.config.bit_pack and _per_word_for(levels) >= 2
        k_idx_stored = pack_indices(k_indices, levels) if use_pack else k_indices
        v_idx_stored = pack_indices(v_indices, levels) if use_pack else v_indices
        if use_pack and k_qjl is not None:
            k_qjl = pack_qjl_bits(k_qjl)
            v_qjl = pack_qjl_bits(v_qjl)
        if use_pack:
            k_scale = k_scale.to(torch.float16)
            v_scale = v_scale.to(torch.float16)

        k_cache = QuantizedKVCache(
            k_indices=k_idx_stored, v_indices=None,
            k_qjl=k_qjl, k_scale=k_scale, seq_len=seq, head_dim=hd,
            num_heads=nh, levels=levels, packed=use_pack,
        )
        v_cache = QuantizedKVCache(
            k_indices=v_idx_stored, v_indices=None,
            k_qjl=v_qjl, k_scale=v_scale, seq_len=seq, head_dim=hd,
            num_heads=nh, levels=levels, packed=use_pack,
        )
        return k_cache, v_cache

    def _dequantize_kv(
        self, k_cache: QuantizedKVCache, v_cache: QuantizedKVCache
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Dequantize K and V for attention computation.

        Rescales by stored per-vector norms to recover original magnitude
        after PolarQuant unit-vector quantization. Unpacks bit-packed indices
        first when the chunk was stored packed.

        Derives matrices from cached head_dim (not self.head_dim) so models
        with non-standard K/V head_dim (e.g. Qwen3.5 MLA) work correctly.
        """
        nh, seq, hd = k_cache.num_heads, k_cache.seq_len, k_cache.head_dim

        # Derive matrices from cached head_dim (matches how it was quantized)
        centroids = get_lloyd_max_centroids(hd, self.config.bits_per_coord, self.device)
        R_k = get_rotation_matrix(hd, self.device)
        R_v = get_rotation_matrix(hd, self.device, seed=43)

        # Stage 1: centroids lookup (unpack packed indices first)
        if k_cache.packed:
            k_idx = unpack_indices(k_cache.k_indices, k_cache.levels, nh * seq * hd)
            v_idx = unpack_indices(v_cache.k_indices, v_cache.levels, nh * seq * hd)
        else:
            k_idx = k_cache.k_indices
            v_idx = v_cache.k_indices
        k_quant = centroids[k_idx.long()].reshape(nh, seq, hd)
        v_quant = centroids[v_idx.long()].reshape(nh, seq, hd)

        # Stage 2: add QJL residual (unpack 1-bit codes first when packed)
        if self.config.enable_qjl and k_cache.k_qjl is not None:
            qjl_dim = self.config.qjl_dim or hd
            P_k = get_qjl_projection(hd, qjl_dim, self.device)
            P_v = get_qjl_projection(hd, qjl_dim, self.device, seed=456)
            if k_cache.packed:
                k_codes = unpack_qjl_bits(k_cache.k_qjl, nh * seq * qjl_dim).reshape(nh, seq, qjl_dim)
                v_codes = unpack_qjl_bits(v_cache.k_qjl, nh * seq * qjl_dim).reshape(nh, seq, qjl_dim)
            else:
                k_codes, v_codes = k_cache.k_qjl, v_cache.k_qjl
            k_residual = qjl_decode(k_codes.reshape(-1, qjl_dim), P_k).reshape(nh, seq, hd)
            v_residual = qjl_decode(v_codes.reshape(-1, qjl_dim), P_v).reshape(nh, seq, hd)
            k_rot = k_quant + k_residual
            v_rot = v_quant + v_residual
        else:
            k_rot, v_rot = k_quant, v_quant

        # Inverse rotation (unit-vector space) + rescale to original magnitude
        k_recon = inverse_rotation(k_rot.reshape(-1, hd), R_k).reshape(nh, seq, hd) * k_cache.k_scale
        v_recon = inverse_rotation(v_rot.reshape(-1, hd), R_v).reshape(nh, seq, hd) * v_cache.k_scale

        return k_recon.unsqueeze(0), v_recon.unsqueeze(0)

    def _buf_len(self, layer_idx: int) -> int:
        return sum(t.shape[2] for t in self._k_buf[layer_idx])

    def _total_seq_len(self, layer_idx: int) -> int:
        total = self._buf_len(layer_idx)
        chunks = self.k_cache[layer_idx]
        if chunks:
            total += sum(c.seq_len for c in chunks)
        return total

    def _flush(self, layer_idx: int):
        """Quantize the raw hot buffer into one chunk and clear it.

        Each token is quantized exactly once, here. Existing chunks are
        never re-quantized, so quality is identical to a one-shot update.
        """
        k_cat = torch.cat(self._k_buf[layer_idx], dim=2)
        v_cat = torch.cat(self._v_buf[layer_idx], dim=2)
        k_cache, v_cache = self._quantize_kv(k_cat, v_cat)
        if self.k_cache[layer_idx] is None:
            self.k_cache[layer_idx] = []
            self.v_cache[layer_idx] = []
        self.k_cache[layer_idx].append(k_cache)
        self.v_cache[layer_idx].append(v_cache)
        self._k_buf[layer_idx] = []
        self._v_buf[layer_idx] = []

    def update(self, layer_idx: int, k: torch.Tensor, v: torch.Tensor):
        """Append new K/V to cache, incremental.

        Raw K/V goes to the hot buffer (O(chunk) work, no quantization of
        history). The buffer is flushed to a quantized chunk when it reaches
        ``chunk_size`` tokens.
        """
        if k.shape[0] != 1:
            raise ValueError(f"Batch > 1 not supported, got batch={k.shape[0]}")
        if k.shape[2] == 0:
            return  # Empty sequence: nothing to cache.
        self._k_buf[layer_idx].append(k)
        self._v_buf[layer_idx].append(v)
        self.seq_length = self._total_seq_len(layer_idx)
        if self._buf_len(layer_idx) >= self._chunk_size:
            self._flush(layer_idx)

    def get(
        self, layer_idx: int, device: Optional[torch.device] = None
    ) -> Tuple[Optional[torch.Tensor], Optional[torch.Tensor]]:
        """Dequantize and return K/V for attention (chunks + hot buffer)."""
        k_parts: List[torch.Tensor] = []
        v_parts: List[torch.Tensor] = []

        chunks = self.k_cache[layer_idx]
        if chunks:
            for kc, vc in zip(chunks, self.v_cache[layer_idx]):
                k, v = self._dequantize_kv(kc, vc)
                k_parts.append(k)
                v_parts.append(v)
        if self._k_buf[layer_idx]:
            # Buffer is raw (engine dtype); dequantized chunks are float32.
            k_parts.append(torch.cat(self._k_buf[layer_idx], dim=2).to(torch.float32))
            v_parts.append(torch.cat(self._v_buf[layer_idx], dim=2).to(torch.float32))

        if not k_parts:
            return None, None
        k = torch.cat(k_parts, dim=2)
        v = torch.cat(v_parts, dim=2)

        if device is not None and k.device != device:
            k = k.to(device, non_blocking=True)
            v = v.to(device, non_blocking=True)

        return k, v

    def clear(self):
        """Reset all cache entries."""
        self.k_cache = [None] * self.num_layers
        self.v_cache = [None] * self.num_layers
        self._k_buf = [[] for _ in range(self.num_layers)]
        self._v_buf = [[] for _ in range(self.num_layers)]
        self.conv_states = [None] * self.num_layers
        self.recurrent_states = [None] * self.num_layers
        self.seq_length = 0

    def get_seq_length(self, layer_idx: int = 0) -> int:
        return self._total_seq_len(layer_idx)

    def get_size_mb(self) -> float:
        """Estimate cache size in MB (quantized chunks + raw hot buffers).

        Packed indices are counted at their real uint32 word size; unpacked
        indices at their byte size. QJL and scale tensors as stored.
        """
        total_bytes = 0
        for layer_idx in range(self.num_layers):
            chunks = self.k_cache[layer_idx]
            if chunks:
                for kc, vc in zip(chunks, self.v_cache[layer_idx]):
                    total_bytes += kc.k_indices.numel() * kc.k_indices.element_size()
                    total_bytes += vc.k_indices.numel() * vc.k_indices.element_size()
                    if kc.k_qjl is not None:
                        total_bytes += kc.k_qjl.numel() * kc.k_qjl.element_size()
                        total_bytes += vc.k_qjl.numel() * vc.k_qjl.element_size()
                    if kc.k_scale is not None:
                        total_bytes += kc.k_scale.numel() * kc.k_scale.element_size()
                        total_bytes += vc.k_scale.numel() * vc.k_scale.element_size()
            for t in self._k_buf[layer_idx]:
                total_bytes += t.numel() * t.element_size()
            for t in self._v_buf[layer_idx]:
                total_bytes += t.numel() * t.element_size()
        return total_bytes / (1024**2)

    @classmethod
    def create(cls, mode: str = "standard", **kwargs):
        """Factory: create a KVCacheManager or TurboQuant variant."""
        if mode == "turboquant":
            from app.engines.shared.turboquant import TurboQuantKVCacheManager, TurboQuantConfig
            config = kwargs.pop('turboquant_config', {})
            if isinstance(config, dict):
                cfg = TurboQuantConfig(**config)
            else:
                cfg = config
            return TurboQuantKVCacheManager(cfg, **kwargs)
        return cls()
