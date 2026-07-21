---
tags: [research, gaps, inference, memory-constraints]
source: "[[Docs/Gaps.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Gaps

This document catalogs 15 research gaps in memory-constrained LLM inference identified from recent academic literature (2023-2025). These gaps represent the key challenges that SovereignAI Edge's dual-engine architecture, particularly the LayerStream engine, aims to address. The gaps span technical architecture, memory management, hardware platforms, collaborative computing, evaluation methodology, system optimization, and integration scalability.

The most critical architectural gap is the lack of unified dual-mode execution frameworks -- current research focuses on single-mode approaches (either full-memory or offloading) rather than adaptive systems that can seamlessly transition between FullRAM and LayerStream execution based on dynamic resource availability. This is the core innovation space that SovereignAI Edge occupies. A closely related gap is the insufficiency of true layer-streaming architecture development: while papers address weight offloading and memory management, none specifically implement the approach of sequentially loading transformer layers from storage during execution that SovereignAI Edge employs.

On the system optimization front, existing approaches fail to provide comprehensive solutions for the quadratic-complexity attention operation bottleneck in memory-limited scenarios, and constraint-aware resource scheduling systems lack algorithms that simultaneously optimize throughput, latency, and resource utilization. The evaluation landscape itself is fragmented -- the field lacks standardized benchmarking frameworks for comparing memory-constrained inference approaches across hardware platforms. These gaps collectively validate SovereignAI Edge's design choices: a portable, dual-mode, fully offline system with layer-streaming inference and adaptive memory management.

## Key Points

- 15 research gaps identified across 7 categories: architecture, memory, hardware, collaborative computing, evaluation, optimization, and integration
- Gap 1 (unified dual-mode execution) is the primary gap SovereignAI Edge addresses
- Gap 3 (real-time adaptive offloading) aligns with the Hardware Profiler's dynamic engine selection
- Gap 5 (fine-grained pipeline coordination) relates to LayerStream's I/O and computation scheduling
- Gap 10 (lack of standardized benchmarking) highlights the need for better evaluation frameworks
- References include FlexInfer, Active-Weight Swapping, LLM in a flash, and other key papers

## Related
- [[PRD]] — Product vision and feature list
- [[TRD]] — Technical requirements and stack details
- [[Engines Overview]] — FullRAM and LayerStream architecture
- [[Algorithms]] — Core adaptive memory and LayerStream algorithms
- [[Technical Architecture]] — How the system addresses these gaps
