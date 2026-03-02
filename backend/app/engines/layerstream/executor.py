"""LayerStream Execution Engine - TRUE Memory-Bounded Layer-by-Layer inference"""
import asyncio
import time
import os
import gc
from typing import Dict, Any, AsyncGenerator, Optional

import torch
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
from accelerate import init_empty_weights

from app.engines.base import BaseEngine
from .introspection import ModelIntrospector
from .splitter import WeightSplitter
from .layer_executor import LayerExecutor
from .sampler import Sampler

class LayerStreamEngine(BaseEngine):
    """Refactored streaming engine: completely decoupling computation phases dynamically"""
    
    def __init__(self, model_path: str, hardware: Dict[str, Any], memory_manager: Any):
        super().__init__(model_path, hardware, memory_manager)
        self.mode = "layerstream"
        
        self.tokenizer = None
        self.model = None
        self.config = None
        self.components = {}
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        self.weights_dir = ""
        self.layer_executor = None

    async def load(self):
        """Prepare meta scaffolding"""
        start_time = time.time()
        
        self.weights_dir = os.path.join("offload_cache", os.path.basename(self.model_path.rstrip("/\\")))
        os.makedirs(self.weights_dir, exist_ok=True)
        
        if not os.path.exists(os.path.join(self.weights_dir, "embed.safetensors")):
            print(f"Components absents. Synchronizing AutoSplitter logic on cpu...")
            splitter = WeightSplitter(self.model_path, self.weights_dir)
            await asyncio.to_thread(splitter.split_and_save, torch.float16)

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True, local_files_only=True)
        except Exception:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)
            
        if not self.tokenizer.pad_token:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            
        self.config = AutoConfig.from_pretrained(self.weights_dir)
        
        with init_empty_weights():
            self.model = AutoModelForCausalLM.from_config(self.config)
            
        self.components = ModelIntrospector.detect_model_components(self.model)
        self.layer_executor = LayerExecutor(self.components, self.config, self.weights_dir, self.device)
        
        self.loaded = True
        self.stats["load_time"] = time.time() - start_time
        print(f"Loaded {self.model_path} LayerStream in {self.stats['load_time']:.1f}s")
    
    async def unload(self):
        """Garbage collection enforcement"""
        if self.model:
            del self.model
            self.model = None
        if self.tokenizer:
            del self.tokenizer
            self.tokenizer = None
        if self.layer_executor:
            self.layer_executor.loader.clear_cache()
            self.layer_executor.kv_manager.clear()
            self.layer_executor = None
        self.components = {}
        
        gc.collect()
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
        """Runs the two-phase computation engine independently maintaining context bounds"""
        if not self.loaded:
            raise RuntimeError("Engine not loaded")
            
        start_time = time.perf_counter()
        # Protect against async unloading race conditions
        tokenizer = self.tokenizer
        executor = self.layer_executor
        if not tokenizer or not executor:
            raise RuntimeError("Engine dependencies have been unloaded.")
            
        # Wipe residual memory structures safely
        executor.kv_manager.clear()
        
        inputs = tokenizer(prompt, return_tensors="pt")
        input_ids = inputs["input_ids"].to(self.device)
        prompt_tokens = input_ids.shape[1]
        generated_tokens = []
        
        def _gen_loop():
            with torch.inference_mode():
                # Phase 1: Context Prefill
                # Spools states and layers exclusively across CPU IO
                logits = executor.execute_forward(input_ids, mode="prefill")
                next_token = Sampler.sample(logits, temperature, top_p)
                generated_tokens.append(next_token.item())
                
                # Phase 2: Decoded Token Generation
                # Avoid disk IO exclusively polling RAM tensors onto active layer execution
                current_input = next_token
                for _ in range(max_tokens - 1):
                    if next_token.item() == tokenizer.eos_token_id:
                        break
                        
                    logits = executor.execute_forward(current_input, mode="decode")
                    next_token = Sampler.sample(logits, temperature, top_p)
                    generated_tokens.append(next_token.item())
                    current_input = next_token
                    
            return generated_tokens
            
        output_ids = await asyncio.to_thread(_gen_loop)
        
        output_text = tokenizer.decode(output_ids, skip_special_tokens=True)
        completion_tokens = len(output_ids)
        elapsed = time.perf_counter() - start_time
        
        stats = executor.tracker.get_stats()
        stats["tokens_per_second"] = completion_tokens / elapsed if elapsed > 0 else 0
        self.stats.update(stats)
        
        return {
            "text": output_text,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "time_seconds": elapsed,
            "tokens_per_second": stats["tokens_per_second"],
            "finish_reason": "stop"
        }

    async def generate_stream(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Provides async telemetry while unspooling context cleanly"""
        if not self.loaded:
            raise RuntimeError("Engine not loaded")
            
        tokenizer = self.tokenizer
        executor = self.layer_executor
        if not tokenizer or not executor:
            url = "Engine dependencies have been unloaded."
            yield {"token": "", "finish_reason": "error"}
            return
            
        executor.kv_manager.clear()
        inputs = tokenizer(prompt, return_tensors="pt")
        input_ids = inputs["input_ids"].to(self.device)
        
        with torch.inference_mode():
            # Initial prompt flush
            logits = await asyncio.to_thread(executor.execute_forward, input_ids, mode="prefill")
            next_token = Sampler.sample(logits, temperature, top_p)
            token_text = tokenizer.decode([next_token.item()], skip_special_tokens=True)
            
            yield {
                "token": token_text,
                "finish_reason": None,
                "layers_loaded": executor.num_layers
            }
            
            current_input = next_token
            for _ in range(max_tokens - 1):
                if not self.tokenizer or not self.layer_executor:
                    break   # Stop generation cleanly if engine gets unloaded externally
                    
                if next_token.item() == tokenizer.eos_token_id:
                    break
                    
                logits = await asyncio.to_thread(executor.execute_forward, current_input, mode="decode")
                next_token = Sampler.sample(logits, temperature, top_p)
                token_text = tokenizer.decode([next_token.item()], skip_special_tokens=True)
                
                yield {
                    "token": token_text,
                    "finish_reason": None,
                    "layers_loaded": executor.num_layers
                }
                current_input = next_token
                
        yield {
            "token": "",
            "finish_reason": "stop"
        }

    def get_memory_usage(self) -> Dict[str, Any]:
        if self.layer_executor:
            stats = self.layer_executor.tracker.get_stats()
            return {
                "ram_used_gb": stats["peak_ram_mb"] / 1024,
                "layers_loaded": self.layer_executor.num_layers,
                "layer_memory_mb": 0,
                "kv_cache_mb": stats["kv_cache_size_mb"],
                "peak_vram_mb": stats["peak_vram_mb"]
            }
        return {}
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            **self.stats,
            "memory": self.get_memory_usage()
        }