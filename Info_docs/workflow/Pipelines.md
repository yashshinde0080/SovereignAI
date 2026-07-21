---
tags: [pipelines, inference, data-flow]
source: "[[Docs/pipelines.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Pipelines

Pipelines define the rigid step-by-step transformation that data undergoes from prompt submission to text output. SovereignAI Edge uses strict synchronous operations for data safety internally, transitioning to asynchronous streaming for client delivery. The pipeline comprises four phases: (1) ingestion and Pydantic validation, (2) pre-processing and context formatting (plugin injection, templating, tokenization), (3) hardware routing and execution (engine selection, KV cache setup, autoregressive forward pass), and (4) output streaming and post-processing (detokenization, WebSocket yielding, metrics recording).

The pipeline architecture ensures that every request passes through the same validation, formatting, and routing gates regardless of the selected engine. Plugins can hook into the pre-processing phase to inject RAG context, apply safety filters, or transform formats. After generation, metrics such as tokens-per-second are calculated and persisted to SQLite alongside the conversation history.

## Key Points

- Four-phase pipeline: Ingestion/Validation, Pre-Processing, Hardware Routing/Execution, Output Streaming
- Pydantic enforces bounds on all input parameters (temperature, top-p, etc.)
- Plugin hooks execute during pre-processing for RAG, formatting, and safety
- Tokenization converts text to integer IDs; detokenization converts back
- The autoregressive loop samples via temperature, top-k, and top-p before emitting the next token

## Related
- [[Working Flow]]
- [[Engine Algorithms]]
- [[Implemented Algorithms]]
- [[Schedulers]]
- [[Pydantic]]
