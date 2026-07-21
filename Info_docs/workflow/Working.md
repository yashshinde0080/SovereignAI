---
tags: [state-machine, architecture, core]
source: "[[Docs/working.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Working

SovereignAI Edge operates through a deterministic state machine that governs the application lifecycle. Six core states -- `UNINITIALIZED`, `READY_IDLE`, `LOADING_MODEL`, `ACTIVE_IDLE`, `INFERENCING`, and `ERROR_STATE` -- ensure consistency, prevent race conditions in single-machine offline deployments, and keep the user informed via SSE-driven UI updates. Transitions between states are triggered by user actions (model selection, prompt submission) or system events (I/O errors, hardware detachments), with the `ERROR_STATE` providing a guaranteed teardown-and-recovery path back to `READY_IDLE`.

The backend communicates its state to the React frontend through a persistent SSE (Server-Sent Events) endpoint or active polling. When traversing states, the UI swaps visual blocks -- for example, morphing an input box into a progress bar during model loading. This pattern keeps the interface responsive while the inference engine performs synchronous compute-bound work.

## Key Points

- Six operational states form the application state machine: UNINITIALIZED, READY_IDLE, LOADING_MODEL, ACTIVE_IDLE, INFERENCING, ERROR_STATE
- SSE or polling carries real-time state updates from backend to frontend
- ERROR_STATE forces teardown of memory-mapped pointers before reverting to READY_IDLE
- Model loading locks inference; inference queues all other tasks via the scheduler
- Uninitialized state blocks on dependency checks before allowing any operation

## Related
- [[Working Flow]]
- [[Flowcharts]]
- [[Schedulers]]
- [[Technical Architecture]]
