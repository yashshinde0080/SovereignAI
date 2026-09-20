# Layer-by-Layer Inference

LayerStream enables 3–8B Q4 models on ~8GB RAM by swapping layer weights from disk per forward pass. Only one transformer layer is on the device at a time.

## Architecture

```
LayerStreamEngine
  → LayerExecutor (orchestrates IO, KV, forward passes)
    → LayerWeightLoader (ThreadPoolExecutor prefetch, LRU budget cache)
    → KVCacheManager / StatefulCache (attention state)
    → Sampler (Top-K + Top-P + multinomial)
    → BenchmarkTracker (perf metrics)
```

## Weight Splitting (First Load)

`WeightSplitter.split_and_save()` (`backend/app/engines/layerstream/splitter.py`):
1. Load full model to CPU via `AutoModelForCausalLM.from_pretrained(device_map="cpu")`
2. RAM preflight: need ~2x model size free
3. `ModelIntrospector.detect_model_components()` → extract embed, layers, norm, lm_head
4. Optionally quantize: none (fp16), int8, int4
5. Save each component as `.safetensors`:
   - `embed.safetensors` — token + position embeddings
   - `layer_0.safetensors` ... `layer_N.safetensors` — transformer blocks
   - `norm.safetensors` — final layer norm
   - `lm_head.safetensors` — language model head
6. Save `quant_config.json`, copy tokenizer files
7. Delete full model from RAM

Output: `workspace/offload_cache/{model_name}/`

## Quantization During Split

### int8 (Per-Tensor Symmetric)
- Scale = `max_abs / 127`
- Quantized: `round(tensor / scale).clamp(-128, 127).to(int8)`
- Stored: `{name}.int8` + `{name}.scale` (fp32 scalar)
- Dequant: `tensor.to(dtype) * scale`

### int4 (Group-wise Q4_0-style)
- Group size: 32 contiguous values along last dim
- Scale = `max_abs / 8` per group (fp16)
- Quantized: `round(grouped / scale).clamp(-8, 7)` → packed 2 nibbles per byte
- Stored: packed uint8 + `{name}.scale` [rows, num_groups]
- Dequant: unpack nibbles → two's complement → multiply by scale → reshape

## Layer Execution (LayerExecutor)

**File:** `backend/app/engines/layerstream/layer_executor.py`

### Forward Pass

```
execute_forward(input_ids, mode="prefill"|"decode")
  1. Load embed weights from loader (pinned — never evicted)
  2. Embed tokens + position IDs
  3. For each layer i:
     a. prefetch_async(layer_i+1) — start disk read ahead
     b. Get weights from loader (wait if not cached)
     c. Dequantize on device (int8/int4 → fp16/bf16)
     d. Run layer forward pass with attention mask + KV cache
     e. offload_weights() — replace params with empty(0) tensors
  4. Apply final norm
  5. Apply lm_head
  6. Return logits
```

### Attention Mask

`_create_attention_mask()` — architecture-aware causal mask:
- Cached per (batch, seq, past_length, dtype) — bounded at 64 entries
- Prefill: full causal mask
- Decode: extends mask with `past_length` columns for cached KV

### Device Cache

Dequantized (compute-dtype) tensors cached per component path on GPU:
- Budget = 50% of free VRAM at init
- Bounded LRU eviction
- Prevents per-token re-dequantization (measured ~68% of decode wall time)

### Compute Dtype Selection

```python
if device == "cuda":    → fp16
elif bf16 capable:      → bf16 (AVX512-BF16/AMX only)
else:                   → fp32
```

BF16 on AVX2 is emulated by torch (~160x slower than fp32), so it's gated on native capability.

## Weight Loading (LayerWeightLoader)

**File:** `backend/app/engines/layerstream/loader.py`

### Prefetch System

- `ThreadPoolExecutor(max_workers=prefetch_depth)` — default depth 3
- `prefetch_async(path)` — submits future for upcoming layers
- Completed futures reaped to make room; full window left for next step
- **Parked:** deeper windows, batched reads, GDS, io_uring — I/O is ~9% of wall and already overlapped

### CPU Cache

- LRU cache of `state_dict` dicts
- Pinned paths (`embed`, `norm`, `lm_head`) — never evicted
- Non-pinned entries evicted when `budget_bytes` exceeded
- Budget = configurable MB or auto-scaled to largest layer file × 4.5

### Quantization on Load

Quantized tensors stored in small form (int8/packed int4) in CPU cache. Dequantization happens on the compute device in `_device_tensors()`, so RAM holds the compact form.

## KV Cache

| Type | Used When | Backend |
|---|---|---|
| `KVCacheManager` | Standard models | Per-layer key/value tensors |
| `HFProxyCache` | Standard models | Wraps KVCacheManager for HF attention interface |
| `StatefulCache` | Hybrid models (Qwen3.5) | Handles full_attention + linear_attention states |
| `TurboQuantKVCacheManager` | TurboQuant enabled | Polar quantized KV cache (experimental, default OFF) |

## Sampling

`Sampler.sample(logits, temperature, top_p)`:
1. Top-K: keep top K logits
2. Top-P (nucleus): keep smallest set with cumulative probability ≥ P
3. Temperature scaling: `logits / temperature`
4. Multinomial sampling from filtered distribution
5. Non-destructive — original logits unchanged

## Streaming Delta

`_stream_delta(tokenizer, all_tokens, emitted, window=8)`:
- Decodes a rolling window of the latest 8 tokens
- Strips already-emitted text via longest-overlap matching
- Handles BPE merges that can absorb spaces/subwords across token boundaries
- Falls back to newest-token-only if no stable overlap found

## Performance Characteristics

- Measured 0.48 tok/s on Qwen3.5-0.8B hybrid (bounded by missing `causal-conv1d`)
- Measured 8.0 tok/s on Qwen2-0.5B int4
- I/O is ~9% of wall time (already overlapped behind compute)
- Device cache eliminates 68% re-dequantization overhead

## Related

- [[04-engine-system]] — Engine interface and lifecycle
- [[06-weight-splitting]] — Weight splitting details
- [[03-model-loading]] — How LayerStreamEngine is loaded
- [[11-hardware-memory]] — Memory constraints that select layerstream
