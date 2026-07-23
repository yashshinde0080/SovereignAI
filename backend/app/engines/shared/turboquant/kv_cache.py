import torch
from typing import Optional, Tuple, List
from dataclasses import dataclass

from .config import TurboQuantConfig
from .polarquant import get_rotation_matrix, apply_rotation, inverse_rotation
from .qjl import get_qjl_projection, qjl_encode, qjl_decode
from .codebook import get_lloyd_max_centroids, quantize_polar


@dataclass
class QuantizedKVCache:
    """Compressed KV cache entry for one layer."""

    # PolarQuant indices: [num_heads, seq_len, head_dim] int32
    k_indices: torch.Tensor
    v_indices: torch.Tensor
    # QJL residual codes: [num_heads, seq_len, qjl_dim] int8
    k_qjl: Optional[torch.Tensor] = None
    v_qjl: Optional[torch.Tensor] = None
    # Metadata
    seq_len: int = 0
    head_dim: int = 0


class TurboQuantKVCacheManager:
    """Drop-in for KVCacheManager with TurboQuant compression.

    Compresses K/V to ~3.5 bits/coord + 1 bit QJL = ~4.5 bits total
    vs FP16 16 bits = ~3.5× compression, near-lossless quality.
    """

    def __init__(
        self,
        config: TurboQuantConfig,
        num_layers: int,
        num_heads: int,
        head_dim: int,
        device: str = "cpu",
    ):
        self.config = config
        self.num_layers = num_layers
        self.num_heads = num_heads
        self.head_dim = head_dim
        self.device = torch.device(device)

        # Per-layer cache storage
        self.k_cache: List[Optional[QuantizedKVCache]] = [None] * num_layers
        self.v_cache: List[Optional[QuantizedKVCache]] = [None] * num_layers

        # Shared rotation matrices (cached globally)
        self.R_k = get_rotation_matrix(head_dim, device)
        self.R_v = get_rotation_matrix(head_dim, device, seed=43)  # Different seed for V

        # QJL projection
        qjl_dim = config.qjl_dim or head_dim
        self.P_k = get_qjl_projection(head_dim, qjl_dim, device)
        self.P_v = get_qjl_projection(head_dim, qjl_dim, device, seed=456)

        # Codebook
        self.centroids = get_lloyd_max_centroids(head_dim, config.bits_per_coord, device)

        # Runtime
        self.seq_length = 0

    def _quantize_kv(
        self, k: torch.Tensor, v: torch.Tensor
    ) -> Tuple[QuantizedKVCache, QuantizedKVCache]:
        """Quantize K and V tensors for one layer."""
        batch, nh, seq, hd = k.shape
        # ponytail: batch > 1 not handled — add if multi-batch inference needed
        if batch != 1:
            raise ValueError(f"Batch > 1 not supported, got batch={batch}")

        # Flatten for vector ops: [num_heads * seq_len, head_dim]
        k_flat = k.squeeze(0).reshape(-1, hd)
        v_flat = v.squeeze(0).reshape(-1, hd)

        # Stage 1: PolarQuant — rotate + quantize
        k_rot = apply_rotation(k_flat, self.R_k)
        v_rot = apply_rotation(v_flat, self.R_v)
        k_indices, k_quant = quantize_polar(k_rot, self.centroids)
        v_indices, v_quant = quantize_polar(v_rot, self.centroids)

        # Stage 2: QJL residual correction
        if self.config.enable_qjl:
            k_qjl = qjl_encode(k_rot - k_quant, self.P_k)
            v_qjl = qjl_encode(v_rot - v_quant, self.P_v)
        else:
            k_qjl = v_qjl = None

        # Reshape back
        k_indices = k_indices.reshape(nh, seq, hd)
        v_indices = v_indices.reshape(nh, seq, hd)
        if k_qjl is not None:
            k_qjl = k_qjl.reshape(nh, seq, -1)
            v_qjl = v_qjl.reshape(nh, seq, -1)

        k_cache = QuantizedKVCache(
            k_indices=k_indices, v_indices=k_indices.new_zeros(0),
            k_qjl=k_qjl, seq_len=seq, head_dim=hd
        )
        v_cache = QuantizedKVCache(
            k_indices=v_indices, v_indices=v_indices.new_zeros(0),
            k_qjl=v_qjl, seq_len=seq, head_dim=hd
        )
        return k_cache, v_cache

    def _dequantize_kv(
        self, k_cache: QuantizedKVCache, v_cache: QuantizedKVCache
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Dequantize K and V for attention computation."""
        nh, seq, hd = k_cache.k_indices.shape

        # Stage 1: centroids lookup
        k_quant = self.centroids[k_cache.k_indices.long()].reshape(nh, seq, hd)
        v_quant = self.centroids[v_cache.k_indices.long()].reshape(nh, seq, hd)

        # Stage 2: add QJL residual
        if self.config.enable_qjl and k_cache.k_qjl is not None:
            k_residual = qjl_decode(
                k_cache.k_qjl.reshape(-1, k_cache.k_qjl.shape[-1]), self.P_k
            ).reshape(nh, seq, hd)
            v_residual = qjl_decode(
                v_cache.k_qjl.reshape(-1, v_cache.k_qjl.shape[-1]), self.P_v
            ).reshape(nh, seq, hd)
            k_rot = k_quant + k_residual
            v_rot = v_quant + v_residual
        else:
            k_rot, v_rot = k_quant, v_quant

        # Inverse rotation
        k_recon = inverse_rotation(k_rot.reshape(-1, hd), self.R_k).reshape(nh, seq, hd)
        v_recon = inverse_rotation(v_rot.reshape(-1, hd), self.R_v).reshape(nh, seq, hd)

        return k_recon.unsqueeze(0), v_recon.unsqueeze(0)

    def update(self, layer_idx: int, k: torch.Tensor, v: torch.Tensor):
        """Quantize and store new K/V, appending if cache exists."""
        if self.k_cache[layer_idx] is None:
            self.k_cache[layer_idx], self.v_cache[layer_idx] = self._quantize_kv(k, v)
        else:
            # Dequantize, concat, re-quantize
            k_old, v_old = self._dequantize_kv(
                self.k_cache[layer_idx], self.v_cache[layer_idx]
            )
            k_new = torch.cat([k_old, k], dim=2)
            v_new = torch.cat([v_old, v], dim=2)
            self.k_cache[layer_idx], self.v_cache[layer_idx] = self._quantize_kv(
                k_new, v_new
            )

        self.seq_length = self.k_cache[layer_idx].seq_len

    def get(
        self, layer_idx: int, device: Optional[torch.device] = None
    ) -> Tuple[Optional[torch.Tensor], Optional[torch.Tensor]]:
        """Dequantize and return K/V for attention."""
        if self.k_cache[layer_idx] is None:
            return None, None

        k, v = self._dequantize_kv(self.k_cache[layer_idx], self.v_cache[layer_idx])

        if device is not None and k.device != device:
            k = k.to(device, non_blocking=True)
            v = v.to(device, non_blocking=True)

        return k, v

    def clear(self):
        """Reset all cache entries."""
        self.k_cache = [None] * self.num_layers
        self.v_cache = [None] * self.num_layers
        self.seq_length = 0

    def get_seq_length(self, layer_idx: int = 0) -> int:
        if self.k_cache[layer_idx] is not None:
            return self.k_cache[layer_idx].seq_len
        return 0

    def get_size_mb(self) -> float:
        """Estimate compressed cache size in MB."""
        total_bytes = 0
        for kc, vc in zip(self.k_cache, self.v_cache):
            if kc is not None:
                total_bytes += kc.k_indices.numel() * kc.k_indices.element_size()
                total_bytes += vc.k_indices.numel() * vc.k_indices.element_size()
                if kc.k_qjl is not None:
                    total_bytes += kc.k_qjl.numel() * kc.k_qjl.element_size()
                    total_bytes += vc.k_qjl.numel() * vc.k_qjl.element_size()
        return total_bytes / (1024**2)
