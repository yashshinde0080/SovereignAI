"""KV Cache for FullRAM Engine"""
from typing import Optional, Tuple
import numpy as np


class KVCache:
    """Key-Value cache for transformer attention"""
    
    def __init__(
        self,
        num_layers: int,
        num_heads: int,
        head_dim: int,
        max_seq_len: int,
        dtype=np.float16
    ):
        self.num_layers = num_layers
        self.num_heads = num_heads
        self.head_dim = head_dim
        self.max_seq_len = max_seq_len
        self.dtype = dtype
        
        # Pre-allocate cache
        cache_shape = (num_layers, 2, max_seq_len, num_heads, head_dim)
        self.cache = np.zeros(cache_shape, dtype=dtype)
        self.position = 0
    
    def update(
        self,
        layer_idx: int,
        key: np.ndarray,
        value: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Update cache with new key/value"""
        seq_len = key.shape[0]
        
        if self.position + seq_len > self.max_seq_len:
            # Sliding window - shift cache
            shift = seq_len
            self.cache[:, :, :-shift] = self.cache[:, :, shift:]
            self.position = self.max_seq_len - seq_len
        
        # Store new values
        self.cache[layer_idx, 0, self.position:self.position + seq_len] = key
        self.cache[layer_idx, 1, self.position:self.position + seq_len] = value
        
        # Return full cache for this layer
        k = self.cache[layer_idx, 0, :self.position + seq_len]
        v = self.cache[layer_idx, 1, :self.position + seq_len]
        
        return k, v
    
    def get(self, layer_idx: int) -> Tuple[np.ndarray, np.ndarray]:
        """Get cached key/value for layer"""
        return (
            self.cache[layer_idx, 0, :self.position],
            self.cache[layer_idx, 1, :self.position]
        )
    
    def clear(self):
        """Clear cache"""
        self.cache.fill(0)
        self.position = 0
    
    def get_memory_usage(self) -> int:
        """Get cache memory usage in bytes"""
        return self.cache.nbytes