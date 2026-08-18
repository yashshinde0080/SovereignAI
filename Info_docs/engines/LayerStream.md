---
tags: [engine, inference, layerstream, memory, streaming]
source: "[[Docs/LayerStream.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# LayerStream

LayerStream is a memory-bounded inference architecture that enables running large language models on severely resource-constrained hardware (as low as 8GB RAM) by streaming neural network layers from disk sequentially. It is one of two core execution engines in SovereignAI Edge's dual-engine architecture, automatically selected when available memory is insufficient for FullRAM mode.

## How It Works

LayerStream operates in four distinct phases. First, weight splitting pre-processes the monolithic model into per-layer `.safetensors` files. Second, meta-scaffolding builds the model architecture using `init_empty_weights()` without allocating memory for weights. Third, context prefill processes the entire prompt layer by layer, storing KV states in system RAM. Fourth, the autoregressive decode loop generates tokens one at a time, streaming each layer from disk per token.

## Performance Characteristics

VRAM usage is limited to the size of a single layer (~1-2% of total model size). The bottleneck shifts from compute (GPU TFLOPS) to storage I/O bandwidth (SSD read speed). A 7B model on PCIe Gen3 x16 achieves approximately 1.14 tokens/sec. The KV cache lives in system RAM while only the active layer occupies VRAM.

## Key Points

- Runs 3-8B Q4 models on 8GB RAM (measured: 0.40 tok/s, 2.3GB peak RSS); larger models run but slowly
- VRAM usage is size of single layer (~1-2% of model)
- I/O-bound: throughput limited by PCIe/storage bandwidth
- Custom two-phase computation pipeline (prefill + decode) bypasses Hugging Face `generate()`
- Aggressive garbage collection: LRU cache clearing, KV manager flush, `gc.collect()`, `torch.cuda.empty_cache()`
- Preprocessing via `WeightSplitter` is a one-time cost

## Related

- [[FullRAM]] — High-memory alternative for the dual-engine architecture
- [[Engines Overview]] — FullRAM vs LayerStream comparison
- [[Engine Algorithms]] — Pseudocode for layer streaming execution
- [[KV Cache]] — KV cache stored in system RAM in LayerStream mode
- [[GGUF]] — Model format consumed by LayerStream
- [[Hardware Profiler]] — Automatic engine selection logic
