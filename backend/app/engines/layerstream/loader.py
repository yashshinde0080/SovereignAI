import os
import time
import gc
import psutil
import torch
from typing import Dict, Optional, Set
from concurrent.futures import ThreadPoolExecutor
from safetensors.torch import safe_open

from .quant_config import QuantConfig


class LayerWeightLoader:
    def __init__(self, weights_dir: str, prefetch_depth: int = 3,
                 cache_budget_mb: Optional[float] = None,
                 pinned_paths: Optional[Set[str]] = None):
        self.weights_dir = weights_dir
        self.prefetch_depth = max(1, prefetch_depth)
        self.executor = ThreadPoolExecutor(max_workers=self.prefetch_depth)
        self.futures: Dict[str, "object"] = {}  # path -> Future
        self.cpu_cache: Dict[str, Dict[str, object]] = {}
        self.pinned = set(pinned_paths or ())
        # Budget in bytes; None = unlimited (legacy behavior). Only non-pinned
        # bytes count against it, so pinned paths never consume the window.
        self.budget_bytes = cache_budget_mb * (1024 ** 2) if cache_budget_mb else None
        self._cached_bytes = 0      # non-pinned bytes only
        self._pinned_bytes = 0      # tracked separately, exempt from budget
        self._lru: Dict[str, float] = {}
        self.quant_config = QuantConfig.load(os.path.join(weights_dir, "quant_config.json"))

    @property
    def is_quantized(self) -> bool:
        return self.quant_config.quant_method not in ("none",)

    @property
    def quant_method(self) -> str:
        return self.quant_config.quant_method

    def _load_file(self, path: str) -> Dict[str, object]:
        """Loads safetensors to CPU in its stored form.

        Quantized tensors stay quantized (int8 + scale, or packed int4 nibbles
        + scale): dequantization happens on the compute device in
        ``dequantize_on_device``, so RAM holds the small form and the device
        pays the conversion. fp16/fp32 layers are returned as-is.
        """
        if not os.path.exists(path):
            return {}
        state_dict = {}
        with safe_open(path, framework="pt", device="cpu") as f:
            for k in f.keys():
                state_dict[k] = f.get_tensor(k)
        return state_dict

    def prefetch_async(self, path: str):
        """Asynchronously load up to prefetch_depth layers ahead.

        Keeps at most ``prefetch_depth`` futures in flight. Completed futures
        are reaped to make room; a full window of in-flight loads is left for
        the caller to retry on the next layer step (the window slides forward
        as ``get_weights`` consumes futures).
        """
        if path in self.cpu_cache or path in self.futures:
            return
        if len(self.futures) >= self.prefetch_depth:
            done = [p for p, f in self.futures.items() if f.done()]
            if not done:
                return  # window full of in-flight loads; caller retries
            for p in done:
                self._cache(p, self.futures.pop(p).result())
        self.futures[path] = self.executor.submit(self._load_file, path)

    def get_weights(self, path: str) -> Dict[str, object]:
        """Provides weights, waiting for an in-flight prefetch if present.

        Cache policy: pinned paths (embed/norm/lm_head) are never evicted;
        everything else is LRU-evicted once ``budget_bytes`` is exceeded.
        """
        if path in self.cpu_cache:
            self._touch(path)
            return self.cpu_cache[path]

        if path in self.futures:
            state_dict = self.futures.pop(path).result()
        else:
            state_dict = self._load_file(path)

        self._cache(path, state_dict)
        return state_dict

    def _cache(self, path: str, state_dict: Dict[str, object]):
        self.cpu_cache[path] = state_dict
        size = _tensor_bytes(state_dict)
        if path in self.pinned:
            self._pinned_bytes += size
        else:
            self._cached_bytes += size
        self._touch(path)
        self._enforce_budget()

    def _touch(self, path: str):
        self._lru[path] = time.monotonic()

    def _enforce_budget(self):
        """Evict non-pinned LRU entries until under the byte budget.

        No gc.collect() here: tensors are freed by reference counting the moment
        they leave the cache; Python GC only chases reference cycles, which
        tensors do not form. A full collect per eviction cost ~1.5s/pass in the
        benchmark.
        """
        if self.budget_bytes is None:
            return
        while self._cached_bytes > self.budget_bytes:
            candidates = [p for p in self.cpu_cache if p not in self.pinned]
            if not candidates:
                return  # pinned-only cache; nothing evictable
            lru_path = min(candidates, key=lambda p: self._lru.get(p, 0.0))
            self._cached_bytes -= _tensor_bytes(self.cpu_cache.pop(lru_path))
            self._lru.pop(lru_path, None)

    def get_cache_stats(self) -> Dict[str, object]:
        """Cache occupancy for the benchmark/report."""
        return {
            "cached_entries": len(self.cpu_cache),
            "cached_mb": (self._cached_bytes + self._pinned_bytes) / (1024 ** 2),
            "budget_mb": self.budget_bytes / (1024 ** 2) if self.budget_bytes else None,
            "pinned_entries": len(self.pinned),
            "futures_in_flight": len(self.futures),
            "prefetch_depth": self.prefetch_depth,
            "process_rss_mb": psutil.Process().memory_info().rss / (1024 ** 2),
        }

    def clear_cache(self):
        for f in self.futures.values():
            f.cancel()
        self.futures.clear()
        self.cpu_cache.clear()
        self._lru.clear()
        self._cached_bytes = 0
        self._pinned_bytes = 0
        self.executor.shutdown(wait=False)
        gc.collect()


def dequantize_on_device(tensor: torch.Tensor, scale: torch.Tensor, device,
                         dtype: torch.dtype, target_shape) -> torch.Tensor:
    """Dequantize an int8 or packed-int4 tensor on the compute device.

    ``tensor``/``scale`` are the raw stored forms from a split dir:

    - int8: tensor is int8, scale is a per-tensor fp32 scalar (view(1)).
    - int4: tensor is uint8 nibbles packed little-endian (byte = hi<<4|lo),
      two's complement [-8, 7]; scale is fp16 [rows, num_groups] where each
      group of 32 covers cols/32 columns. ``target_shape`` restores the true
      (unpadded) shape the parameter expects.

    Returns a tensor on ``device`` in ``dtype`` ready for matmul.
    """
    if tensor.dtype == torch.int8:
        return tensor.to(device=device, dtype=dtype) * scale.to(device, dtype)

    # int4: unpack nibbles back to interleaved q_flat = [lo, hi, lo, hi, ...]
    packed = tensor.to(device)
    rows = packed.numel() // packed.shape[-1] if packed.dim() > 1 else 1
    p2 = packed.reshape(rows, -1)
    lo = (p2 & 0x0F).to(torch.int8)
    hi = ((p2 >> 4) & 0x0F).to(torch.int8)
    lo = torch.where(lo >= 8, lo - 16, lo)  # two's complement nibble -> [-8, 7]
    hi = torch.where(hi >= 8, hi - 16, hi)
    # interleave lo,hi,lo,hi... matching the splitter's 0::2/1::2 layout
    q_flat = torch.stack([lo, hi], dim=-1).reshape(rows, -1)

    n_groups = scale.shape[-1]
    q = q_flat.reshape(rows, n_groups, 32).to(dtype)
    q = q * scale.to(device, dtype).unsqueeze(-1)  # [rows, groups, 32]
    q = q.reshape(rows, -1)
    cols = target_shape[-1]
    if cols < q.shape[1]:
        q = q[:, :cols]  # strip group padding
    return q.reshape(target_shape)


def _tensor_bytes(state_dict: Dict[str, object]) -> int:
    total = 0
    for t in state_dict.values():
        try:
            total += t.numel() * t.element_size()
        except AttributeError:
            pass
    return total
