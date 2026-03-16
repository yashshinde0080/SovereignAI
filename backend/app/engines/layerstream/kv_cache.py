import torch
from typing import Optional, Tuple, List
from transformers.cache_utils import DynamicCache

class KVCacheManager:
    """Manages KV cache strictly on CPU with O(1 layer) GPU footprint."""
    def __init__(self):
        self.key_cache: List[Optional[torch.Tensor]] = []
        self.value_cache: List[Optional[torch.Tensor]] = []
        self.conv_states: List[Optional[torch.Tensor]] = []
        self.recurrent_states: List[Optional[torch.Tensor]] = []
        self.seq_length: int = 0
        
    def ensure_layer(self, layer_idx: int):
        while len(self.key_cache) <= layer_idx:
            self.key_cache.append(None)
            self.value_cache.append(None)
            self.conv_states.append(None)
            self.recurrent_states.append(None)
            
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
        self.conv_states = []
        self.recurrent_states = []
        self.seq_length = 0
        
    def get_seq_length(self, layer_idx: int = 0) -> int:
        return self.seq_length
        
    def get_size_mb(self) -> float:
        total_bytes = 0
        for lst in (self.key_cache, self.value_cache, self.conv_states, self.recurrent_states):
            for t in lst:
                if t is not None:
                    total_bytes += t.nelement() * t.element_size()
        return total_bytes / (1024 ** 2)


class ProxyList:
    def __init__(self, manager: KVCacheManager, attr_name: str):
        self.manager = manager
        self.attr_name = attr_name
        self._active_views = {}
        
    def __getitem__(self, i: int):
        self.manager.ensure_layer(i)
        lst = getattr(self.manager, self.attr_name)
        val = lst[i]
        if val is not None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            view = val.to(device)
            self._active_views[i] = view
            return view
        return None
        
    def __setitem__(self, i: int, val):
        self.manager.ensure_layer(i)
        lst = getattr(self.manager, self.attr_name)
        if val is not None:
            self._active_views[i] = val
            lst[i] = val.detach().cpu()
        else:
            if i in self._active_views:
                del self._active_views[i]
            lst[i] = None

    def sync_back(self):
        lst = getattr(self.manager, self.attr_name)
        for i, view in self._active_views.items():
            if view is not None:
                lst[i] = view.detach().cpu()
        self._active_views.clear()

class HFProxyCache(DynamicCache):
    """Interface to map layer-local KV tuple seamlessly into transformers.DynamicCache"""
    def __init__(self, manager: KVCacheManager):
        super().__init__()
        self.manager = manager
        self.conv_states = ProxyList(manager, "conv_states")
        self.recurrent_states = ProxyList(manager, "recurrent_states")
        
    @property
    def has_previous_state(self):
        return self.manager.get_seq_length(0) > 0 or (len(self.manager.conv_states) > 0 and any(c is not None for c in self.manager.conv_states))
        
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
        if layer_idx < len(self.manager.key_cache) and self.manager.key_cache[layer_idx] is not None:
            return self.manager.key_cache[layer_idx].shape[-2]
        for k in self.manager.key_cache:
            if k is not None:
                return k.shape[-2]
        return self.manager.get_seq_length(layer_idx)
        
    def get_max_length(self) -> Optional[int]:
        return None
    
    def __len__(self):
        return len(self.manager.key_cache)
    
    def __getitem__(self, layer_idx: int):
        kv = self.manager.get(layer_idx)
        if kv is not None:
            return kv
        return None
