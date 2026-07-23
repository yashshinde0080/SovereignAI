from typing import Optional, Tuple
import torch

from .kv_cache import TurboQuantKVCacheManager

try:
    from transformers.cache_utils import DynamicCache as _DynamicCache
except ImportError:
    _DynamicCache = object  # Fallback if transformers not installed


class TurboQuantHFProxyCache(_DynamicCache):
    """Drop-in for HFProxyCache using TurboQuant compression.

    Compatible with the DynamicCache interface transformers model layers expect.
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
        """Store quantized K/V, return dequantized for current attention."""
        self.tq_manager.update(layer_idx, key_states, value_states)
        self._seen_layers.add(layer_idx)
        return self.tq_manager.get(layer_idx, key_states.device)

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
        # ponytail: beam search reorder not implemented — add if beam search needed
        raise NotImplementedError("Beam search reorder not yet supported with TurboQuant")
