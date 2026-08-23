import os
import time
import inspect
import torch
import torch.nn as nn
from typing import Dict, Any, List, Optional

from .loader import LayerWeightLoader, dequantize_on_device
from .kv_cache import KVCacheManager, HFProxyCache, StatefulCache
from .benchmark import BenchmarkTracker


def _cpu_bf16_capable() -> bool:
    """True only where torch's bf16 matmul is native (AVX512-BF16/AMX).

    On AVX2, bf16 is emulated by torch and measured ~160x slower than fp32
    (245ms vs 1.5ms per 1024x1024 matmul), so it must be gated on capability
    rather than enabled by default.
    """
    try:
        return bool(torch.backends.cpu.is_bf16_supported())
    except Exception:
        # older torch: no is_bf16_supported; fall back to the capability string
        try:
            return torch.backends.cpu.get_cpu_capability() in ("avx512_bf16", "amx")
        except Exception:
            return False


def _compute_dtype_for(device: torch.device) -> torch.dtype:
    """Pick the compute dtype: fp16 on CUDA, bf16 on capable CPUs, fp32 else."""
    if device.type == "cuda":
        return torch.float16
    return torch.bfloat16 if _cpu_bf16_capable() else torch.float32

class LayerExecutor:
    """Orchestrates IO, KV, and isolated GPU forward passes safely."""
    def __init__(self, components: Dict[str, Any], config: Any, weights_dir: str, device: str,
                 turboquant_config: Optional[dict] = None, layer_types: Optional[list] = None,
                 prefetch_depth: int = 3, cache_budget_mb: Optional[float] = None):
        self.components = components
        self.config = config
        self.weights_dir = weights_dir
        self.device = torch.device(device)
        self.num_layers = len(components['layers'])

        self.compute_dtype = _compute_dtype_for(self.device)

        self.layer_paths = [os.path.join(weights_dir, f"layer_{i}.safetensors") for i in range(self.num_layers)]
        self.embed_path = os.path.join(weights_dir, "embed.safetensors")
        self.norm_path = os.path.join(weights_dir, "norm.safetensors")
        self.lm_head_path = os.path.join(weights_dir, "lm_head.safetensors")

        # Snapshot of each component's true parameter shapes, taken from the
        # meta model (init_empty_weights) before any offload runs. offload_weights
        # replaces params with torch.empty(0), so on later passes param.shape is
        # degenerate — dequantize_on_device needs the real shape as its reshape
        # target (int4 restores padding/1-D vs 2-D from it).
        self._param_shapes: Dict[int, Dict[str, tuple]] = {}
        for comp in [components.get("embed"), components.get("norm"), components.get("lm_head")] + list(components.get("layers", [])):
            if comp is not None:
                shapes = {n: tuple(p.shape) for n, p in comp.named_parameters()}
                shapes.update({n: tuple(b.shape) for n, b in comp.named_buffers()})
                self._param_shapes[id(comp)] = shapes

        # Pinned = tiny, used every pass: never evicted from the loader cache.
        pinned = {self.embed_path, self.norm_path, self.lm_head_path}
        self.loader = LayerWeightLoader(
            weights_dir,
            prefetch_depth=prefetch_depth,
            cache_budget_mb=cache_budget_mb,
            pinned_paths=pinned,
        )
        self._mask_cache = {}
        self.tracker = BenchmarkTracker()

        # Device cache: dequantized (compute-dtype) tensors per component path,
        # bounded LRU in VRAM. The CPU loader cache holds the small packed form;
        # this holds the fp16 form the forward pass actually uses, so decode
        # steps after the first pass skip the per-token re-dequantization that
        # measured ~68% of decode wall time. Budget = half of free VRAM at init:
        # small models cache fully, big models hold a recency window.
        # ponytail: fixed 50%-of-free heuristic; add a settings knob if VRAM
        # contention ever shows up.
        self._dev_cache: Dict[str, Dict[str, torch.Tensor]] = {}
        self._dev_sizes: Dict[str, int] = {}
        self._dev_lru: Dict[str, float] = {}
        self._dev_bytes = 0
        if self.device.type == "cuda":
            free_vram, _ = torch.cuda.mem_get_info()
            self.dev_cache_budget = int(free_vram * 0.5)
        else:
            self.dev_cache_budget = 0

        # Detect hybrid/stateful models (e.g. Qwen3.5 with linear_attention + full_attention)
        # layer_types is passed from executor.py which checks both full config and text_config
        if layer_types is None:
            layer_types = getattr(config, 'layer_types', None)
        self._is_hybrid = layer_types is not None and 'linear_attention' in layer_types

        # TurboQuant or standard KV cache
        self.turboquant_config = turboquant_config
        if self._is_hybrid:
            # Hybrid models use StatefulCache that lives on GPU — handles both
            # full_attention (key_cache/value_cache) and linear_attention (conv_states/recurrent_states)
            self.cache = StatefulCache(config=config, num_layers=self.num_layers, layer_types=layer_types)
            self.kv_manager = None
            if turboquant_config is not None:
                print("TurboQuant skipped: hybrid/stateful model uses StatefulCache instead")
            self._hf_cache_factory = lambda: self.cache
        elif turboquant_config is not None:
            from app.engines.shared.turboquant import TurboQuantKVCacheManager, TurboQuantHFProxyCache
            tq_config = turboquant_config if hasattr(turboquant_config, 'bits_per_coord') else type('obj', (object,), {'bits_per_coord': 3.5, 'qjl_dim': 128, 'enable_qjl': True, 'device': device})()
            # Use config object
            from app.engines.shared.turboquant import TurboQuantConfig
            if isinstance(turboquant_config, dict):
                tq_cfg = TurboQuantConfig(**turboquant_config)
            else:
                tq_cfg = turboquant_config
            tq_cfg.device = device
            head_dim = config.hidden_size // config.num_attention_heads
            self.kv_manager = TurboQuantKVCacheManager(
                config=tq_cfg,
                num_layers=self.num_layers,
                num_heads=config.num_attention_heads,
                head_dim=head_dim,
                device=device
            )
            self._hf_cache_factory = lambda: TurboQuantHFProxyCache(self.kv_manager)
        else:
            self.kv_manager = KVCacheManager()
            self._hf_cache_factory = lambda: HFProxyCache(self.kv_manager)
    
    def _create_attention_mask(self, input_shape: tuple, past_length: int, dtype: torch.dtype) -> torch.Tensor:
        """Architecture-aware attention mask mapping (cached per shape).

        The mask only depends on (batch, seq, past_length, dtype), so repeated
        identical shapes across generate() calls (same prompt length, or a
        prefill repeated after a context reset) hit the cache instead of
        rebuilding. Bounded at 64 shapes; decode's past_length grows per token,
        so the cache is capped rather than allowed to track a full context.
        """
        key = (input_shape, past_length, str(dtype))
        cached = self._mask_cache.get(key)
        if cached is not None:
            return cached

        batch_size, seq_length = input_shape
        mask = torch.full((batch_size, 1, seq_length, seq_length + past_length), torch.finfo(dtype).min, device=self.device)
        
        causal_mask = torch.tril(torch.ones((seq_length, seq_length), device=self.device))
        if past_length > 0:
            past_mask = torch.ones((seq_length, past_length), device=self.device)
            full_mask = torch.cat([past_mask, causal_mask], dim=-1)
        else:
            full_mask = causal_mask
            
        full_mask = full_mask.unsqueeze(0).unsqueeze(0).expand(batch_size, 1, seq_length, seq_length + past_length)
        mask = torch.where(full_mask == 1.0, torch.tensor(0.0, device=self.device, dtype=dtype), mask)
        if len(self._mask_cache) > 64:
            self._mask_cache.clear()  # bounded: decode grows past_length per token
        self._mask_cache[key] = mask
        return mask

    def _device_tensors(self, module: nn.Module, state_dict: dict) -> Dict[str, torch.Tensor]:
        """Dequantize/copy params to the compute device; returns {name: tensor}.

        Quantized weights (int8/int4, detected by a matching ``<name>.scale``
        entry) are dequantized on the compute device, so RAM/disk hold the
        small form and the device pays the conversion. fp16/fp32 pass through
        unchanged. non_blocking=True overlaps the copy with the next disk read.
        """
        shapes = self._param_shapes.get(id(module), {})
        tensors = {}
        for name, param in module.named_parameters():
            if name not in state_dict:
                continue
            scale = state_dict.get(f"{name}.scale")
            if scale is not None:
                tensors[name] = dequantize_on_device(
                    state_dict[name], scale, self.device, self.compute_dtype,
                    shapes.get(name) or tuple(param.shape))
            else:
                tensors[name] = state_dict[name].to(self.device, dtype=self.compute_dtype, non_blocking=True)
        return tensors

    def _materialize_buffers(self, module: nn.Module, state_dict: dict):
        """Assign buffers from state_dict, or materialize meta buffers (RoPE etc)."""
        shapes = self._param_shapes.get(id(module), {})
        for name, buf in module.named_buffers():
            parts = name.split('.')
            parent = module
            for part in parts[:-1]:
                parent = getattr(parent, part)
            attr = parts[-1]

            if name in state_dict:
                scale = state_dict.get(f"{name}.scale")
                if scale is not None:
                    dev_tensor = dequantize_on_device(
                        state_dict[name], scale, self.device, self.compute_dtype,
                        shapes.get(name) or tuple(buf.shape))
                else:
                    dev_tensor = state_dict[name].to(self.device, non_blocking=True)
                parent._buffers[attr] = dev_tensor
            elif buf is not None and buf.device.type == 'meta':
                # Handle RoPE and other buffers specifically for CUDA/vGPU
                if "inv_freq" in attr:
                    dim = buf.shape[0] * 2
                    base = getattr(self.config, "rope_theta", 10000.0)
                    inv_freq = 1.0 / (base ** (torch.arange(0, dim, 2, dtype=torch.float32, device=self.device) / dim))
                    parent._buffers[attr] = inv_freq
                else:
                    if getattr(buf, 'dtype', None) in [torch.int, torch.long, torch.bool]:
                        parent._buffers[attr] = torch.zeros_like(buf, device=self.device)
                    else:
                        parent._buffers[attr] = torch.zeros_like(buf, device=self.device, dtype=self.compute_dtype)

    def _dev_tensors_for(self, path: str, module: nn.Module, state_dict: dict):
        """Device tensors for ``path``: cache hit, or dequantize + store.

        Returns (tensors, state_dict). On a hit the state_dict is skipped
        entirely (buffers re-materialize from meta) so the per-token
        re-dequantization hot path never touches the packed form.
        """
        hit = self._dev_cache.get(path)
        if hit is not None:
            self._dev_lru[path] = time.monotonic()
            return hit, {}
        tensors = self._device_tensors(module, state_dict)
        if self.dev_cache_budget:
            self._store_dev(path, tensors)
        return tensors, state_dict

    def _store_dev(self, path: str, tensors: Dict[str, torch.Tensor]):
        """Store tensors in the bounded VRAM LRU, evicting least-recently-used."""
        size = sum(t.numel() * t.element_size() for t in tensors.values())
        if size > self.dev_cache_budget:
            return  # single component bigger than the whole budget: don't cache
        while self._dev_bytes + size > self.dev_cache_budget and self._dev_cache:
            lru_path = min(self._dev_lru, key=lambda p: self._dev_lru.get(p, 0.0))
            self._dev_bytes -= self._dev_sizes.pop(lru_path)
            self._dev_cache.pop(lru_path, None)
            self._dev_lru.pop(lru_path, None)
        self._dev_cache[path] = tensors
        self._dev_sizes[path] = size
        self._dev_lru[path] = time.monotonic()
        self._dev_bytes += size

    def assign_weights(self, module: nn.Module, state_dict: dict, tensors: Optional[Dict[str, torch.Tensor]] = None):
        """Ultra-fast weight assignment with vGPU/CUDA awareness.

        ``tensors`` (pre-dequantized device tensors, e.g. from the device
        cache) is used when provided; otherwise params are dequantized/copied
        here. Buffers are always materialized from ``state_dict`` (or meta).
        """
        if tensors is None:
            tensors = self._device_tensors(module, state_dict)
        for name, dev_tensor in tensors.items():
            parts = name.split('.')
            parent = module
            for part in parts[:-1]:
                parent = getattr(parent, part)
            attr = parts[-1]
            parent._parameters[attr] = nn.Parameter(dev_tensor, requires_grad=False)
        self._materialize_buffers(module, state_dict)

    def clear_device_cache(self):
        """Free all dequantized device tensors."""
        self._dev_cache.clear()
        self._dev_sizes.clear()
        self._dev_lru.clear()
        self._dev_bytes = 0

    def offload_weights(self, module: nn.Module):
        """Immediately destroys dense parameters to isolate VRAM peak values."""
        for name, param in module.named_parameters():
            parts = name.split('.')
            parent = module
            for part in parts[:-1]:
                parent = getattr(parent, part)
            attr = parts[-1]
            parent._parameters[attr] = nn.Parameter(torch.empty(0, device="cpu", dtype=param.dtype), requires_grad=False)
            
        for name, buf in module.named_buffers():
            if buf is not None and buf.numel() > 1000:
                parts = name.split('.')
                parent = module
                for part in parts[:-1]:
                    parent = getattr(parent, part)
                attr = parts[-1]
                parent._buffers[attr] = torch.empty(0, device="cpu", dtype=buf.dtype)

    def execute_forward(self, input_ids: torch.Tensor, mode: str = "decode") -> torch.Tensor:
        """Executes full discrete unspooling: modes are prefill / decode."""
        compute_start = time.perf_counter()
        batch_size, seq_length = input_ids.shape

        if self._is_hybrid:
            past_length = self.cache.get_seq_length(0)
        else:
            past_length = 0 if mode == "prefill" else self.kv_manager.get_seq_length(0)
            
        max_context = getattr(self.config, "max_position_embeddings", 4096)
        if past_length + seq_length > max_context:
            raise ValueError(f"Context length limits exceeded. Try generating fewer tokens.")
        
        t0 = time.perf_counter()
        embed = self.components['embed']
        embed_dict = self.loader.get_weights(self.embed_path)
        self.tracker.record_layer_load(time.perf_counter() - t0)
        embed_tensors, embed_dict = self._dev_tensors_for(self.embed_path, embed, embed_dict)
        self.assign_weights(embed, embed_dict, tensors=embed_tensors)
        hidden_states = embed(input_ids)
        self.offload_weights(embed)
        
        # Removed aggressive CUDA sync/empty_cache here for speed.
        # The allocator handles fragmentation naturally.

        position_ids = torch.arange(past_length, past_length + seq_length, dtype=torch.long, device=self.device).unsqueeze(0)
        cache_position = torch.arange(past_length, past_length + seq_length, dtype=torch.long, device=self.device)
        attention_mask = self._create_attention_mask((batch_size, seq_length), past_length, hidden_states.dtype)
        
        # Pre-compute RoPE if required by newer transformers
        position_embeddings = None
        rotary_emb = self.components.get("rotary_emb")
        if rotary_emb is not None:
             # Ensure rotary_emb buffers are in the right place. Buffers arrive
             # meta (init_empty_weights) and .to() on a meta tensor raises
             # ("Cannot copy out of meta tensor"), so materialize inv_freq from
             # rope_theta first — same formula as assign_weights' meta-buffer
             # branch.
             if (getattr(rotary_emb, "inv_freq", None) is not None
                     and rotary_emb.inv_freq.device.type == "meta"):
                 dim = rotary_emb.inv_freq.shape[0] * 2
                 base = getattr(self.config, "rope_theta", 10000.0)
                 rotary_emb.inv_freq = 1.0 / (base ** (torch.arange(0, dim, 2, dtype=torch.float32, device=self.device) / dim))
             rotary_emb.to(self.device)
             # Modern transformers expect (cos, sin) tuple
             # Note: Some architectures differ, but this is the standard for Qwen2/Llama3
             res = rotary_emb(hidden_states, position_ids)
             if isinstance(res, tuple):
                 # Return (cos, sin) as-is from the rotary_emb module.
                 # Modern transformers (4.46+) expect these to be broadcastable 
                 # to (batch, num_heads, seq, head_dim).
                 # Standard Qwen2RotaryEmbedding returns (batch, seq, head_dim).
                 position_embeddings = res
             else:
                 position_embeddings = res
        
        if self._is_hybrid:
            hf_cache = self.cache
        else:
            hf_cache = self._hf_cache_factory()

        # Main layer loop
        for i, layer in enumerate(self.components['layers']):
            t0 = time.perf_counter()
            # Prefetch prefetch_depth layers ahead so the disk stays saturated
            # while the GPU/CPU computes the current layer. This overlap is
            # what hides disk I/O behind compute (measured: wall ~= compute,
            # disk read ~9% of wall). PARKED (2026-08-16): deeper prefetch,
            # batched reads, GDS/io_uring are second-order until compute stops
            # dominating — triggers in reviews/parked-io-fixes-2026-08-16.md.
            for d in range(1, self.loader.prefetch_depth + 1):
                next_idx = i + d
                if next_idx < self.num_layers:
                    self.loader.prefetch_async(self.layer_paths[next_idx])
            
            layer_dict = self.loader.get_weights(self.layer_paths[i])
            self.tracker.record_layer_load(time.perf_counter() - t0)
            tensors, layer_dict = self._dev_tensors_for(self.layer_paths[i], layer, layer_dict)
            self.assign_weights(layer, layer_dict, tensors=tensors)
            
            # Dynamic introspective signature dispatching
            sig = inspect.signature(layer.forward)
            kwargs = {}
            if "position_ids" in sig.parameters:
                kwargs["position_ids"] = position_ids
            if "attention_mask" in sig.parameters:
                kwargs["attention_mask"] = attention_mask
            
            if "use_cache" in sig.parameters:
                kwargs["use_cache"] = True
            # Support both old (past_key_value) and new (past_key_values) param names
            if "past_key_values" in sig.parameters:
                kwargs["past_key_values"] = hf_cache
            elif "past_key_value" in sig.parameters:
                kwargs["past_key_value"] = hf_cache
                
            if "cache_position" in sig.parameters:
                kwargs["cache_position"] = cache_position
            if "position_embeddings" in sig.parameters:
                kwargs["position_embeddings"] = position_embeddings
                
            layer_outputs = layer(hidden_states, **kwargs)
            
            # sync_back only needed for HFProxyCache (standard model with CPU offloading)
            if not self._is_hybrid:
                hf_cache.conv_states.sync_back()
                hf_cache.recurrent_states.sync_back()
            
            if isinstance(layer_outputs, tuple):
                hidden_states = layer_outputs[0]
            else:
                hidden_states = layer_outputs
            
            self.offload_weights(layer)
            
            # REMOVED: torch.cuda.empty_cache() and synchronize() in inner loop
            # These were the primary bottlenecks for LayerStream generation speed.
            # We only record VRAM usage here.
            self.tracker.update_vram()
            
        norm = self.components['norm']
        if norm is not None:
            t0 = time.perf_counter()
            norm_dict = self.loader.get_weights(self.norm_path)
            self.tracker.record_layer_load(time.perf_counter() - t0)
            norm_tensors, norm_dict = self._dev_tensors_for(self.norm_path, norm, norm_dict)
            self.assign_weights(norm, norm_dict, tensors=norm_tensors)
            hidden_states = norm(hidden_states)
            self.offload_weights(norm)
            self.tracker.update_vram()

        lm_head = self.components['lm_head']
        t0 = time.perf_counter()
        lm_head_dict = self.loader.get_weights(self.lm_head_path)
        self.tracker.record_layer_load(time.perf_counter() - t0)
        lm_tensors, lm_head_dict = self._dev_tensors_for(self.lm_head_path, lm_head, lm_head_dict)
        self.assign_weights(lm_head, lm_head_dict, tensors=lm_tensors)
        
        last_hidden_state = hidden_states[:, -1:, :]
        logits = lm_head(last_hidden_state)
        self.offload_weights(lm_head)
        self.tracker.update_vram()
        
        self.tracker.record_compute(time.perf_counter() - compute_start)
        if self._is_hybrid:
            self.tracker.set_kv_cache_size(self.cache.get_size_mb())
            self.cache._seq_length = past_length + seq_length
        else:
            self.tracker.set_kv_cache_size(self.kv_manager.get_size_mb())
            self.kv_manager.seq_length = past_length + seq_length
        return logits
