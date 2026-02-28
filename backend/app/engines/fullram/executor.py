"""FullRAM Execution Engine"""
import asyncio
import time
from typing import Dict, Any, AsyncGenerator, Optional
import numpy as np

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer
from threading import Thread
import psutil

from app.engines.base import BaseEngine

class FullRAMEngine(BaseEngine):
    """Full RAM inference engine - loads entire model into memory using HuggingFace Transformers"""
    
    def __init__(self, model_path: str, hardware: Dict[str, Any], memory_manager: Any):
        super().__init__(model_path, hardware, memory_manager)
        self.mode = "fullram"
        self.loader = None
        self.tokenizer = None
        self.model = None
        self.model_config = {}
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
    
    async def load(self):
        """Load model into RAM"""
        start_time = time.time()
        
        # Load Hugging Face tokenizer and model
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_path, 
                trust_remote_code=True,
                local_files_only=True
            )
            
            # Find optimal settings for GPU vs CPU
            model_kwargs = {
                "trust_remote_code": True,
                "local_files_only": True,
                "low_cpu_mem_usage": True
            }
            
            if self.device == "cuda":
                model_kwargs["device_map"] = "auto"
                model_kwargs["torch_dtype"] = torch.float16
            else:
                model_kwargs["device_map"] = "cpu"
                model_kwargs["torch_dtype"] = torch.float32
                
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                **model_kwargs
            )
            
            if not self.tokenizer.pad_token:
                self.tokenizer.pad_token = self.tokenizer.eos_token
                
            self.loaded = True
            self.stats["load_time"] = time.time() - start_time
            print(f"Loaded {self.model_path} in Full RAM mode on {self.device} in {self.stats['load_time']:.1f}s")
        except Exception as e:
            self.loaded = False
            raise RuntimeError(f"Failed to load model: {e}")
    
    async def unload(self):
        """Unload model from RAM"""
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
        """Generate completion"""
        if not self.loaded:
            raise RuntimeError("Model not loaded")
        
        start_time = time.perf_counter()
        
        # Tokenize
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        prompt_tokens = inputs.input_ids.shape[1]
        
        # Run generation
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
            raise RuntimeError("Model not loaded")
            
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        
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
                "finish_reason": None
            }
            # Give back event loop control
            await asyncio.sleep(0)
            
        yield {
            "token": "",
            "finish_reason": "stop"
        }
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage"""
        process = psutil.Process()
        return {
            "ram_used_gb": process.memory_info().rss / (1024**3),
            "peak_ram_gb": process.memory_info().peak_wset / (1024**3) if hasattr(process.memory_info(), 'peak_wset') else 0,
            "kv_cache_mb": 0  # Managed by HF internally
        }