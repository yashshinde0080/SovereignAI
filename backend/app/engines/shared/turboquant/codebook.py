import torch
import numpy as np
from functools import lru_cache
from scipy.stats import beta as beta_dist
from scipy.integrate import quad


@lru_cache(maxsize=8)
def get_lloyd_max_centroids(dim: int, bits: float, device: str = "cpu") -> torch.Tensor:
    """Compute optimal Lloyd-Max centroids for rotated-vector coordinates.

    After random orthogonal rotation, coordinates of a unit vector follow
    a symmetric distribution on [-1, 1] with density proportional to
    (1 - x^2)^((d-3)/2), which is equivalent to a scaled Beta distribution:
    if Y ~ Beta(1/2, (dim-1)/2) on [0, 1], then X = 2Y - 1 on [-1, 1].

    Centroids are symmetric around 0 and shared across all layers/models.
    """
    alpha = 0.5
    beta_param = (dim - 1) / 2.0
    num_levels = int(2**bits)  # ponytail: only even power_of_2 combos give symmetric codebook

    # Generate symmetric centroids on [-1, 1]
    # Use half the levels for the positive side, mirror for negative
    num_pos = num_levels // 2
    has_zero = num_levels % 2 == 1

    if num_pos == 0:
        return torch.tensor([0.0], dtype=torch.float32, device=device)

    # Quantiles for positive side distribution of |X| where X ~ scaled Beta
    pos_quantiles = np.linspace(1 / (num_pos + 1), 1 - 1 / (num_pos + 1), num_pos)
    # Beta(1/2, (d-1)/2) on [0, 1], map to [-1, 1] positive side: Y -> 2Y - 1
    pos_centroids = 2 * beta_dist.ppf(pos_quantiles, alpha, beta_param) - 1

    # Refine via Lloyd-Max on the transformed distribution
    for _ in range(3):
        boundaries = np.concatenate(
            [[-np.inf], (pos_centroids[:-1] + pos_centroids[1:]) / 2, [np.inf]]
        )
        new_pos = []
        for i in range(len(pos_centroids)):
            a, b = boundaries[i], boundaries[i + 1]
            # Clip to [0, 1] for Beta integration
            a_c = max(0.0, (a + 1) / 2)
            b_c = min(1.0, (b + 1) / 2)
            if a_c >= b_c:
                new_pos.append(pos_centroids[i])
                continue
            num, _ = quad(lambda x: (2 * x - 1) * beta_dist.pdf(x, alpha, beta_param), a_c, b_c)
            den = beta_dist.cdf(b_c, alpha, beta_param) - beta_dist.cdf(a_c, alpha, beta_param)
            new_pos.append(num / den if den > 0 else pos_centroids[i])
        pos_centroids = np.array(new_pos)

    # Build symmetric codebook
    if has_zero:
        centroids = np.concatenate([-pos_centroids[::-1], [0.0], pos_centroids])
    else:
        centroids = np.concatenate([-pos_centroids[::-1], pos_centroids])

    return torch.tensor(centroids, dtype=torch.float32, device=device)


def quantize_polar(
    x: torch.Tensor, centroids: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor]:
    """Quantize rotated vectors to nearest centroids.

    Args:
        x: [..., d] rotated vectors
        centroids: [num_levels] optimal centroids (symmetric around 0)

    Returns:
        indices: [..., d] uint8 centroid indices (uint16 if >256 levels)
        quantized: [..., d] reconstructed values
    """
    diff = x.unsqueeze(-1) - centroids.view(*([1] * x.ndim), -1)
    idx_dtype = torch.uint8 if len(centroids) <= 255 else torch.int32
    indices = diff.abs().argmin(dim=-1).to(idx_dtype)
    quantized = centroids[indices.long()]
    return indices, quantized
