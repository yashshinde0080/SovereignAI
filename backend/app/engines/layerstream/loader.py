import os
import torch
import gc
from typing import Dict
from concurrent.futures import ThreadPoolExecutor
from safetensors.torch import safe_open

class LayerWeightLoader:
    def __init__(self, weights_dir: str):
        self.weights_dir = weights_dir
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.future = None
        self.future_path = None
        self.cpu_cache: Dict[str, Dict[str, torch.Tensor]] = {}
    
    def _load_file(self, path: str) -> Dict[str, torch.Tensor]:
        """Loads safetensors directly into CPU without hitting GPU memory."""
        if not os.path.exists(path):
            return {}
        state_dict = {}
        with safe_open(path, framework="pt", device="cpu") as f:
            for k in f.keys():
                state_dict[k] = f.get_tensor(k)
        return state_dict

    def prefetch_async(self, path: str):
        """Asynchronously double-buffer the loading of the next tensor."""
        if path not in self.cpu_cache and self.future is None:
            self.future = self.executor.submit(self._load_file, path)
            self.future_path = path

    def get_weights(self, path: str) -> Dict[str, torch.Tensor]:
        """Provides weights and permanently caches them in CPU memory to avoid duplicate IO loops."""
        if path in self.cpu_cache:
            return self.cpu_cache[path]
            
        if self.future is not None and self.future_path == path:
            state_dict = self.future.result()
            self.cpu_cache[path] = state_dict
            self.future = None
            self.future_path = None
            return state_dict
            
        state_dict = self._load_file(path)
        self.cpu_cache[path] = state_dict
        return state_dict
        
    def clear_cache(self):
        self.cpu_cache.clear()
        gc.collect()
