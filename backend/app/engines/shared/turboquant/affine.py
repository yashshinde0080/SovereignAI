"""KIVI-style per-channel affine quantization for the KV cache.

The polar scheme normalizes each vector, rotates it, and scalar-quantizes the
direction with a codebook on [-1, 1] — good when rotated coordinates are iid,
but the rotation destroys the per-channel magnitude structure real K/V have.
The affine scheme keeps that structure (the KIVI insight, arXiv:2402.02750):
each (head, dim) channel of K gets its own max-abs scale computed over the
sequence, each token of V gets its own max-abs scale computed over head dims,
and coordinates are quantized uniformly within their scale. Measured on real
Qwen2-0.5B K/V this is 5-28x lower NMSE than polar at the same bit rate
(benchmarks/kv_structure_probe.py), because raw channels vary ~10x in scale
while rotated unit-vector coordinates are forced into [-1, 1].
"""

import torch


def quantize_affine(
    x: torch.Tensor, levels: int, axis: int
) -> tuple[torch.Tensor, torch.Tensor]:
    """Per-group symmetric affine quantization.

    Args:
        x: [nh, seq, hd] float32 tensor (one chunk, one layer)
        levels: codebook size (2 ** bits); odd levels supported (e.g. 11)
        axis: 1 -> scale per (nh, hd) channel over the seq dim (K-style);
              2 -> scale per (nh, seq) token over the hd dim (V-style)

    Returns:
        indices: [nh, seq, hd] uint8/int32 in [0, levels)
        scale:   [nh, 1, hd] (axis=1) or [nh, seq, 1] (axis=2) float32
    """
    # Level positions span symmetric ±half in level units (half = 7.5 for 16
    # levels, 5.0 for 11). The index mapping `round(x_level + half)` is exactly
    # bijective for BOTH odd and even counts: truncating would shift every
    # interior index by -0.5 (a half-step bias, 3x worse NMSE) — caught by
    # TestAffineScheme.test_roundtrip_shape_and_nmse.
    half = (levels - 1) / 2.0
    scale = x.abs().amax(dim=axis, keepdim=True).clamp(min=1e-12)
    x_level = x / scale * half
    indices = (x_level + half).round().clamp(0, levels - 1).to(torch.int64)
    idx_dtype = torch.uint8 if levels <= 255 else torch.int32
    return indices.to(idx_dtype), scale


def dequantize_affine(
    indices: torch.Tensor, scale: torch.Tensor, levels: int
) -> torch.Tensor:
    """Inverse of :func:`quantize_affine`: reconstruct from indices + scale."""
    half = (levels - 1) / 2.0
    q = indices.to(torch.float32) - half
    return q / half * scale  # exact inverse: round(x_level + half) - half == x_level
