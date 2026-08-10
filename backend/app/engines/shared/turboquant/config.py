from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class TurboQuantConfig:
    """Configuration for TurboQuant KV cache compression.

    Two quantizer schemes:
      - "polar" (default): PolarQuant rotation + scalar codebook + optional
        QJL residual stage (the paper pipeline).
      - "affine": KIVI-style per-channel affine quantization (arXiv
        2402.02750). K gets a per-(head, dim) max-abs scale computed over the
        sequence (channel outliers), V a per-(head, token) max-abs scale
        (token outliers). No rotation, no QJL. Measured 5-28x lower real-data
        NMSE than polar at the same bit rate (benchmarks/kv_structure_probe.py).
    """

    # Quantization bits per coordinate (3.5 = lossless, 2.5 = near-lossless)
    bits_per_coord: float = 3.5

    # Per-tensor bit overrides for the affine scheme (KIVI-style asymmetric
    # budgets: per-token V is harder to quantize than per-channel K).
    # None -> bits_per_coord for both.
    k_bits: Optional[float] = None
    v_bits: Optional[float] = None

    # Quantizer scheme: "polar" (rotation + codebook + QJL) or "affine"
    # (per-channel/per-token scales, no rotation).
    quant_scheme: Literal["polar", "affine"] = "polar"

    # QJL residual correction dimension. Kept None at construction so the
    # runtime "auto" path resolves it (kv_cache.py uses `qjl_dim or head_dim`);
    # a hardcoded default here silently disabled auto for head_dim != 128.
    qjl_dim: Optional[int] = None

    # Enable QJL residual correction
    enable_qjl: bool = True

    # Bit-pack PolarQuant indices (base-`levels` into uint32 words, 9 per word
    # at 3.5 bits => ~0.44 B/coord). Off keeps one byte per index (unpacked
    # fallback for debugging / level counts too large to pack).
    bit_pack: bool = True

    # Device for quantization ops
    device: str = "cpu"
