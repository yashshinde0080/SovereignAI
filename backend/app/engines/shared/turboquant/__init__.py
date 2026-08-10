from .config import TurboQuantConfig
from .codebook import get_lloyd_max_centroids, quantize_polar
from .polarquant import get_rotation_matrix, apply_rotation, inverse_rotation
from .qjl import get_qjl_projection, qjl_encode, qjl_decode, pack_qjl_bits, unpack_qjl_bits
from .affine import quantize_affine, dequantize_affine
from .kv_cache import TurboQuantKVCacheManager, QuantizedKVCache

try:
    from .hf_proxy import TurboQuantHFProxyCache
except ImportError:
    pass  # Optional transformers dependency

__all__ = [
    "TurboQuantConfig",
    "get_lloyd_max_centroids",
    "quantize_polar",
    "get_rotation_matrix",
    "apply_rotation",
    "inverse_rotation",
    "get_qjl_projection",
    "qjl_encode",
    "qjl_decode",
    "pack_qjl_bits",
    "unpack_qjl_bits",
    "quantize_affine",
    "dequantize_affine",
    "TurboQuantKVCacheManager",
    "QuantizedKVCache",
    "TurboQuantHFProxyCache",
]
