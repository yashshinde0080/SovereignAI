"""LayerStream Execution Engine"""
import asyncio
import time
import os
from pathlib import Path
from typing import Dict, Any, AsyncGenerator, Optional
import numpy as np

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer
from threading import Thread
import psutil

from app.engines.base import BaseEngine

class LayerStreamEngine(BaseEngine):
    """Layer streaming inference engine - loads layers on demand from disk"""
    
    def __init__(self, model_path: str, hardware: Dict[str, Any], memory_manager: Any):
        super().__init__(model_path, hardware, memory_manager)
        self.mode = "layerstream"
        
        self.tokenizer = None
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
    async def load(self):
        """Initialize engine with disk offloading (Layer Streaming via Accelerate)"""
        start_time = time.time()
        
        from accelerate import init_empty_weights, load_checkpoint_and_dispatch
        from transformers import AutoConfig
        
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_path, 
            trust_remote_code=True,
            local_files_only=True
        )
        
        offload_dir = Path("offload_cache")
        offload_dir.mkdir(exist_ok=True)
        
        # Dispatch with offloading directly
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            device_map="auto",
            offload_folder=str(offload_dir),
            trust_remote_code=True,
            local_files_only=True
        )
        self.model.eval()
        
        if not self.tokenizer.pad_token:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            
        self.loaded = True
        self.stats["load_time"] = time.time() - start_time
        print(f"Loaded {self.model_path} in LayerStream (Accelerate) mode in {self.stats['load_time']:.1f}s")
    
    async def unload(self):
        """Cleanup engine"""
        if self.model:
            del self.model
            self.model = None
            
        if self.tokenizer:
            del self.tokenizer
            self.tokenizer = None
            
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            
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
        
        # Tokenize (moves to right device inside model normally)
        inputs = self.tokenizer(prompt, return_tensors="pt")
        # Moving explicitly to model's first device
        target_device = getattr(self.model, "device", self.device)
        inputs = {k: v.to(target_device) for k, v in inputs.items()}
        prompt_tokens = inputs["input_ids"].shape[1]
        
        generation_kwargs = dict(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=temperature if temperature > 0 else 1.0,
            do_sample=temperature > 0,
            top_p=top_p,
            pad_token_id=self.tokenizer.eos_token_id
        )
        
        def _generate():
            with torch.no_grad():
                return self.model.generate(**generation_kwargs)
                
        output_ids = await asyncio.to_thread(_generate)
        output_ids = output_ids[0][prompt_tokens:]
        
        output_text = self.tokenizer.decode(output_ids, skip_special_tokens=True)
        completion_tokens = len(output_ids)
        elapsed = time.perf_counter() - start_time
        
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
            raise RuntimeError("Engine not loaded")
        
        inputs = self.tokenizer(prompt, return_tensors="pt")
        target_device = getattr(self.model, "device", self.device)
        inputs = {k: v.to(target_device) for k, v in inputs.items()}
        
        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
        
        generation_kwargs = dict(
            **inputs,
            streamer=streamer,
            max_new_tokens=max_tokens,
            temperature=temperature if temperature > 0 else 1.0,
            do_sample=temperature > 0,
            top_p=top_p,
            pad_token_id=self.tokenizer.eos_token_id
        )
        
        thread = Thread(target=self.model.generate, kwargs=generation_kwargs)
        thread.start()
        
        for new_text in streamer:
            yield {
                "token": new_text,
                "finish_reason": None,
                "layers_loaded": 1
            }
            await asyncio.sleep(0)
            
        yield {
            "token": "",
            "finish_reason": "stop"
        }
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage stats"""
        process = psutil.Process()
        return {
            "ram_used_gb": process.memory_info().rss / (1024**3),
            "layers_loaded": 1,
            "layer_memory_mb": 0,
            "kv_cache_mb": 0,
            "prefetch_stats": {}
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics"""
        return {
            **self.stats,
            "memory": self.get_memory_usage()
        }