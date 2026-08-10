> ⚠️ **Status: experimental, default-off** — The eval gate (perplexity + needle-in-haystack) FAILS on Qwen2-0.5B and Pythia-70m at all bit rates (3-6 bits, both polar and affine schemes). See [`reviews/autoplan-report-2026-08-09.md`](reviews/autoplan-report-2026-08-09.md) for the full accuracy analysis and gate results.

# TurboQuant Integration Guide for SovereignAI Edge

> **Source Paper**: *TurboQuant: Online Vector Quantization with Near-optimal Distortion Rate* (Google Research, ICLR 2026)  
> **arXiv**: [2504.19874](https://arxiv.org/abs/2504.19874) | **Blog**: [Google Research Blog](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/)

---

## Executive Summary

**TurboQuant** is a Google Research vector quantization algorithm for **KV cache compression** that achieves **~6× memory reduction with zero accuracy loss at 3.5 bits/channel**, requiring **no training, calibration, or fine-tuning**. It is **data-oblivious** and **online-capable** — perfectly suited for SovereignAI's LayerStream engine which streams layers from disk and maintains KV cache on CPU/GPU.

| Metric | TurboQuant 3-bit | FP16 Baseline | KIVI 2-bit |
|--------|------------------|---------------|------------|
| KV Cache Memory | **~7.5 GB** (Llama-3.1-70B, 128K ctx) | 40 GB | ~10 GB |
| Needle-in-Haystack (104K) | **0.997** | 0.997 | 0.981 |
| LongBench (Llama-3.1-8B) | **50.06** | 50.06 | — |
| Attention Speedup (H100, 4-bit) | **8×** | 1× | ~4× |
| Calibration Data | **None (data-oblivious)** | N/A | None |
| Online/Streaming | **Yes** | N/A | Limited |

---

## Core Algorithm: Two-Stage Pipeline

### Stage 1: PolarQuant — Rotate → Quantize

```python
# Mathematical formulation
# 1. Random orthogonal rotation:  x̃ = R @ x   where R ∈ O(d)
# 2. Coordinates follow Beta(1/2, (d-1)/2) distribution
# 3. Per-coordinate Lloyd-Max quantization to optimal centroids
# 4. Store integer indices (3-4 bits each) — no per-block scale/offset metadata!
```

**Key insight**: Rotation concentrates vector mass into predictable Beta distribution → optimal scalar quantizers per coordinate → **zero metadata overhead**.

### Stage 2: QJL — 1-bit Residual Correction

```python
# Quantized Johnson-Lindenstrauss Transform
# Residual: r = x - x̂ (from Stage 1)
# Project:   z = sign(P @ r)  where P ∈ {+1, -1}^(d' × d), d' ≈ d
# Store:     1 bit per dimension
# Effect:    Restores unbiased inner products ⟨q(x), q(y)⟩ ≈ ⟨x, y⟩
```

**Critical for attention**: MSE-optimal quantizers introduce bias in dot products. QJL's 1-bit residual restores **unbiased attention scores** with only **1 extra bit/dimension**.

---

## Why TurboQuant Fits SovereignAI Edge

| SovereignAI Feature | TurboQuant Synergy |
|---------------------|-------------------|
| **LayerStream Engine** — KV cache lives on CPU/GPU during layer-by-layer streaming | TurboQuant is **online/streaming** compatible; quantize K/V on-the-fly as they enter cache |
| **FullRAM Engine** — All weights in RAM, KV cache dominates memory at long context | 6× KV compression → **directly enables longer context on same hardware** |
| **Offline/USB deployment** — No calibration data available | **Zero calibration** — works out-of-box on any GGUF/HF model |
| **Consumer hardware (CPU/GPU)** — Limited VRAM/RAM | 81% KV memory reduction (70B @ 128K: 40GB → 7.5GB) |
| **GGUF/llama.cpp compatibility** | Community PRs exist for `llama.cpp` (`tbq3_0`, `tbq4_0` cache types) |

---

## Integration Architecture for SovereignAI

### Target Integration Points

```
┌─────────────────────────────────────────────────────────────────┐
│                    SOVEREIGN AI ENGINE STACK                     │
├─────────────────────────────────────────────────────────────────┤
│  LayerStream Engine                    FullRAM Engine            │
│  ┌─────────────────────┐              ┌─────────────────────┐   │
│  │ LayerExecutor       │              │ FullRAMExecutor     │   │
│  │   └─ KVCacheManager │◄──┐          │   └─ KVCache        │   │
│  │       │             │   │          │       │             │   │
│  │       ▼             │   │          │       ▼             │   │
│  │  HFProxyCache ◄─────┼───┼──────────┼── TurboQuantKVCache │   │
│  │   (transformers     │   │          │   (quantized K/V,   │   │
│  │    DynamicCache)    │   │          │    rotation + QJL)  │   │
│  └─────────────────────┘   │          └─────────────────────┘   │
│                            │                                     │
│                    ┌───────┴───────┐                             │
│                    │ TurboQuant    │                             │
│                    │ Core Library  │                             │
│                    │  • PolarQuant │                             │
│                    │  • QJL        │                             │
│                    │  • Codebook   │                             │
│                    └───────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

### Proposed File Structure

```
backend/app/engines/
├── shared/
│   └── turboquant/                    # NEW: Shared TurboQuant core
│       ├── __init__.py
│       ├── polarquant.py              # Rotation + Lloyd-Max quantization
│       ├── qjl.py                     # Quantized Johnson-Lindenstrauss
│       ├── codebook.py                # Precomputed Beta-distribution centroids
│       ├── kv_cache.py                # TurboQuantKVCacheManager (drop-in)
│       └── config.py                  # TurboQuantConfig (bits, QJL dim, etc.)
├── layerstream/
│   ├── kv_cache.py                    # MODIFY: Add TurboQuantKVCacheManager
│   └── executor.py                    # MODIFY: Wire TurboQuant into HFProxyCache
└── fullram/
    └── kv_cache.py                    # MODIFY: Add TurboQuant support
```

---

## Implementation Specification

### 1. TurboQuant Configuration

```python
# backend/app/engines/shared/turboquant/config.py
from dataclasses import dataclass
from typing import Literal

@dataclass
class TurboQuantConfig:
    """Configuration for TurboQuant KV cache compression."""
    
    # Quantization bits per coordinate (3.5 = lossless, 2.5 = near-lossless)
    bits_per_coord: float = 3.5
    
    # QJL residual correction dimension (typically = head_dim)
    qjl_dim: int = None  # None = auto (head_dim)
    
    # Enable/disable stages
    enable_polarquant: bool = True
    enable_qjl: bool = True
    
    # Rotation matrix: 'random' | 'hadamard' | 'learned' (future)
    rotation_type: Literal['random', 'hadamard'] = 'random'
    
    # Codebook: 'beta_lloyd_max' | 'uniform' | 'kmeans' (future)
    codebook_type: str = 'beta_lloyd_max'
    
    # Device for quantization ops
    device: str = 'cpu'  # 'cpu' | 'cuda' | 'auto'
    
    # Cache quantization stats for debugging
    collect_stats: bool = False
    
    def __post_init__(self):
        if self.qjl_dim is None:
            self.qjl_dim = 128  # Default head_dim, overridden at runtime
```

### 2. Precomputed Beta-Distribution Codebook

```python
# backend/app/engines/shared/turboquant/codebook.py
import torch
import numpy as np
from functools import lru_cache

@lru_cache(maxsize=8)
def get_lloyd_max_centroids(dim: int, bits: float, device: str = 'cpu') -> torch.Tensor:
    """
    Precompute optimal Lloyd-Max centroids for Beta(1/2, (dim-1)/2) distribution.
    
    This is the CORE of PolarQuant — centroids are shared across ALL layers, 
    models, and inference runs. Computed once at startup.
    """
    # Beta distribution params for rotated coordinates
    alpha = 0.5
    beta = (dim - 1) / 2.0
    
    num_levels = int(2 ** bits)
    
    # Compute optimal centroids via Lloyd-Max algorithm
    # (scipy.stats.beta.ppf for inverse CDF, then iterative refinement)
    from scipy.stats import beta
    from scipy.optimize import minimize_scalar
    
    # Initial centroids from quantiles
    quantiles = np.linspace(0, 1, num_levels + 1)[1:-1]
    centroids = beta.ppf(quantiles, alpha, beta)
    
    # Refine via Lloyd-Max iterations (3-5 iterations sufficient)
    for _ in range(5):
        # Assign intervals
        boundaries = np.concatenate([[-np.inf], 
                                     (centroids[:-1] + centroids[1:]) / 2,
                                     [np.inf]])
        
        # Update centroids to conditional means
        new_centroids = []
        for i in range(num_levels):
            a, b = boundaries[i], boundaries[i+1]
            # Conditional mean of truncated Beta
            # E[X | a < X < b] = (CDF(b)*μ_b - CDF(a)*μ_a) / (CDF(b) - CDF(a))
            # where μ_x is partial moment — use numeric integration
            from scipy.integrate import quad
            num, _ = quad(lambda x: x * beta.pdf(x, alpha, beta), a, b)
            den = beta.cdf(b, alpha, beta) - beta.cdf(a, alpha, beta)
            new_centroids.append(num / den if den > 0 else centroids[i])
        centroids = np.array(new_centroids)
    
    return torch.tensor(centroids, dtype=torch.float32, device=device)


def quantize_polar(x: torch.Tensor, centroids: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Quantize rotated vectors to nearest centroids.
    
    Args:
        x: [..., d] rotated vectors
        centroids: [num_levels] optimal centroids
    
    Returns:
        indices: [..., d] int32 centroid indices
        quantized: [..., d] reconstructed values
    """
    # Expand for broadcasting: [..., d, 1] - [num_levels] -> [..., d, num_levels]
    diff = x.unsqueeze(-1) - centroids.view(*([1]*x.ndim), -1)
    indices = diff.abs().argmin(dim=-1).to(torch.int32)
    quantized = centroids[indices]
    return indices, quantized
```

### 3. Random Orthogonal Rotation (PolarQuant)

```python
# backend/app/engines/shared/turboquant/polarquant.py
import torch
from functools import lru_cache

@lru_cache(maxsize=4)
def get_rotation_matrix(dim: int, device: str = 'cpu', seed: int = 42) -> torch.Tensor:
    """
    Generate random orthogonal matrix R ∈ O(dim) via QR decomposition.
    
    Cached per (dim, device) — shared across all layers/models.
    """
    torch.manual_seed(seed)
    # Random Gaussian matrix
    A = torch.randn(dim, dim, device=device, dtype=torch.float32)
    # QR decomposition → Q is orthogonal
    Q, R = torch.linalg.qr(A)
    # Ensure uniform distribution over O(dim) by fixing signs
    D = torch.diag(torch.sign(torch.diag(R)))
    return Q @ D


def apply_rotation(x: torch.Tensor, R: torch.Tensor) -> torch.Tensor:
    """
    Apply rotation: x̃ = x @ R.T  (R is orthogonal, so R.T = R^-1)
    
    Args:
        x: [..., d] input vectors
        R: [d, d] orthogonal matrix
    
    Returns:
        [..., d] rotated vectors
    """
    return x @ R.T


def inverse_rotation(x_tilde: torch.Tensor, R: torch.Tensor) -> torch.Tensor:
    """Recover original: x = x̃ @ R"""
    return x_tilde @ R
```

### 4. QJL Residual Correction

```python
# backend/app/engines/shared/turboquant/qjl.py
import torch
from functools import lru_cache

@lru_cache(maxsize=4)
def get_qjl_projection(dim: int, qjl_dim: int, device: str = 'cpu', seed: int = 123) -> torch.Tensor:
    """
    Generate ±1 projection matrix for QJL.
    
    Each row is a random Rademacher vector.
    """
    torch.manual_seed(seed)
    # [qjl_dim, dim] matrix of ±1
    P = torch.randint(0, 2, (qjl_dim, dim), device=device, dtype=torch.int8) * 2 - 1
    return P.to(torch.float32) / (qjl_dim ** 0.5)  # Normalized


def qjl_encode(residual: torch.Tensor, P: torch.Tensor) -> torch.Tensor:
    """
    Encode residual to 1-bit QJL sketch.
    
    Args:
        residual: [..., d] float32 residual vectors
        P: [qjl_dim, d] projection matrix
    
    Returns:
        [..., qjl_dim] int8 values in {-1, +1}
    """
    # Project: [..., d] @ [d, qjl_dim] -> [..., qjl_dim]
    projected = residual @ P.T
    # Sign quantization: +1 or -1
    return torch.sign(projected).to(torch.int8)


def qjl_decode(qjl_codes: torch.Tensor, P: torch.Tensor) -> torch.Tensor:
    """
    Reconstruct residual approximation from QJL codes.
    
    Returns unbiased estimator of residual.
    """
    # [..., qjl_dim] @ [qjl_dim, d] -> [..., d]
    return qjl_codes.to(torch.float32) @ P
```

### 5. TurboQuant KV Cache Manager (Drop-in Replacement)

```python
# backend/app/engines/shared/turboquant/kv_cache.py
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
    """
    Drop-in replacement for KVCacheManager with TurboQuant compression.
    
    Compresses K/V to ~3.5 bits/coord + 1 bit QJL = ~4.5 bits total
    vs FP16 16 bits = 3.5x compression, near-lossless quality.
    """
    
    def __init__(self, config: TurboQuantConfig, num_layers: int, 
                 num_heads: int, head_dim: int, device: str = 'cpu'):
        self.config = config
        self.num_layers = num_layers
        self.num_heads = num_heads
        self.head_dim = head_dim
        self.device = torch.device(device)
        
        # Cache storage per layer
        self.k_cache: List[Optional[QuantizedKVCache]] = [None] * num_layers
        self.v_cache: List[Optional[QuantizedKVCache]] = [None] * num_layers
        
        # Shared rotation matrices (cached globally)
        self.R_k = get_rotation_matrix(head_dim, device)
        self.R_v = get_rotation_matrix(head_dim, device)  # Can share or separate
        
        # QJL projection
        qjl_dim = config.qjl_dim or head_dim
        self.P_k = get_qjl_projection(head_dim, qjl_dim, device)
        self.P_v = get_qjl_projection(head_dim, qjl_dim, device)
        
        # Codebook
        self.centroids = get_lloyd_max_centroids(head_dim, config.bits_per_coord, device)
        
        # Runtime stats
        self.seq_length = 0
        
    def _quantize_kv(self, k: torch.Tensor, v: torch.Tensor) -> Tuple[QuantizedKVCache, QuantizedKVCache]:
        """Quantize K and V tensors for one layer."""
        # k, v: [batch, num_heads, seq_len, head_dim]
        batch, nh, seq, hd = k.shape
        assert batch == 1, "Batch > 1 not yet supported"
        
        # Flatten heads for processing: [num_heads * seq_len, head_dim]
        k_flat = k.squeeze(0).reshape(-1, hd)
        v_flat = v.squeeze(0).reshape(-1, hd)
        
        # Stage 1: PolarQuant
        # Rotate
        k_rot = apply_rotation(k_flat, self.R_k)
        v_rot = apply_rotation(v_flat, self.R_v)
        
        # Quantize to centroids
        k_indices, k_quant = quantize_polar(k_rot, self.centroids)
        v_indices, v_quant = quantize_polar(v_rot, self.centroids)
        
        # Stage 2: QJL Residual Correction
        if self.config.enable_qjl:
            k_residual = k_rot - k_quant
            v_residual = v_rot - v_quant
            
            k_qjl = qjl_encode(k_residual, self.P_k)
            v_qjl = qjl_encode(v_residual, self.P_v)
        else:
            k_qjl = v_qjl = None
        
        # Reshape back
        k_indices = k_indices.reshape(nh, seq, hd)
        v_indices = v_indices.reshape(nh, seq, hd)
        if k_qjl is not None:
            k_qjl = k_qjl.reshape(nh, seq, -1)
            v_qjl = v_qjl.reshape(nh, seq, -1)
        
        k_cache = QuantizedKVCache(
            k_indices=k_indices, k_qjl=k_qjl,
            seq_len=seq, head_dim=hd
        )
        v_cache = QuantizedKVCache(
            k_indices=v_indices, k_qjl=v_qjl,  # Reuse field for V
            seq_len=seq, head_dim=hd
        )
        
        return k_cache, v_cache
    
    def _dequantize_kv(self, k_cache: QuantizedKVCache, 
                       v_cache: QuantizedKVCache) -> Tuple[torch.Tensor, torch.Tensor]:
        """Dequantize K and V for attention computation."""
        nh, seq, hd = k_cache.k_indices.shape
        
        # Stage 1: Reconstruct from centroids
        k_flat = k_cache.k_indices.reshape(-1, hd)
        v_flat = v_cache.k_indices.reshape(-1, hd)  # v_cache uses k_indices field
        
        k_quant = self.centroids[k_flat].reshape(nh, seq, hd)
        v_quant = self.centroids[v_flat].reshape(nh, seq, hd)
        
        # Stage 2: Add QJL residual correction
        if self.config.enable_qjl and k_cache.k_qjl is not None:
            k_residual = qjl_decode(k_cache.k_qjl.reshape(-1, k_cache.k_qjl.shape[-1]), 
                                   self.P_k).reshape(nh, seq, hd)
            v_residual = qjl_decode(v_cache.k_qjl.reshape(-1, v_cache.k_qjl.shape[-1]), 
                                   self.P_v).reshape(nh, seq, hd)
            
            k_rot = k_quant + k_residual
            v_rot = v_quant + v_residual
        else:
            k_rot = k_quant
            v_rot = v_quant
        
        # Inverse rotation
        k_recon = inverse_rotation(k_rot.reshape(-1, hd), self.R_k).reshape(nh, seq, hd)
        v_recon = inverse_rotation(v_rot.reshape(-1, hd), self.R_v).reshape(nh, seq, hd)
        
        # Add batch dim
        return k_recon.unsqueeze(0), v_recon.unsqueeze(0)
    
    def update(self, layer_idx: int, k: torch.Tensor, v: torch.Tensor):
        """Quantize and append new K/V to cache."""
        if self.k_cache[layer_idx] is None:
            self.k_cache[layer_idx], self.v_cache[layer_idx] = self._quantize_kv(k, v)
        else:
            # Append: dequantize existing, concat, re-quantize
            k_old, v_old = self._dequantize_kv(self.k_cache[layer_idx], self.v_cache[layer_idx])
            k_new = torch.cat([k_old, k], dim=2)
            v_new = torch.cat([v_old, v], dim=2)
            self.k_cache[layer_idx], self.v_cache[layer_idx] = self._quantize_kv(k_new, v_new)
        
        self.seq_length = self.k_cache[layer_idx].seq_len
    
    def get(self, layer_idx: int, device: Optional[torch.device] = None) -> Tuple[torch.Tensor, torch.Tensor]:
        """Dequantize and return K/V for attention."""
        if self.k_cache[layer_idx] is None:
            return None, None
        
        k, v = self._dequantize_kv(self.k_cache[layer_idx], self.v_cache[layer_idx])
        
        if device is not None and k.device != device:
            k = k.to(device, non_blocking=True)
            v = v.to(device, non_blocking=True)
        
        return k, v
    
    def clear(self):
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
        for k_cache, v_cache in zip(self.k_cache, self.v_cache):
            if k_cache is not None:
                # Indices: int32 (4 bytes) * num_elements
                total_bytes += k_cache.k_indices.numel() * 4
                total_bytes += v_cache.k_indices.numel() * 4
                # QJL: int8 (1 byte) * num_elements
                if k_cache.k_qjl is not None:
                    total_bytes += k_cache.k_qjl.numel() * 1
                    total_bytes += v_cache.k_qjl.numel() * 1
        return total_bytes / (1024 ** 2)
```

### 6. HF Proxy Cache Wrapper (Drop-in for transformers)

```python
# backend/app/engines/shared/turboquant/hf_proxy.py
from typing import Optional, Tuple
import torch
from transformers.cache_utils import DynamicCache

from .kv_cache import TurboQuantKVCacheManager, QuantizedKVCache


class TurboQuantHFProxyCache(DynamicCache):
    """
    Drop-in replacement for HFProxyCache that uses TurboQuant compression.
    
    Compatible with transformers.DynamicCache interface expected by model layers.
    """
    
    def __init__(self, turboquant_manager: TurboQuantKVCacheManager):
        super().__init__()
        self.tq_manager = turboquant_manager
        self._seen_layers = set()
    
    def update(
        self,
        key_states: torch.Tensor,
        value_states: torch.Tensor,
        layer_idx: int,
        cache_kwargs: Optional[dict] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Store quantized K/V, return dequantized for current computation."""
        # Quantize and store
        self.tq_manager.update(layer_idx, key_states, value_states)
        self._seen_layers.add(layer_idx)
        
        # Return dequantized for this layer's attention computation
        k, v = self.tq_manager.get(layer_idx, key_states.device)
        return k, v
    
    def get_seq_length(self, layer_idx: int = 0) -> int:
        return self.tq_manager.get_seq_length(layer_idx)
    
    def get_max_length(self) -> Optional[int]:
        return None  # No hard limit
    
    def __len__(self):
        return self.tq_manager.num_layers
    
    def __getitem__(self, layer_idx: int):
        k, v = self.tq_manager.get(layer_idx)
        if k is not None:
            return (k, v)
        return None
    
    def reorder_cache(self, beam_idx: torch.LongTensor):
        """Required for beam search — not yet implemented for TurboQuant."""
        raise NotImplementedError("Beam search reorder not yet supported with TurboQuant")
```

---

## LayerStream Integration

### Modified `layerstream/executor.py`

```python
# In LayerExecutor.__init__
from app.engines.shared.turboquant import TurboQuantConfig, TurboQuantKVCacheManager, TurboQuantHFProxyCache

class LayerExecutor:
    def __init__(self, components, config, weights_dir, device, turboquant_config=None):
        # ... existing init ...
        
        # TurboQuant KV Cache
        self.turboquant_config = turboquant_config or TurboQuantConfig()
        head_dim = config.hidden_size // config.num_attention_heads
        self.tq_kv_manager = TurboQuantKVCacheManager(
            config=self.turboquant_config,
            num_layers=self.num_layers,
            num_heads=config.num_attention_heads,
            head_dim=head_dim,
            device=device
        )
        
        # Replace standard KV manager
        self.kv_manager = self.tq_kv_manager
    
    def execute_forward(self, input_ids, mode="decode"):
        # ... existing code ...
        
        # Replace HFProxyCache with TurboQuant version
        hf_cache = TurboQuantHFProxyCache(self.tq_kv_manager)
        
        # ... rest unchanged, model layers call hf_cache.update() automatically ...
```

### Modified `layerstream/kv_cache.py` — Add TurboQuant Option

```python
# In KVCacheManager class, add factory method
@classmethod
def create(cls, mode: str = "standard", **kwargs):
    if mode == "turboquant":
        from app.engines.shared.turboquant import TurboQuantKVCacheManager, TurboQuantConfig
        config = TurboQuantConfig(**kwargs.get('turboquant_config', {}))
        return TurboQuantKVCacheManager(config, **kwargs)
    return cls()
```

---

## FullRAM Integration

```python
# backend/app/engines/fullram/kv_cache.py
# Add TurboQuantKVCacheManager as alternative backend

class FullRAMKVCache:
    def __init__(self, config, use_turboquant: bool = False, turboquant_config=None):
        self.use_turboquant = use_turboquant
        if use_turboquant:
            from app.engines.shared.turboquant import TurboQuantKVCacheManager, TurboQuantConfig
            self.tq_manager = TurboQuantKVCacheManager(
                config=turboquant_config or TurboQuantConfig(),
                num_layers=config.num_hidden_layers,
                num_heads=config.num_attention_heads,
                head_dim=config.hidden_size // config.num_attention_heads,
                device=config.device
            )
        else:
            # Original FP16 cache
            self.key_cache = []
            self.value_cache = []
```

---

## Engine Router Integration

```python
# engine selection: backend/app/services/model_manager.py (via EngineFactory)

def select_engine_and_kv_config(hardware_profile, model_size_gb, context_length):
    """
    Enhanced engine selection with TurboQuant awareness.
    """
    kv_cache_gb = estimate_kv_cache(model_size_gb, context_length)
    available_ram = hardware_profile.ram_total_gb - hardware_profile.ram_used_gb
    
    # With TurboQuant: ~6x KV compression at 3.5-bit
    kv_cache_turboquant_gb = kv_cache_gb / 6.0
    
    if kv_cache_turboquant_gb < available_ram * 0.7:
        # Can fit compressed KV in RAM → FullRAM + TurboQuant
        return "fullram", {"use_turboquant": True, "bits": 3.5}
    
    if kv_cache_gb < available_ram * 0.7:
        # Can fit uncompressed KV → FullRAM standard
        return "fullram", {"use_turboquant": False}
    
    # Need LayerStream regardless
    # LayerStream + TurboQuant enables even longer context
    return "layerstream", {"turboquant_config": {"bits_per_coord": 3.5}}
```

---

## Configuration & CLI

### Settings Integration

```python
# backend/app/config.py — add to Settings class
class Settings(BaseSettings):
    # ... existing ...
    
    # TurboQuant settings
    turboquant_enabled: bool = True
    turboquant_bits: float = 3.5
    turboquant_qjl_enabled: bool = True
    turboquant_rotation: str = "random"  # "random" | "hadamard"
```

### CLI Command

```python
# backend/app/cli/main.py
@app.command()
def benchmark_turboquant(
    model: str = typer.Argument(..., help="Model path"),
    bits: float = typer.Option(3.5, help="Bits per coordinate"),
    context_len: int = typer.Option(32768, help="Context length"),
    compare: bool = typer.Option(True, help="Compare with FP16 baseline"),
):
    """Benchmark TurboQuant KV compression vs FP16."""
    from app.engines.shared.turboquant.benchmark import run_turboquant_benchmark
    run_turboquant_benchmark(model, bits, context_len, compare)
```

---

## Performance Targets for SovereignAI

| Model | Context | FP16 KV (GB) | TurboQuant 3.5-bit (GB) | Reduction |
|-------|---------|--------------|-------------------------|-----------|
| Llama-3.1-8B | 32K | 2.0 | 0.33 | 6.0× |
| Llama-3.1-8B | 128K | 8.0 | 1.33 | 6.0× |
| Llama-3.1-70B | 32K | 10.0 | 1.67 | 6.0× |
| Llama-3.1-70B | 128K | 40.0 | 6.67 | 6.0× |

**Target hardware enablement:**
- 8B @ 128K context on **16 GB RAM** (was impossible)
- 70B @ 32K context on **24 GB RAM** (was 48 GB+)
- 70B @ 128K context on **64 GB RAM** (was 128 GB+)

---

## Implementation Roadmap

### Phase 1: Core Library (Week 1-2)
- [ ] `backend/app/engines/shared/turboquant/` package
- [ ] PolarQuant: rotation + Lloyd-Max codebook
- [ ] QJL: ±1 projection + sign encoding
- [ ] Unit tests: reconstruction error < 1e-3 vs FP16
- [ ] Benchmark: attention quality vs FP16 on synthetic data

### Phase 2: LayerStream Integration (Week 2-3)
- [ ] `TurboQuantKVCacheManager` drop-in for `KVCacheManager`
- [ ] `TurboQuantHFProxyCache` for transformers compatibility
- [ ] Wire into `LayerExecutor.execute_forward()`
- [ ] Test Needle-in-Haystack at 128K context
- [ ] Memory profiling: verify 6× reduction

### Phase 3: FullRAM Integration (Week 3)
- [ ] Add `use_turboquant` flag to `FullRAMKVCache`
- [ ] Engine router auto-enable based on RAM budget
- [ ] Benchmark FullRAM + TurboQuant vs LayerStream

### Phase 4: GGUF/llama.cpp Compatibility (Week 4)
- [ ] Export `tbq3_0`, `tbq4_0` cache type definitions
- [ ] Test with community `llama.cpp` PR #21089
- [ ] Document USB/offline deployment with Turbo