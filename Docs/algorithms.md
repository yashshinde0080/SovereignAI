# Core Algorithms

## 1. Overview
The efficiency of SovereignAI Edge rests entirely on its custom algorithms designed to squeeze maximum performance out of severely limited hardware while remaining entirely ==offline==. 

## 2. Adaptive Memory Allocation Algorithm
Ensures the software never crashes due to ==OOM (Out of Memory)==, a common issue with local LLM runners.

**Algorithm Logic:**
1. Upon model load request, parse `.gguf` header to calculate total tensor bytes (ModelSize).
2. Query OS for `Free_System_RAM` and `Free_VRAM`.
3. If `Free_VRAM > ModelSize`, execute entirely on GPU.
4. If `Free_VRAM + Free_System_RAM > ModelSize * 1.1` (10% buffer for OS safety), execute via ==FullRAM== CPU engine.
5. If `Free_System_RAM < ModelSize`, initialize ==LayerStream== Algorithm.

## 3. LayerStream Execution Algorithm
Traditional LLMs require the entire model graph in memory. LayerStream mathematically breaks the graph.
1. The ==KV Cache== for the active context is locked in RAM.
2. A sliding buffer window is allocated in RAM (sized for exactly 2 neural network layers).
3. The inference thread reads `Layer N` from the NVMe SSD into the buffer.
4. Matrix multiplication occurs against the KV cache.
5. While `Layer N` computes, `Layer N+1` is asynchronously pre-fetched into the second buffer from SSD.
6. Once `Layer N` finishes, its buffer is discarded/overwritten by `Layer N+2`, and execution moves to `Layer N+1`.
Result: ==Disk I/O== is hidden behind compute time, allowing massive models to run on 8GB laptops.

## 4. Context Window Sliding Mechanism
When a conversation exceeds the model's max context limit (e.g., 8192 tokens):
1. **Anchor pinning:** The system prompt (first N tokens) is pinned and never discarded.
2. **Sliding:** The oldest 50% of the conversation history is pruned out of the prompt array.
3. **KV Forgetting:** The KV cache indices mapped to the pruned tokens are invalidated and overwritten by new tokens.

## 5. Algorithmic Flow Visual
```text
============== Adaptive Engine Allocation ==============

    Input: Load "Model_70B.gguf" (Size: 40GB)
                     |
            [ Profiler Sweep ]
     MemAvailable = (RAM_FREE: 16GB)
                     |
       Is (16GB > 40GB) ? ---> NO
                     |
             [ Trigger LayerStream ]

============== LayerStream Algorithm Workflow ===========

     [ System RAM (KV Cache + Layer Buffer Array) ]
     
     +-----------------+      +-----------------+
     | Buffer A (Wait) |      | Buffer B (Read) |
     +--------+--------+      +--------+--------+
              |                        ^
              v                        |
     Compute Layer N --------- Async SSD Read Layer N+1
              |
         Wait/Swap
              |
     +--------+--------+      +-----------------+
     | Buffer A (Read) |      | Buffer B (Wait) |
     +--------+--------+      +--------+--------+
              ^                        |
              |                        v
     Async SSD Read ------ Compute Layer N+1
       Layer N+2
```

## See Also
- [[Engine Algorithms]] — Pseudocode for FullRAM and LayerStream
- [[Engines Overview]] — Architecture and memory lifecycle
- [[Gaps]] — Research gaps in memory-constrained inference
- [[Implemented Algorithms]] — All 25 algorithms across the platform
