"""FullRAM Execution Engine"""
import asyncio
import time
from typing import Dict, Any, AsyncGenerator, Optional
import numpy as np

from app.engines.base import BaseEngine
from app.engines.fullram.loader import GGUFLoader
from app.engines.fullram.kv_cache import KVCache
from app.engines.shared.tokenizer import Tokenizer


class FullRAMEngine(BaseEngine):
    """Full RAM inference engine - loads entire model into memory"""
    
    def __init__(self, model_path: str, hardware: Dict[str, Any], memory_manager: Any):
        super().__init__(model_path, hardware, memory_manager)
        self.mode = "fullram"
        self.loader: Optional[GGUFLoader] = None
        self.tokenizer: Optional[Tokenizer] = None
        self.kv_cache: Optional[KVCache] = None
        self.model_config = {}
    
    async def load(self):
        """Load model into RAM"""
        # Load model file
        self.loader = GGUFLoader(self.model_path)
        self.loader.load()
        
        # Get model config
        self.model_config = self.loader.get_metadata()
        
        # Initialize tokenizer
        self.tokenizer = Tokenizer(self.model_path)
        
        # Initialize KV cache
        # These would come from model config
        self.kv_cache = KVCache(
            num_layers=32,
            num_heads=32,
            head_dim=128,
            max_seq_len=4096
        )
        
        self.loaded = True
        self.stats["load_time"] = time.time()
    
    async def unload(self):
        """Unload model from RAM"""
        if self.loader:
            self.loader.unload()
            self.loader = None
        
        if self.kv_cache:
            self.kv_cache.clear()
            self.kv_cache = None
        
        self.loaded = False
    
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> Dict[str, Any]:
        """Generate completion"""
        if not self.loaded:
            raise RuntimeError("Model not loaded")
        
        start_time = time.perf_counter()
        
        # Tokenize
        input_ids = self.tokenizer.encode(prompt)
        prompt_tokens = len(input_ids)
        
        # Generate tokens
        generated_tokens = []
        
        for _ in range(max_tokens):
            # Forward pass (simplified)
            next_token = await self._forward_pass(input_ids + generated_tokens)
            
            # Sample
            sampled = self._sample(next_token, temperature, top_p)
            
            if sampled == self.tokenizer.eos_token_id:
                break
            
            generated_tokens.append(sampled)
        
        # Decode
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
            raise RuntimeError("Model not loaded")
        
        # Tokenize
        input_ids = self.tokenizer.encode(prompt)
        generated_tokens = []
        
        for i in range(max_tokens):
            # Forward pass
            next_token = await self._forward_pass(input_ids + generated_tokens)
            
            # Sample
            sampled = self._sample(next_token, temperature, top_p)
            
            if sampled == self.tokenizer.eos_token_id:
                yield {
                    "token": "",
                    "finish_reason": "stop"
                }
                break
            
            generated_tokens.append(sampled)
            token_text = self.tokenizer.decode([sampled])
            
            yield {
                "token": token_text,
                "finish_reason": None
            }
            
            # Small delay to simulate real inference
            await asyncio.sleep(0.01)
    
    async def _forward_pass(self, tokens: list) -> np.ndarray:
        """
        Forward pass through model.
        This is a placeholder - real implementation would use llama.cpp bindings.
        """
        # Simulated logits
        vocab_size = 32000
        return np.random.randn(vocab_size).astype(np.float32)
    
    def _sample(
        self,
        logits: np.ndarray,
        temperature: float,
        top_p: float
    ) -> int:
        """Sample next token from logits"""
        if temperature == 0:
            return int(np.argmax(logits))
        
        # Apply temperature
        logits = logits / temperature
        
        # Softmax
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / np.sum(exp_logits)
        
        # Top-p sampling
        sorted_indices = np.argsort(probs)[::-1]
        cumsum = np.cumsum(probs[sorted_indices])
        
        cutoff_idx = np.searchsorted(cumsum, top_p)
        top_indices = sorted_indices[:cutoff_idx + 1]
        
        # Renormalize
        top_probs = probs[top_indices]
        top_probs = top_probs / np.sum(top_probs)
        
        # Sample
        return int(np.random.choice(top_indices, p=top_probs))
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage"""
        import psutil
        process = psutil.Process()
        
        return {
            "ram_used_gb": process.memory_info().rss / (1024**3),
            "peak_ram_gb": process.memory_info().peak_wset / (1024**3) if hasattr(process.memory_info(), 'peak_wset') else 0,
            "kv_cache_mb": self.kv_cache.get_memory_usage() / (1024**2) if self.kv_cache else 0
        }