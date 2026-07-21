---
tags: [architecture, diagrams, system-design]
source: "[[Docs/visuals.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Visuals

The Visuals page serves as the canonical reference for SovereignAI Edge system architecture diagrams, rendered in ASCII box-drawing characters for maximum terminal and text-editor compatibility. It covers: (1) the high-level system architecture showing the Electron shell, React frontend, FastAPI gateway, and dual inference engines (FullRAM and LayerStream) over the filesystem/hardware layer; (2) the engine selection decision logic based on hardware profiling; (3) a deep-dive into LayerStream's SSD-backed layer-by-layer execution with double-buffering; (4) the end-to-end inference pipeline tracing a token from keystroke to UI update; (5) LayerStream double-buffering (ping-pong buffers to hide disk I/O latency); (6) context window sliding with anchor-pinning; (7) a data flow matrix mapping components to their input, transformation, and output; (8) the USB deployment structure; and (9) an ER diagram of the SQLite schema.

The double-buffering and context-window-sliding diagrams illustrate the two most critical algorithmic innovations: the former hides NVMe read latency behind compute, and the latter preserves system prompt context when conversations exceed the model's maximum token limit.

## Key Points

- ASCII diagrams cover system architecture, engine selection, LayerStream internals, and data flow
- Double-buffering: Buffer A computes Layer N while Buffer B pre-loads Layer N+1 from SSD
- Context sliding: system prompt is pinned, oldest 50% of conversation history is pruned
- Data flow matrix maps components to their input, transformation, and output types
- ER diagram shows Models, Sessions, Messages, Hardware, and Plugins tables
- USB deployment structure ensures zero-configuration portability across hosts

## Related
- [[Engines Overview]]
- [[Engine Algorithms]]
- [[Algorithms]]
- [[Working]]
- [[Technical Architecture]]
