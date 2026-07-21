---
tags: [algorithm, engine, inference, pseudocode]
source: "[[Docs/engine_algorithms.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Engine Algorithms

This document details the procedural algorithms and mathematical models that drive SovereignAI's dual inference engines. The FullRAM engine follows a straightforward monolithic autoregressive generation loop, while the LayerStream engine implements a custom four-phase pipeline designed to execute large models on severely hardware-constrained systems.

## FullRAM Execution

The FullRAM algorithm loads the entire model into memory in a single operation, then uses the standard Hugging Face `transformers` generation loop. Tokenization, forward pass, and sampling are all handled internally by `model.generate()`, wrapped in `asyncio.to_thread()` to avoid blocking the event loop. Its latency is compute-bound, governed by GPU TFLOPS.

## LayerStream Execution

LayerStream uses a four-phase algorithm:

1. **Weight Splitting (Phase 0):** Monolithic model weights are chunked into per-layer `.safetensors` files on disk. This is a one-time preprocessing step.
2. **Meta-Scaffolding (Phase 1):** The model architecture is built using `init_empty_weights()` without allocating memory for weights. Executors and KV cache manager are initialized.
3. **Context Prefill (Phase 2):** The entire prompt is processed layer by layer -- each layer is loaded from disk, computed, its KV state stored, and flushed before loading the next. Establishes initial logits and KV cache.
4. **Token Decoding (Phase 3):** An autoregressive loop generates tokens one at a time, streaming each layer from disk per token. For a 32-layer model generating 100 tokens, this performs 3,200 separate file reads.

## Mathematical Framework

The key formulas for VRAM occupancy differ fundamentally between engines:
- **FullRAM VRAM:** $V_{full} \approx S_{model} + (2 \times L_{ctx} \times N_{layers} \times D_{hidden} \times B_{p})$
- **LayerStream VRAM:** $V_{layer} \approx \frac{S_{model}}{N_{layers}} + \text{Padding\_Buffers}$ (KV cache offloaded to system RAM)

Inference latency is bounded by different resources:
- **FullRAM:** Compute-bound -- $T_{full} \approx \frac{FLOPs_{per\_token}}{TFLOPS_{gpu}}$
- **LayerStream:** Bandwidth-bound -- $T_{layer} \approx \frac{S_{model}}{BW_{pcie}}$

## Key Points

- FullRAM is a single-phase load-and-generate algorithm; LayerStream is a four-phase pipeline
- LayerStream transforms the bottleneck from compute speed (GPU TFLOPS) into storage I/O speed (SSD MB/s)
- For a 7B model on PCIe Gen3 x16, LayerStream throughput is approximately 1.14 tokens/sec
- KV cache in LayerStream resides entirely in system RAM to minimize VRAM footprint
- Each decoded token in LayerStream requires streaming all N layers from disk

## Related

- [[Engines Overview]] — FullRAM and LayerStream architecture deep-dive
- [[Implemented Algorithms]] — 25 algorithms across the full SovereignAI platform
- [[FullRAM]] — Monolithic engine
- [[LayerStream]] — Memory-bounded engine
- [[KV Cache]] — KV cache management across both engines
