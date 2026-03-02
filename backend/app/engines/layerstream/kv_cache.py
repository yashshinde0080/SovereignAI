import torch
from typing import Optional, Tuple, List
from transformers.cache_utils import DynamicCache

class KVCacheManager:
    """Manages KV cache strictly on CPU with O(1 layer) GPU footprint."""
    def __init__(self):
        self.key_cache: List[Optional[torch.Tensor]] = []
        self.value_cache: List[Optional[torch.Tensor]] = []
        
    def ensure_layer(self, layer_idx: int):
        while len(self.key_cache) <= layer_idx:
            self.key_cache.append(None)
            self.value_cache.append(None)
            
    def get(self, layer_idx: int) -> Optional[Tuple[torch.Tensor, torch.Tensor]]:
        if layer_idx < len(self.key_cache):
            k = self.key_cache[layer_idx]
            v = self.value_cache[layer_idx]
            if k is not None and v is not None:
                return k, v
        return None
        
    def set(self, layer_idx: int, kv: Tuple[torch.Tensor, torch.Tensor]):
        self.ensure_layer(layer_idx)
        k, v = kv
        # Enforce CPU residency
        self.key_cache[layer_idx] = k.detach().cpu()
        self.value_cache[layer_idx] = v.detach().cpu()
        
    def clear(self):
        self.key_cache = []
        self.value_cache = []
        
    def get_seq_length(self, layer_idx: int = 0) -> int:
        if layer_idx < len(self.key_cache) and self.key_cache[layer_idx] is not None:
            return self.key_cache[layer_idx].shape[-2]
        return 0
        
    def get_size_mb(self) -> float:
        total_bytes = 0
        for k in self.key_cache:
            if k is not None:
                total_bytes += k.nelement() * k.element_size()
        for v in self.value_cache:
            if v is not None:
                total_bytes += v.nelement() * v.element_size()
        return total_bytes / (1024 ** 2)


class HFProxyCache(DynamicCache):
    """Interface to map layer-local KV tuple seamlessly into transformers.DynamicCache"""
    def __init__(self, manager: KVCacheManager):
        super().__init__()
        self.manager = manager
        
    def update(
        self,
        key_states: torch.Tensor,
        value_states: torch.Tensor,
        layer_idx: int,
        cache_kwargs=None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        past_kv = self.manager.get(layer_idx)
        if past_kv is not None:
            k_cpu, v_cpu = past_kv
            k_new = torch.cat([k_cpu.to(key_states.device), key_states], dim=-2)
            v_new = torch.cat([v_cpu.to(value_states.device), value_states], dim=-2)
        else:
            k_new = key_states
            v_new = value_states
            
        self.manager.set(layer_idx, (k_new, v_new))
        return k_new, v_new
        
    def get_seq_length(self, layer_idx: int = 0) -> int:
        return self.manager.get_seq_length(layer_idx)
        
    def get_max_length(self) -> Optional[int]:
        return None
