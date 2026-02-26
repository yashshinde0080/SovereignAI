"""LayerStream Execution Engine"""
import asyncio
import time
from typing import Dict, Any, AsyncGenerator, Optional
import numpy as np

from app.engines.base import BaseEngine
from app.engines.layerstream.scheduler import LayerScheduler, LayerState
from app.engines.layerstream.prefetch import PrefetchQueue
from app.engines.layerstream.mmap_loader import MMapLoader
from app.engines.fullram.kv_cache import KVCache
from app.engines.shared.tokenizer import Tokenizer


class LayerStreamEngine(BaseEngine):
    """Layer streaming inference engine - loads layers on demand"""
    
    def __init__(self, model_path: str, hardware: Dict[str, Any], memory_manager: Any):
        super().__init__(model_path, hardware, memory_manager)
        self.mode = "layerstream"
        
        self.loader: Optional[MMapLoader] = None
        self.scheduler: Optional[LayerScheduler] = None
        self.prefetch_queue: Optional[PrefetchQueue] = None
        self.tokenizer: Optional[Tokenizer] = None
        self.kv_cache: Optional[KVCache] = None
        
        self.num_layers = 32
        self.prefetch_count = 2
        self.max_loaded_layers = 3
    
    async def load(self):
        """Initialize engine"""
        # Open model file
        self.loader = MMapLoader(self.model_path)
        self.loader.open()
        
        self.num_layers = self.loader.get_num_layers()
        
        # Initialize scheduler
        self.scheduler = LayerScheduler(
            num_layers=self.num_layers,
            max_loaded=self.max_loaded_layers,
            prefetch_count=self.prefetch_count
        )
        self.scheduler.initialize_layers(self.loader.get_all_layers())
        
        # Initialize prefetch queue
        self.prefetch_queue = PrefetchQueue(max_concurrent=2)
        asyncio.create_task(self.prefetch_queue.start(self.loader))
        
        # Initialize tokenizer
        self.tokenizer = Tokenizer(self.model_path)
        
        # Initialize KV cache (smaller for layer streaming)
        self.kv_cache = KVCache(
            num_layers=self.num_layers,
            num_heads=32,
            head_dim=128,
            max_seq_len=2048  # Smaller for memory efficiency
        )
        
        self.loaded = True
        self.stats["load_time"] = time.time()
        self.stats["mode"] = "layerstream"
    
    async def unload(self):
        """Cleanup engine"""
        if self.prefetch_queue:
            await self.prefetch_queue.stop()
            self.prefetch_queue = None
        
        if self.loader:
            self.loader.close()
            self.loader = None
        
        if self.kv_cache:
            self.kv_cache.clear()
            self.kv_cache = None
        
        self.scheduler = None
        self.loaded = False
    
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> Dict[str, Any]:
        """Generate completion with layer streaming"""
        if not self.loaded:
            raise RuntimeError("Engine not loaded")
        
        start_time = time.perf_counter()
        
        # Tokenize
        input_ids = self.tokenizer.encode(prompt)
        prompt_tokens = len(input_ids)
        
        # Generate tokens
        generated_tokens = []
        layer_times = []
        
        for _ in range(max_tokens):
            token_start = time.perf_counter()
            
            # Forward pass through all layers
            activations = await self._embed(input_ids + generated_tokens)
            
            for layer_id in range(self.num_layers):
                # Schedule prefetch for next layers
                await self._schedule_prefetch(layer_id)
                
                # Ensure layer is loaded
                layer_buffer = await self.scheduler.ensure_loaded(layer_id, self.loader)
                
                # Compute layer
                activations = await self._compute_layer(layer_id, activations, layer_buffer)
                
                # Evict previous layer if needed
                if layer_id > 0:
                    await self.scheduler.evict_layer(layer_id - 1)
            
            # Final projection
            logits = await self._final_projection(activations)
            
            # Sample next token
            next_token = self._sample(logits, temperature, top_p)
            
            layer_times.append(time.perf_counter() - token_start)
            
            if next_token == self.tokenizer.eos_token_id:
                break
            
            generated_tokens.append(next_token)
        
        # Decode output
        output_text = self.tokenizer.decode(generated_tokens)
        
        elapsed = time.perf_counter() - start_time
        completion_tokens = len(generated_tokens)
        
        return {
            "text": output_text,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "time_seconds": elapsed,
            "tokens_per_second": completion_tokens / elapsed if elapsed > 0 else 0,
            "avg_layer_time_ms": np.mean(layer_times) * 1000 if layer_times else 0,
            "finish_reason": "stop"
        }
    
    async def generate_stream(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate with streaming"""
        if not self.loaded:
            raise RuntimeError("Engine not loaded")
        
        # Tokenize
        input_ids = self.tokenizer.encode(prompt)
        generated_tokens = []
        
        for _ in range(max_tokens):
            # Forward pass
            activations = await self._embed(input_ids + generated_tokens)
            
            for layer_id in range(self.num_layers):
                await self._schedule_prefetch(layer_id)
                layer_buffer = await self.scheduler.ensure_loaded(layer_id, self.loader)
                activations = await self._compute_layer(layer_id, activations, layer_buffer)
                
                if layer_id > 0:
                    await self.scheduler.evict_layer(layer_id - 1)
            
            logits = await self._final_projection(activations)
            next_token = self._sample(logits, temperature, top_p)
            
            if next_token == self.tokenizer.eos_token_id:
                yield {"token": "", "finish_reason": "stop"}
                break
            
            generated_tokens.append(next_token)
            token_text = self.tokenizer.decode([next_token])
            
            yield {
                "token": token_text,
                "finish_reason": None,
                "layers_loaded": self.scheduler.get_loaded_count()
            }
    
    async def _schedule_prefetch(self, current_layer: int):
        """Schedule prefetch for upcoming layers"""
        for i in range(1, self.prefetch_count + 1):
            next_layer = current_layer + i
            if next_layer < self.num_layers:
                await self.prefetch_queue.schedule(next_layer)
    
    async def _embed(self, tokens: list) -> np.ndarray:
        """Get embeddings for tokens"""
        # Placeholder - real implementation uses embedding layer
        embed_dim = 4096
        return np.random.randn(len(tokens), embed_dim).astype(np.float32)
    
    async def _compute_layer(
        self,
        layer_id: int,
        activations: np.ndarray,
        layer_buffer: bytes
    ) -> np.ndarray:
        """Compute single transformer layer"""
        # Placeholder - real implementation uses layer weights
        # Simulates computation time
        await asyncio.sleep(0.001)
        return activations + np.random.randn(*activations.shape).astype(np.float32) * 0.01
    
    async def _final_projection(self, activations: np.ndarray) -> np.ndarray:
        """Project to vocabulary"""
        vocab_size = 32000
        return np.random.randn(vocab_size).astype(np.float32)
    
    def _sample(self, logits: np.ndarray, temperature: float, top_p: float) -> int:
        """Sample next token"""
        if temperature == 0:
            return int(np.argmax(logits))
        
        logits = logits / temperature
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / np.sum(exp_logits)
        
        sorted_indices = np.argsort(probs)[::-1]
        cumsum = np.cumsum(probs[sorted_indices])
        cutoff_idx = np.searchsorted(cumsum, top_p)
        top_indices = sorted_indices[:cutoff_idx + 1]
        
        top_probs = probs[top_indices]
        top_probs = top_probs / np.sum(top_probs)
        
        return int(np.random.choice(top_indices, p=top_probs))
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage stats"""
        import psutil
        process = psutil.Process()
        
        return {
            "ram_used_gb": process.memory_info().rss / (1024**3),
            "layers_loaded": self.scheduler.get_loaded_count() if self.scheduler else 0,
            "layer_memory_mb": self.scheduler.get_memory_usage() / (1024**2) if self.scheduler else 0,
            "kv_cache_mb": self.kv_cache.get_memory_usage() / (1024**2) if self.kv_cache else 0,
            "prefetch_stats": self.prefetch_queue.get_stats() if self.prefetch_queue else {}
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics"""
        return {
            **self.stats,
            "memory": self.get_memory_usage(),
            "num_layers": self.num_layers,
            "max_loaded_layers": self.max_loaded_layers
        }