import torch
from functools import lru_cache


@lru_cache(maxsize=4)
def get_qjl_projection(
    dim: int, qjl_dim: int, device: str = "cpu", seed: int = 123
) -> torch.Tensor:
    """Generate ±1 projection matrix for QJL (Rademacher).

    Args:
        dim: input dimension (head_dim)
        qjl_dim: projection dimension
        device: target device
        seed: rng seed for reproducibility

    Returns:
        [qjl_dim, dim] float32 projection matrix, normalized by sqrt(qjl_dim)
    """
    torch.manual_seed(seed)
    P = (torch.randint(0, 2, (qjl_dim, dim), device=device, dtype=torch.int8) * 2 - 1).to(
        torch.float32
    )
    return P / (qjl_dim**0.5)


def qjl_encode(residual: torch.Tensor, P: torch.Tensor) -> torch.Tensor:
    """Encode residual to 1-bit QJL sketch.

    Args:
        residual: [..., d] float32 residual vectors
        P: [qjl_dim, d] projection matrix

    Returns:
        [..., qjl_dim] int8 values in {-1, +1}
    """
    projected = residual @ P.T
    return torch.sign(projected).to(torch.int8)


# Empirically tuned QJL decode scale (see benchmarks/qjl_ablation.py).
#
# P is normalized by 1/sqrt(d'), so `codes @ P` has per-entry std ~1 in unit
# space regardless of d'. The naive shipped decode `codes @ P / d'`
# undercorrects; the textbook "unbiased" 1/sqrt(d') overcorrects. The
# ablation's scaling sweep found the optimum at c = 1/32 for BOTH hd=32 and
# hd=64, with a cliff at c = 1/16 (noise floor dominates):
#   3.5 bits attn NMSE: off 0.494, shipped 0.463, c=1/32 0.275, c=1/16 0.574
#   3.0/4.0 bits: c=1/32 best on normal data; at 4.0 bits heavy-tailed it
#   slightly overcorrects (0.216 vs 0.179 attn) - a documented corner. So
#   1/32 is the robust optimum at the default 3.5-bit operating point (a
#   "16x shipped" multiplier would drift across head dims and cross the cliff
#   at hd=32).
#
# Caveat: tuned on synthetic K/V (normal + t4) with random queries; hd=128
# was spot-checked (helps), not swept. Re-validate on real model K/V in the
# accuracy eval-gate task before trusting it in production.
_QJL_DECODE_SCALE = 1.0 / 32.0


def qjl_decode(qjl_codes: torch.Tensor, P: torch.Tensor) -> torch.Tensor:
    """Reconstruct residual approximation from QJL codes.

    Uses the empirically tuned scale c = 1/32 (not the textbook 1/d' or
    1/sqrt(d')): tuned via benchmarks/qjl_ablation.py across hd=32/64 and
    bits 3.0-4.0. Re-validate on real models in the eval-gate task.
    """
    return qjl_codes.to(torch.float32) @ P * _QJL_DECODE_SCALE


def pack_qjl_bits(codes: torch.Tensor) -> torch.Tensor:
    """Pack +/-1 QJL codes into uint32 words, 32 codes per word (1 bit each).

    Codes are int8 in {-1, +1}; bit i of a word holds the i-th code (0 -> -1,
    1 -> +1), little-endian. The tail is zero-padded; callers recover the
    original count from their own shape metadata.
    """
    bits = ((codes.reshape(-1).to(torch.int64) + 1) // 2)  # -1 -> 0, +1 -> 1
    n = bits.numel()
    pad = (-n) % 32
    if pad:
        bits = torch.cat([bits, bits.new_zeros(pad)])
    x = bits.reshape(-1, 32)
    weights = 2 ** torch.arange(32, dtype=torch.int64, device=bits.device)
    return (x * weights).sum(dim=1).to(torch.uint32)


def unpack_qjl_bits(packed: torch.Tensor, n: int) -> torch.Tensor:
    """Inverse of :func:`pack_qjl_bits`: recover ``n`` codes as int8 in {-1, +1}."""
    x = packed.to(torch.int64)
    bits = ((x.unsqueeze(-1) >> torch.arange(32, dtype=torch.int64, device=x.device)) & 1).reshape(-1)[:n]
    return (bits * 2 - 1).to(torch.int8)
