---
tags: [memory, inference, optimization, kv-cache, attention]
source: "[[Docs/KV Cache.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# KV Cache

Key-Value (KV) Cache is a memory optimization technique used in transformer-based LLMs to avoid recomputing attention keys and values for previously generated tokens. Instead of recalculating the full attention matrix at each step, the KV cache stores the key and value tensors from prior tokens and appends only the new token's contributions.

## Role in SovereignAI Edge

KV Cache is critical to both inference engines, with different storage strategies. In FullRAM mode, the KV cache is stored entirely in VRAM for fastest access. In LayerStream mode, the KV cache resides in system RAM while VRAM only holds the active layer -- this prevents VRAM-based execution failure as context length grows.

## Memory Impact

The KV cache grows linearly with context length:
$$\Delta KV \approx 4 \times L_{ctx} \times N_{layers} \times D_{hidden} \times \text{Precision\_Bytes}$$

For a 7B model with 32 layers and 4096 hidden dimension at FP16, the KV cache costs approximately 2GB of VRAM at 2048 tokens in FullRAM mode. In LayerStream mode, this growth is absorbed by system RAM.

## Context Sliding

When conversation exceeds the token limit, the context window sliding mechanism pins the system prompt, prunes the oldest tokens from history, and invalidates corresponding KV cache entries.

## Key Points

- Eliminates O(L^2) recomputation for each new token, reducing per-token attention cost to O(L)
- FullRAM stores KV cache in VRAM; LayerStream stores it in system RAM
- KV cache scales linearly with context length, hidden dimension, and layer count
- Context sliding prunes oldest tokens to stay within memory budget

## Related

- [[LayerStream]] — KV cache stored in system RAM during layer-streaming inference
- [[Engines Overview]] — Memory lifecycle in both FullRAM and LayerStream
- [[Engine Algorithms]] — VRAM and RAM occupancy formulas including KV cache
- [[FullRAM]] — KV cache stored in VRAM for fastest access
