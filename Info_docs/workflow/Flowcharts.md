---
tags: [architecture, flowcharts, decision-logic]
source: "[[Docs/flowcharts.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Flowcharts

SovereignAI Edge uses two primary decision flowcharts to govern model initialization and request error handling. The model initialization flowchart traces the path from a "Load Model" request through GGUF header parsing, compute footprint calculation, and hardware comparison -- branching to either FullRAM (if the model fits in available RAM) or LayerStream (if memory is constrained). The request error handling flowchart routes incoming chat payloads through Pydantic validation, returning 422 on invalid input, or enqueuing the job with a 202 Accepted status if the engine is busy.

These flowcharts codify the core routing logic that makes SovereignAI Edge adaptive to diverse hardware environments without requiring user configuration. The decision to use FullRAM versus LayerStream is the single most consequential branching point in the system, determining memory usage, inference speed, and power consumption for the entire session.

## Key Points

- Model init: GGUF header reading \(\rightarrow\) footprint calculation \(\rightarrow\) RAM comparison \(\rightarrow\) FullRAM or LayerStream
- Request handling: Pydantic validation \(\rightarrow\) engine busy check \(\rightarrow\) enqueue or infer immediately
- 422 returned for invalid payloads; 202 Accepted used when engine is busy
- Engine selection is purely automatic based on hardware profiling

## Related
- [[Working]]
- [[Engines Overview]]
- [[Technical Architecture]]
- [[Pydantic]]
