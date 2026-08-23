# Engine System

Two inference engines implement `BaseEngine` ABC. `ModelManager` routes all load/unload/generate through the active engine reference.

## BaseEngine ABC

`backend/app/engines/base.py` — 5 abstract methods:

| Method | Purpose |
|---|---|
| `async load()` | Load model into engine |
| `async unload()` | Unload model, free resources |
| `async generate(input_data, **kwargs) -> Dict` | Non-streaming inference |
| `async generate_stream(input_data, **kwargs) -> AsyncGenerator` | Streaming inference |
| `get_memory_usage() -> Dict` | Current RAM/VRAM usage |

Concrete: `get_stats()` returns engine statistics dict.

## FullRAMEngine

**File:** `backend/app/engines/fullram/executor.py`
**Mode:** `fullram`
**Experimental:** `False` (default for models that fit)

### Load

1. `TaskResolver.resolve()` — get task_type, input_modality, is_generative
2. `TaskRouter.get_model_class(task_type)` — maps task → `AutoModelForCausalLM` / `AutoModelForSequenceClassification` / etc.
3. `model_class.from_pretrained()` with device_map, dtype, trust_remote_code
4. GGUF: passes `gguf_file=` kwarg to transformers
5. Load tokenizer / processor (text / image / audio / multimodal)
6. GGUF fallback chain: transformers → `ik_llama_cpp` (BitNet/IQ2_BN) → `llama_cpp`

### Generate (non-streaming)

1. Process inputs by modality (text, image, audio, multimodal)
2. Tokenize with chat template if available
3. `TaskRouter.execute()` — runs `model.generate()` in `asyncio.to_thread()`
4. Decode output IDs, strip prompt tokens
5. Return `{output, finish_reason, metadata}`

### Generate (streaming)

1. Tokenize prompt
2. Create `TextIteratorStreamer` (skip_prompt=True, skip_special_tokens=True)
3. Run `model.generate()` in a **Thread** with streamer
4. Yield `{token, finish_reason}` for each new text chunk

### llama-cpp Fallback

When transformers can't load the architecture:
1. Try `ik_llama_cpp.IkLlama` (handles BitNet IQ2_BN)
2. Fall back to `llama_cpp.Llama`
3. Both use `_IkModelWrapper` for API compatibility
4. llama-cpp models run via `asyncio.to_thread()` for non-blocking

## LayerStreamEngine

**File:** `backend/app/engines/layerstream/executor.py`
**Mode:** `layerstream`
**Experimental:** `True` (~0.4 tok/s measured vs 3.84 FullRAM CPU)

### Load

1. Check if split weights exist in `workspace/offload_cache/{model_name}/`
2. If not: run `WeightSplitter.split_and_save()` — loads full model to CPU, saves per-layer safetensors
3. Load tokenizer from weights_dir
4. `AutoConfig.from_pretrained()` → force eager attention
5. `AutoModelForCausalLM.from_config()` with `init_empty_weights()` (meta tensors)
6. `ModelIntrospector.detect_model_components()` → extract embed, layers, norm, lm_head
7. Create `LayerExecutor` with weight loader, KV cache, prefetch settings

### Generate (non-streaming)

```python
# Phase 1: Prefill — process entire input sequence
logits = executor.execute_forward(input_ids, mode="prefill")
next_token = Sampler.sample(logits, temperature, top_p)

# Phase 2: Decode — generate one token at a time
for _ in range(max_tokens):
    logits = executor.execute_forward(current_input, mode="decode")
    next_token = Sampler.sample(logits, temperature, top_p)
    generated_tokens.append(next_token.item())
```

Runs in `asyncio.to_thread()` for non-blocking.

### Generate (streaming)

Same prefill → decode loop, but yields tokens incrementally. Uses `_stream_delta()` — rolling-window decode with overlap detection to handle BPE subword merges.

See [[05-layer-by-layer]] for detailed layer execution.

## Hybrid Models (Qwen3.5)

Models with mixed attention types (linear_attention + full_attention) use `StatefulCache` instead of `KVCacheManager`. The cache tracks both `key_cache`/`value_cache` (full attention) and `conv_states`/`recurrent_states` (linear attention) per layer.

## TurboQuant (Experimental, Default OFF)

Optional KV-cache compression via polar quantization + QJL. Configured via `settings.turboquant_enabled` (default: False). The eval gate fails — do not re-enable without the gate passing.

## Engine Unloading

Both engines:
1. `del model` / `del tokenizer` / `del processor`
2. Clear caches (KV cache, device cache, loader cache)
3. `gc.collect()` + `torch.cuda.empty_cache()`
4. `self.loaded = False`

## Related

- [[00-architecture-overview]] — Engine selection in the architecture
- [[03-model-loading]] — How engines are created and loaded
- [[05-layer-by-layer]] — LayerStream's execution internals
- [[06-weight-splitting]] — How models are split
- [[12-task-resolution]] — Task type determines which model class to use
- [[11-hardware-memory]] — Mode selection logic
