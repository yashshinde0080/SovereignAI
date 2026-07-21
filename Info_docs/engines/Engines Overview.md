---
tags: [engine, architecture, inference]
source: "[[Docs/engines_overview.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Engines Overview

SovereignAI Edge uses a dual-engine inference architecture consisting of the [[FullRAM]] engine and the [[LayerStream]] engine. These engines are selected automatically at runtime by the hardware profiler based on available system resources. FullRAM maximizes throughput by loading the entire model into active memory, while LayerStream enables running large models on memory-constrained hardware by streaming layers from disk.

The FullRAM engine inherits from `BaseEngine` and uses the standard Hugging Face `transformers` pipeline. It loads all model weights into VRAM or RAM at once, delivering maximum tokens-per-second performance. Its inference pipeline wraps the blocking `model.generate()` call in `asyncio.to_thread()` to keep the API responsive, and supports streaming via `TextIteratorStreamer` for real-time token delivery.

The LayerStream engine implements a memory-bounded architecture that decouples computation from memory by streaming transformer layers sequentially. It pre-processes models into per-layer `.safetensors` chunks via `WeightSplitter`, builds an empty model scaffold with `init_empty_weights()`, and executes a custom two-phase pipeline (context prefill followed by autoregressive decoding) that loads, computes, and flushes each layer one at a time. The KV cache resides in system RAM, keeping VRAM footprint nearly constant regardless of context length.

## Key Points

- FullRAM is compute-bound (GPU TFLOPS limits throughput); LayerStream is I/O-bound (PCIe/SSD bandwidth limits throughput)
- FullRAM requires enough RAM/VRAM to hold the entire model; LayerStream needs only enough for a single layer (~1-2% of model size)
- FullRAM uses standard Hugging Face generation; LayerStream uses a custom `execute_forward()` loop with independent `Sampler`
- Pre-processing overhead: FullRAM loads directly (no preprocessing); LayerStream requires one-time disk chunking via `WeightSplitter`
- LayerStream's VRAM savings factor scales with the number of layers ($N_{layers}$), e.g., ~30x for a 32-layer model

## Related

- [[FullRAM]] — High-performance monolithic inference engine
- [[LayerStream]] — Memory-bounded layer-sequential inference engine
- [[Engine Algorithms]] — Pseudocode and mathematical models for both engines
- [[Hardware Profiler]] — Engine selection logic based on hardware detection
- [[BaseEngine]] — Abstract engine interface
