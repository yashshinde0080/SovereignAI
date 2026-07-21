---
tags: [algorithms, memory, inference, core]
source: "[[Docs/algorithms.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Algorithms

SovereignAI Edge's efficiency rests on custom algorithms designed to squeeze maximum performance from constrained hardware while remaining entirely offline. Three foundational algorithms drive the system. The **Adaptive Memory Allocation Algorithm** prevents out-of-memory (OOM) crashes: it parses the GGUF header for total tensor bytes, queries free system RAM and VRAM, and routes execution to GPU (if VRAM is sufficient), FullRAM CPU (if total RAM exceeds model size by a 10% buffer), or LayerStream (if RAM is insufficient). The **LayerStream Execution Algorithm** breaks the traditional requirement that the entire model graph reside in memory: it locks the KV cache in RAM, allocates a two-layer sliding buffer, computes Layer N while asynchronously pre-fetching Layer N+1 from NVMe SSD, then discards and overwrites. The **Context Window Sliding Mechanism** pins the system prompt, prunes the oldest 50% of conversation history when the token limit is exceeded, and invalidates the corresponding KV cache entries.

These algorithms together enable running 70B-parameter models on as little as 8 GB of RAM by effectively treating the SSD as virtualized model memory and the context window as a rolling buffer.

## Key Points

- Adaptive Memory Allocation: three-tier routing (GPU \(\rightarrow\) FullRAM \(\rightarrow\) LayerStream) based on real-time memory availability
- LayerStream Execution: ping-pong double-buffering hides SSD read latency behind compute
- Context Window Sliding: anchor-pinning preserves system prompt; oldest turns are pruned; KV cache slots are recycled
- All algorithms are designed for offline, no-cloud operation from the ground up

## Related
- [[Engine Algorithms]]
- [[Engines Overview]]
- [[Gaps]]
- [[Implemented Algorithms]]
- [[LayerStream]]
- [[FullRAM]]
