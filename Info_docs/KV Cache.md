# KV Cache

Key-Value (KV) Cache is a ==memory optimization technique== used in transformer-based LLMs to avoid recomputing attention keys and values for previously generated tokens.

## Role in SovereignAI Edge

==KV Cache== is critical to both inference engines, with different storage strategies:

- **FullRAM Mode:** KV Cache stored entirely in VRAM for fastest access
- **LayerStream Mode:** KV Cache stored in system RAM while VRAM only holds active layer

## Memory Impact

The KV Cache grows linearly with context length:
$$\\Delta KV \\approx 4 \\times L_{ctx} \\times N_{layers} \\times D_{hidden} \\times \\text{Precision\\_Bytes}$$

For a 7B model with 32 layers and 4096 hidden dimension at FP16:
- **FullRAM:** ~2GB VRAM for 2048 token context
- **LayerStream:** System RAM absorbs this growth, keeping VRAM nearly constant

## Context Sliding

When conversation exceeds token limit, the ==Context Window Sliding== mechanism:
1. Pins the system prompt
2. Prunes oldest tokens from history
3. Invalidates corresponding KV Cache entries

## See Also

- [[Engines Overview]] — Memory lifecycle in both engines
- [[Engine Algorithms]] — VRAM and RAM occupancy formulas
- [[Algorithms]] — Context window sliding mechanism
- [[Gaps]] — Research gaps in KV cache optimization
