---
tags: [scheduling, concurrency, resource-management]
source: "[[Docs/schedulers.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Schedulers

In a local, portable LLM execution environment, resource contention is a primary concern. SovereignAI Edge uses a hierarchical scheduling system to manage concurrent requests, allocate CPU threads and GPU VRAM, and orchestrate background maintenance tasks. The core request queue operates as an asynchronous FIFO: incoming requests check whether the inference engine is IDLE; if so, the request is popped and processed; if BUSY, the request is held with an HTTP 202 Accepted status.

Worker thread allocation queries `os.cpu_count(logical=False)` and reserves one core for the OS and API responsiveness, allocating the remainder to the llama.cpp backend via OpenMP thread pooling. Background tasks -- database compaction (SQLite VACUUM every five minutes) and plugin registry scanning (hourly hot-reload) -- run through a lightweight `apscheduler` framework, ensuring they never interfere with active inference.

## Key Points

- FIFO queue for inference requests with 202 Accepted for queued jobs
- CPU thread allocation: `max_cores - 1` reserved for llama.cpp, 1 core for OS/API
- Background scheduler handles SQLite compaction (5 min) and plugin hot-reload (1 hour)
- GPU VRAM tracked via NVML for concurrent GPU task coordination
- Engine state is locked to BUSY during inference, preventing memory overload

## Related
- [[Working]]
- [[Pipelines]]
- [[Technical Architecture]]
- [[SQLite]]
