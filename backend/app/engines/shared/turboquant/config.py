from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class TurboQuantConfig:
    """Configuration for TurboQuant KV cache compression.

    Controls the PolarQuant + QJL two-stage pipeline for ~6× KV cache
    compression with near-lossless quality at 3.5 bits/channel.
    """

    # Quantization bits per coordinate (3.5 = lossless, 2.5 = near-lossless)
    bits_per_coord: float = 3.5

    # QJL residual correction dimension. Kept None at construction so the
    # runtime "auto" path resolves it (kv_cache.py uses `qjl_dim or head_dim`);
    # a hardcoded default here silently disabled auto for head_dim != 128.
    qjl_dim: Optional[int] = None

    # Enable/disable stages
    enable_polarquant: bool = True
    enable_qjl: bool = True

    # Bit-pack PolarQuant indices (base-`levels` into uint32 words, 9 per word
    # at 3.5 bits => ~0.44 B/coord). Off keeps one byte per index (unpacked
    # fallback for debugging / level counts too large to pack).
    bit_pack: bool = True

    # Rotation matrix strategy
    rotation_type: Literal["random", "hadamard"] = "random"

    # Codebook type for scalar quantizer
    codebook_type: str = "beta_lloyd_max"

    # Device for quantization ops
    device: str = "cpu"

    # Collect debug stats
    collect_stats: bool = False
