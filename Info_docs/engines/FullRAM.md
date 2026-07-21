---
tags: [engine, inference, fullram, performance]
source: "[[Docs/FullRAM.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# FullRAM

FullRAM is a high-performance inference architecture that loads the entire language model into VRAM or RAM for maximum tokens-per-second speed. It is one of two core execution engines in SovereignAI Edge's dual-engine architecture, automatically selected by the hardware profiler when available memory exceeds model size by at least 20%.

## Architecture

The FullRAM engine inherits from `BaseEngine` and uses the Hugging Face `transformers` ecosystem. It loads the complete model via `AutoModelForCausalLM` with `device_map="auto"` for automatic CUDA/CPU placement. On CUDA systems it uses FP16 precision; on CPU systems it falls back to FP32. Inference is wrapped in `asyncio.to_thread()` to avoid blocking the event loop, and streaming uses `TextIteratorStreamer` for real-time token delivery.

## Memory Characteristics

FullRAM's memory formula is:
$$V_{full} \approx S_{model} + (2 \times L_{ctx} \times N_{layers} \times D_{hidden} \times B_{p})$$

Where $S_{model}$ is model size and $L_{ctx}$ is context length. The KV cache is stored entirely in VRAM for fastest access. Unloading uses explicit `del self.model` and `torch.cuda.empty_cache()` to reclaim memory.

## Key Points

- Maximum throughput -- all parameters in memory, no I/O wait for weight loading
- Requires 16GB+ RAM or 8GB+ VRAM depending on model size
- Compute-bound: throughput limited by GPU TFLOPS
- Standard Hugging Face `transformers` pipeline, no custom layer management
- Best for systems with sufficient memory where speed is the priority

## Related

- [[LayerStream]] — Low-memory alternative for the dual-engine architecture
- [[Engines Overview]] — FullRAM vs LayerStream comparison
- [[Engine Algorithms]] — Pseudocode for FullRAM execution
- [[GGUF]] — Model format consumed by both engines
- [[Hardware Profiler]] — Automatic engine selection logic
- [[KV Cache]] — KV cache management in FullRAM mode
