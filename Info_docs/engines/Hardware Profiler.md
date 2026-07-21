---
tags: [hardware, profiler, engine-selection, detection]
source: "[[Docs/Hardware Profiler.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Hardware Profiler

The Hardware Profiler is the engine selection component that analyzes system resources at runtime to choose the optimal inference mode for SovereignAI Edge. It sits at the decision-making layer of the architecture, determining whether the FullRAM or LayerStream engine is used for each inference request. It queries system resources via psutil and OS-level APIs to check available RAM and VRAM, compares the model size against available resources with a 20% safety buffer, and routes execution to the appropriate engine.

The decision logic follows a three-tier cascade. If free VRAM exceeds the model size, execution runs on GPU in FullRAM mode for maximum performance. If free VRAM plus free RAM exceeds model size times a 1.2 safety factor, execution runs on CPU in FullRAM mode, using mmap to map the model directly into memory. If neither condition is satisfied, the system initializes LayerStream mode, loading and unloading individual neural network layers from disk sequentially. This adaptive selection ensures the largest possible models run on any given hardware configuration.

The Hardware Profiler also supports automatic fallback -- if resource availability changes during a session (e.g., another application frees memory), it can dynamically switch between modes. This real-time adaptability directly addresses a key research gap identified in the literature (Gap 3: lack of real-time adaptation mechanisms) and is central to SovereignAI Edge's value proposition of running LLMs on a wide range of consumer-grade hardware without manual configuration.

## Key Points

- Queries psutil and OS-level APIs for available RAM and VRAM
- Three-tier decision: GPU FullRAM -> CPU FullRAM -> LayerStream
- Applies 1.2x safety buffer when comparing model size to available memory
- Supports dynamic fallback if resource availability changes mid-session
- Central to the dual-engine architecture: enables automatic, configuration-free engine selection
- Addresses research Gap 3 (real-time adaptive offloading mechanisms)

## Related
- [[Info Dashboard]] — Vault navigation and overview
- [[FullRAM]] — High-memory inference engine
- [[LayerStream]] — Low-memory inference engine
- [[Technical Architecture]] — System component interactions
- [[Algorithms]] — Adaptive memory allocation algorithm
- [[PRD]] — Product feature list including hardware profiler
