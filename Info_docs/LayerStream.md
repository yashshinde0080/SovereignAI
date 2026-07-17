# LayerStream

A ==memory-bounded inference architecture== that enables running large language models on severely resource-constrained hardware (as low as 8GB RAM) by streaming neural network layers from disk sequentially.

## Role in SovereignAI Edge

[[LayerStream]] is one of the two core execution engines in SovereignAI Edge's ==dual-engine architecture==. It is automatically selected by the [[Hardware Profiler]] when available memory is insufficient for [[FullRAM]] mode.

## How It Works

1. **Weight Splitting:** The monolithic model is pre-processed into discrete per-layer `.safetensors` files
2. **Meta-Scaffolding:** The model architecture is built with `init_empty_weights()` — no memory allocated for weights
3. **Sequential Execution:** Each layer is loaded from disk → computed → flushed before loading the next
4. **KV Cache in RAM:** Key-Value cache stays in system memory while only the active layer occupies VRAM

## Performance Characteristics

| Metric | Value |
|--------|-------|
| **VRAM Usage** | Size of single layer (~1-2% of model) |
| **Bottleneck** | Storage I/O bandwidth (SSD read speed) |
| **Throughput** | ~1.14 tokens/sec on PCIe Gen3 for 7B model |
| **Best For** | 70B+ models on 8GB RAM laptops |

## See Also

- [[Engines Overview]] — FullRAM vs LayerStream deep-dive
- [[Engine Algorithms]] — Pseudocode for layer streaming
- [[Algorithms]] — Adaptive memory allocation algorithm
- [[GGUF]] — Model format used for layer storage
