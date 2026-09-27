---
tags: [engine, architecture, inference]
source: "[[Docs/engines_overview.md]]"
created: 2026-07-21
updated: 2026-09-27
---

# Engines Overview

SovereignAI Edge uses a **three-engine** inference architecture: **FullRAM**, **LayerStream**, and **CloudAPI**. Engines are selected automatically at runtime by the hardware profiler and `MemoryManager` based on available system resources and model fit scoring (`llmfit`). `mode=auto` (default) triggers auto-selection; `mode=cloud` bypasses all local checks.

All engines implement the `BaseEngine` ABC (`backend/app/engines/base.py`) with 5 abstract methods: `async load()`, `async unload()`, `async generate()`, `async generate_stream()`, `get_memory_usage()`. The active engine is stored in `app.state.active_engine` and routed through `ModelManager`.

### FullRAM Engine — Maximum Throughput
- Loads **entire model** into RAM/VRAM via `transformers.AutoModelForCausalLM` (primary)
- GGUF fallback via `llama-cpp-python` / `ik-llama-cpp-python` (for architectures transformers cannot load, e.g., BitNet IQ2_BN)
- Streaming via `TextIteratorStreamer` + `asyncio.to_thread()`
- **Best for:** 16GB+ RAM, dedicated GPU (8GB+ VRAM)
- **Performance:** 20-80+ tok/s on consumer GPUs

### LayerStream Engine — Memory-Bounded
- **Streams layers** from disk per forward pass (safetensors chunks in `workspace/offload_cache/`)
- Preprocessing: `WeightSplitter` → per-layer `.safetensors` + `quant_config.json` (quant: none/int8/int4)
- Two-phase pipeline: Context prefill → Autoregressive decode (`LayerExecutor.execute_forward()`)
- KV cache in system RAM; VRAM footprint ~constant regardless of context length
- `LayerWeightLoader` = `ThreadPoolExecutor(prefetch_depth=3)` + LRU byte-budget cache (pinned: embed/norm/lm_head)
- Hybrid models (Qwen3.5) → `StatefulCache` (transformers 5.x hybrid protocol); standard → `KVCacheManager` + `HFProxyCache`
- Device cache budget: CUDA = 50% free VRAM; CPU = 50% total RAM (floor 512MB) — must cover full per-token working set
- **Best for:** 8GB RAM, NVMe SSD, integrated graphics
- **Performance:** 0.4-8 tok/s (measured on 8GB device: Qwen2-0.5B int4 8.0 tok/s; Qwen3.5-0.8B hybrid 1.3 tok/s with cache resident)

### CloudAPI Engine — Online Mode
- Proxies requests to external providers: OpenAI, Anthropic, Google, Mistral, Custom (OpenAI-compatible: Together, Groq, vLLM, Ollama)
- No local model weights loaded — `mode=cloud` skips `TaskResolver` and `MemoryManager` entirely
- Encrypted API key storage: Fernet + PBKDF2HMAC (480k iters) in `cloud_providers` table (`sovereign_settings.db`)
- Keys **never returned in GET responses** (masked only: `****sk-...xxxx`), never logged
- Streaming SSE from all provider types, unified chunk format via `CloudAPIEngine.stream_response()`
- Switch via `POST /v1/chat/mode/switch?mode=cloud` or CLI `sovereign cloud add`

## Key Points

- FullRAM is compute-bound (GPU TFLOPS limits throughput); LayerStream is I/O-bound (PCIe/SSD bandwidth limits throughput); CloudAPI is network-bound
- FullRAM requires enough RAM/VRAM to hold the entire model; LayerStream needs only enough for a single layer (~1-2% of model size)
- FullRAM uses standard Hugging Face generation; LayerStream uses custom `execute_forward()` loop with independent `Sampler`; CloudAPI translates provider APIs
- Pre-processing overhead: FullRAM loads directly; LayerStream requires one-time disk chunking via `WeightSplitter`; CloudAPI requires zero local prep
- LayerStream's VRAM savings factor scales with the number of layers ($N_{layers}$), e.g., ~30x for a 32-layer model
- Engine selection lives in `ModelManager._load_model_locked()` → `EngineFactory.create_engine()`, not in engines themselves
- TurboQuant (KV-cache compression) is experimental, default OFF (`turboquant_enabled=False`), eval gate fails

## Related

- [[FullRAM]] — High-performance monolithic inference engine
- [[LayerStream]] — Memory-bounded layer-sequential inference engine
- [[CloudAPI]] — Online provider proxy engine
- [[Engine Algorithms]] — Pseudocode and mathematical models for all engines
- [[Hardware Profiler]] — Engine selection logic based on hardware detection
- [[BaseEngine]] — Abstract engine interface