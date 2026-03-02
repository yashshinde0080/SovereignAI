"""
Layer-by-Layer Streaming Inference for AutoModelForCausalLM.
Implements memory-efficient layer-by-layer inference where only ONE transformer
block resides on GPU at a time, along with layer fetching with asynchronous disk IO.
"""

import os
import time
import json
import gc
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, Tuple

import torch
import torch.nn as nn
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
from transformers.cache_utils import DynamicCache
from accelerate import init_empty_weights
from safetensors.torch import save_file, load_file

# --------------------------------------------------------
# 1. MODEL INTROSPECTION
# --------------------------------------------------------

class ModelIntrospector:
    @staticmethod
    def detect_model_components(model: nn.Module) -> Dict[str, Any]:
        """
        Dynamically detects core components of any AutoModelForCausalLM structure.
        Returns embed, layers, norm, lm_head.
        """
        components = {}
        
        # 1. LM Head
        if hasattr(model, 'get_output_embeddings'):
            components['lm_head'] = model.get_output_embeddings()
        elif hasattr(model, 'lm_head'):
            components['lm_head'] = model.lm_head
        else:
            # Fallback for LM Head: usually the last linear layer
            linears = [m for m in model.modules() if isinstance(m, nn.Linear)]
            if linears:
                components['lm_head'] = linears[-1]
            
        base_model = getattr(model, model.base_model_prefix, model)
        
        # 2. Embedding Layer
        if hasattr(base_model, 'get_input_embeddings'):
            components['embed'] = base_model.get_input_embeddings()
        else:
            # Fallback for Embedding
            embeds = [m for m in base_model.modules() if isinstance(m, nn.Embedding)]
            if embeds:
                components['embed'] = embeds[0]
            
        # 3. Transformer Layers
        module_lists = [m for m in base_model.modules() if isinstance(m, nn.ModuleList)]
        if module_lists:
            # The transformer layers are typically the longest ModuleList
            longest_list = max(module_lists, key=lambda x: len(x))
            components['layers'] = longest_list
        else:
            raise ValueError("Could not dynamically detect transformer layers (nn.ModuleList).")
        
        # 4. Final Norm Layer
        for name, module in base_model.named_children():
            if 'norm' in name.lower() or 'ln_f' in name.lower():
                components['norm'] = module
                break
                
        if 'norm' not in components:
            norms = [m for m in base_model.modules() if 'norm' in m.__class__.__name__.lower()]
            if norms:
                components['norm'] = norms[-1]
            else:
                components['norm'] = None # Some models may not have a final norm
                
        # Validate existence
        if 'embed' not in components or components['embed'] is None:
            raise ValueError("Could not dynamically detect Embedding layer.")
        if 'lm_head' not in components or components['lm_head'] is None:
            raise ValueError("Could not dynamically detect LM head.")
            
        return components


# --------------------------------------------------------
# 2. PRE-SPLIT WEIGHTS
# --------------------------------------------------------

class WeightSplitter:
    def __init__(self, model_id: str, output_dir: str = "layers"):
        self.model_id = model_id
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def split_and_save(self, dtype=torch.float16):
        """
        Loads the full model into CPU RAM precisely once and saves the core components
        into separate safetensors files.
        """
        print(f"Loading full model '{self.model_id}' to CPU for splitting...")
        # Load full model to CPU
        model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            device_map="cpu",
            torch_dtype=dtype,
            low_cpu_mem_usage=True
        )
        
        components = ModelIntrospector.detect_model_components(model)
        
        print("Saving embed...")
        save_file(components['embed'].state_dict(), os.path.join(self.output_dir, "embed.safetensors"))
        
        print(f"Saving {len(components['layers'])} layers...")
        for i, layer in enumerate(components['layers']):
            save_file(layer.state_dict(), os.path.join(self.output_dir, f"layer_{i}.safetensors"))
            
        if components['norm'] is not None:
            print("Saving final norm...")
            save_file(components['norm'].state_dict(), os.path.join(self.output_dir, "norm.safetensors"))
            
        print("Saving lm_head...")
        save_file(components['lm_head'].state_dict(), os.path.join(self.output_dir, "lm_head.safetensors"))
        
        # Save config
        model.config.save_pretrained(self.output_dir)
        
        # Clean up full model from RAM
        del model
        gc.collect()
        print(f"Splitting complete. Files saved to {self.output_dir}/")


# --------------------------------------------------------
# 3. MEMORY MANAGER & ASYNC PREFETCH
# --------------------------------------------------------

class MemoryManager:
    def __init__(self, device: str = "cuda"):
        self.device = torch.device(device)
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.prefetch_future = None

    def load_state_dict_async(self, path: str):
        """Asynchronous disk IO to overlap with compute."""
        if not os.path.exists(path):
            return
        self.prefetch_future = self.executor.submit(load_file, path, str(self.device))

    def get_prefetched_state_dict(self, fallback_path: str = None) -> Dict[str, torch.Tensor]:
        """Wait for and return the prefetched tensor dict."""
        if self.prefetch_future:
            result = self.prefetch_future.result()
            self.prefetch_future = None
            return result
        elif fallback_path and os.path.exists(fallback_path):
            return load_file(fallback_path, str(self.device))
        return None

    def assign_module_weights(self, module: nn.Module, state_dict: Dict[str, torch.Tensor]):
        """Zero-copy assignment of parameters to empty meta module."""
        if state_dict is None:
            return
        # assign=True requires PyTorch 2.1+ and Replaces parameters with tensors
        module.load_state_dict(state_dict, strict=False, assign=True)
        # Ensure buffers (like causal masks, rotary embeddings) are correctly instantiated on device
        for name, buf in module.named_buffers():
            if buf is not None and buf.device.type == 'meta':
                # Recreate meta buffers directly on target device with zero
                if buf.dtype in [torch.int, torch.long, torch.bool]:
                    module._buffers[name] = torch.zeros_like(buf, device=self.device)
                else:
                    module._buffers[name] = torch.zeros_like(buf, device=self.device, dtype=torch.float16)

    def offload_module(self, module: nn.Module):
        """Free GPU memory by replacing dense parameters with empty CPU tensors."""
        for name, param in module.named_parameters():
             module._parameters[name] = nn.Parameter(torch.empty(0, device="cpu", dtype=param.dtype))
        for name, buf in module.named_buffers():
             if buf is not None:
                 module._buffers[name] = torch.empty(0, device="cpu", dtype=buf.dtype)
        # Free CUDA memory allocator blocks
        torch.cuda.empty_cache()


# --------------------------------------------------------
# 4. KV CACHE STRATEGY
# --------------------------------------------------------

class CPUOffloadedCache(DynamicCache):
    """
    Seamlessly integrates with HuggingFace layers to keep KV pairs on CPU.
    Tensors move to GPU only during layer execution.
    """
    def __init__(self):
        super().__init__()
        # PyTorch lists tracking CPU tensors internally
        self.key_cache = []
        self.value_cache = []

    def update(
        self,
        key_states: torch.Tensor,
        value_states: torch.Tensor,
        layer_idx: int,
        cache_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Receives new keys/values on GPU from self-attention block,
        concatenates them to CPU history, and returns full history on GPU.
        """
        if len(self.key_cache) <= layer_idx:
            # First token
            self.key_cache.append(key_states.detach().cpu())
            self.value_cache.append(value_states.detach().cpu())
        else:
            # Subsequent tokens: cat on CPU
            self.key_cache[layer_idx] = torch.cat(
                [self.key_cache[layer_idx], key_states.detach().cpu()], dim=-2
            )
            self.value_cache[layer_idx] = torch.cat(
                [self.value_cache[layer_idx], value_states.detach().cpu()], dim=-2
            )
            
        # Return concatenated cache on GPU for the layer to perform attention
        return (
            self.key_cache[layer_idx].to(key_states.device),
            self.value_cache[layer_idx].to(value_states.device)
        )

    def get_seq_length(self, layer_idx: int = 0) -> int:
        if len(self.key_cache) <= layer_idx:
            return 0
        return self.key_cache[layer_idx].shape[-2]
        
    def get_max_length(self) -> Optional[int]:
        return None

# --------------------------------------------------------
# 5. RUNTIME ENGINE & TOKEN GENERATION
# --------------------------------------------------------

class LayerByLayerEngine:
    def __init__(self, config_dir: str, weights_dir: str = "layers", device: str = "cuda"):
        self.device = torch.device(device)
        self.weights_dir = weights_dir
        
        self.config = AutoConfig.from_pretrained(config_dir)
        
        # Initialize bare-bones architecture on the 'meta' device consuming 0 memory
        with init_empty_weights():
            self.model = AutoModelForCausalLM.from_config(self.config)
            
        self.components = ModelIntrospector.detect_model_components(self.model)
        self.num_layers = len(self.components['layers'])
        
        # Paths verification
        self.layer_paths = [os.path.join(weights_dir, f"layer_{i}.safetensors") for i in range(self.num_layers)]
        self.embed_path = os.path.join(weights_dir, "embed.safetensors")
        self.norm_path = os.path.join(weights_dir, "norm.safetensors")
        self.lm_head_path = os.path.join(weights_dir, "lm_head.safetensors")
        
        self.memory_manager = MemoryManager(device)
        self.cpu_cache = CPUOffloadedCache()
        
    def manual_forward_pass(self, input_ids: torch.Tensor) -> torch.Tensor:
        """
        Executes a true layer-by-layer forward pass.
        No `model.generate()` or `model(input_ids)` calls. Everything is explicit.
        """
        batch_size, seq_length = input_ids.shape
        past_length = self.cpu_cache.get_seq_length() if getattr(self.cpu_cache, 'get_seq_length', None) else 0
        
        # 1. Load Embeddings to GPU
        embed = self.components['embed']
        self.memory_manager.assign_module_weights(embed, self.memory_manager.get_prefetched_state_dict(self.embed_path))
        hidden_states = embed(input_ids)
        self.memory_manager.offload_module(embed)
        
        # Wait for any IO tasks to clear
        torch.cuda.synchronize()
        
        # Construct kwargs standard for transformer blocks (AutoModelForCausalLM abstraction)
        # Position IDs (RoPE needs absolute positions spanning [past_length, past_length + seq_length])
        position_ids = torch.arange(
            past_length, past_length + seq_length, dtype=torch.long, device=self.device
        ).unsqueeze(0)
        
        # Standard causal mask / attention mask 
        attention_mask = torch.ones(
            (batch_size, past_length + seq_length), dtype=torch.long, device=self.device
        )
        
        # Most layers accept position_ids, attention_mask, past_key_value, use_cache
        layer_kwargs = {
            "position_ids": position_ids,
            "attention_mask": attention_mask,
            "use_cache": True,
            "past_key_value": self.cpu_cache
        }

        # Handle specific edge cases in kwargs
        if "llama" in self.config.model_type or "mistral" in self.config.model_type or "qwen" in self.config.model_type:
             if seq_length > 1:
                 # Standard causal mask for prompt execution
                 causal_mask = torch.tril(torch.ones((seq_length, seq_length), device=self.device))
                 causal_mask = causal_mask[None, None, :, :].expand(batch_size, 1, seq_length, seq_length)
                 # Add past length zeros
                 if past_length > 0:
                     causal_mask = torch.cat([torch.ones(batch_size, 1, seq_length, past_length, device=self.device), causal_mask], dim=-1)
                 causal_mask = (1.0 - causal_mask) * torch.finfo(hidden_states.dtype).min
                 layer_kwargs["attention_mask"] = causal_mask
             elif seq_length == 1:
                 # Generation step causal mask
                 layer_kwargs["attention_mask"] = torch.zeros((batch_size, 1, 1, past_length + 1), device=self.device)

        # 2. Transformer Layer Loop
        for i, layer in enumerate(self.components['layers']):
            # Fetch layer 'i' weights (waits for async loading if initiated)
            state_dict = self.memory_manager.get_prefetched_state_dict(self.layer_paths[i])
            self.memory_manager.assign_module_weights(layer, state_dict)
            
            # Initiate async prefetch of layer 'i+1'
            next_idx = i + 1
            if next_idx < self.num_layers:
                self.memory_manager.load_state_dict_async(self.layer_paths[next_idx])
                
            # Forward pass inner
            try:
                layer_outputs = layer(hidden_states, **layer_kwargs)
            except TypeError as te:
                # Fallback if position_ids or other kwargs are rejected by layer signature
                # E.g., older model layers (GPT-2 style) taking just hidden_states & attention_mask
                if "position_ids" in str(te):
                    del layer_kwargs["position_ids"]
                    layer_outputs = layer(hidden_states, **layer_kwargs)
                else:
                    raise te
                    
            # Extract new hidden states. KV cache is auto-updated internally by CPUOffloadedCache.
            hidden_states = layer_outputs[0]
            
            # Offload layer 'i' & drop GPU tensors
            self.memory_manager.offload_module(layer)

        # 3. Final Norm
        norm = self.components['norm']
        if norm is not None:
            self.memory_manager.assign_module_weights(norm, self.memory_manager.get_prefetched_state_dict(self.norm_path))
            hidden_states = norm(hidden_states)
            self.memory_manager.offload_module(norm)
            
        # 4. LM Head (Compute Logits)
        lm_head = self.components['lm_head']
        self.memory_manager.assign_module_weights(lm_head, self.memory_manager.get_prefetched_state_dict(self.lm_head_path))
        
        # We only need logits for the last token in the sequence
        last_hidden_state = hidden_states[:, -1:, :]
        logits = lm_head(last_hidden_state)
        
        self.memory_manager.offload_module(lm_head)
        
        return logits

    @torch.inference_mode()
    def generate(self, input_ids: torch.Tensor, max_new_tokens: int = 20, temperature: float = 0.0, top_p: float = 1.0):
        """
        Token generation loop.
        Supports greedy decoding (temperature=0.0) or sampling (temperature>0, top_p).
        """
        self.cpu_cache = CPUOffloadedCache()
        generated_tokens = []
        
        # Initial context processing (Prompt) - executed entirely through layer-by-layer
        print(f"Processing prompt of length {input_ids.shape[-1]}...")
        logits = self.manual_forward_pass(input_ids)
        next_token = self._sample(logits, temperature, top_p)
        generated_tokens.append(next_token.item())
        
        # Give generation a stream output
        print(f"Gen: {next_token.item()} ", end="", flush=True)
        
        # Stream Generation
        current_input = next_token
        
        for step in range(max_new_tokens - 1):
            logits = self.manual_forward_pass(current_input)
            next_token = self._sample(logits, temperature, top_p)
            generated_tokens.append(next_token.item())
            
            print(f"{next_token.item()} ", end="", flush=True)
            current_input = next_token

        print()
        return generated_tokens

    def _sample(self, logits: torch.Tensor, temperature: float, top_p: float) -> torch.Tensor:
        """Helper for Greedy and Nucleus (top_p) Sampling"""
        logits = logits[:, -1, :]  # Shape: [batch_size, vocab_size]
        
        if temperature == 0.0:
            # Greedy Decode
            return torch.argmax(logits, dim=-1).unsqueeze(0)
            
        # Apply temperature
        logits = logits / temperature
        
        # Top-p (nucleus filtering)
        if top_p < 1.0:
            sorted_logits, sorted_indices = torch.sort(logits, descending=True)
            cumulative_probs = torch.cumsum(torch.softmax(sorted_logits, dim=-1), dim=-1)
            
            # Remove tokens with cumulative probability above the threshold
            sorted_indices_to_remove = cumulative_probs > top_p
            # Shift the indices to the right to keep also the first token above the threshold
            sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
            sorted_indices_to_remove[..., 0] = 0

            indices_to_remove = sorted_indices_to_remove.scatter(1, sorted_indices, sorted_indices_to_remove)
            logits[indices_to_remove] = float('-inf')

        # Sample from the filtered distribution
        probs = torch.softmax(logits, dim=-1)
        next_token = torch.multinomial(probs, num_samples=1)
        return next_token


# --------------------------------------------------------
# 8. BENCHMARKING
# --------------------------------------------------------

def benchmark(model_dir: str, weights_dir: str = "layers", max_tokens: int = 10):
    """
    Executes and benchmarks memory patterns and tokens per second.
    """
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
    
    print("--- BENCHMARK ---")
    
    start_time = time.time()
    
    engine = LayerByLayerEngine(config_dir=model_dir, weights_dir=weights_dir, device="cpu" if not torch.cuda.is_available() else "cuda")
    
    # Dummy prompt (5 tokens)
    input_ids = torch.tensor([[1, 2, 3, 4, 5]], device="cpu" if not torch.cuda.is_available() else "cuda")
    
    print("Starting generation...")
    gen_start = time.time()
    generated = engine.generate(input_ids, max_new_tokens=max_tokens, temperature=0.7, top_p=0.9)
    gen_time = time.time() - gen_start
    
    peak_mem = torch.cuda.max_memory_allocated() / (1024 ** 2) if torch.cuda.is_available() else 0
    current_mem = torch.cuda.memory_allocated() / (1024 ** 2) if torch.cuda.is_available() else 0
    
    print("--- METRICS ---")
    print(f"Total time: {time.time() - start_time:.2f}s")
    print(f"Generation time: {gen_time:.2f}s")
    print(f"Tokens/sec: {max_tokens / gen_time:.2f}")
    print(f"Peak GPU Memory: {peak_mem:.2f} MB")
    print(f"Tear-down GPU Memory: {current_mem:.2f} MB")
    print(f"Tokens generated: {generated}")


# --------------------------------------------------------
# HOW TO RUN
# --------------------------------------------------------
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Layer-by-Layer Streaming Inference")
    parser.add_argument("--model", type=str, required=True, help="HF model id or local path")
    parser.add_argument("--split", action="store_true", help="Split model into separate safetensors before running")
    parser.add_argument("--layer_dir", type=str, default="layers", help="Directory where layers are stored")
    parser.add_argument("--tokens", type=int, default=10, help="Number of tokens to generate")
    
    args = parser.parse_args()
    
    if args.split:
        splitter = WeightSplitter(model_id=args.model, output_dir=args.layer_dir)
        splitter.split_and_save()
        
    benchmark(model_dir=args.model if not args.split else args.layer_dir, 
              weights_dir=args.layer_dir, 
              max_tokens=args.tokens)
