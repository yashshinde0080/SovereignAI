# LayerStream Small-Model Benchmark — 2026-08-14

First end-to-end LayerStream measurement (CEO P1 / S2). Closes the unvalidated
"70B on 8GB" premise with real numbers instead of a story.

## Setup

- Machine: dev box, 8 GB RAM (~2 GB free), CPU-only (no CUDA)
- Model: `Qwen-Qwen3.5-0.8B` split (hybrid linear+full attention, 1.9 GB on disk in `workspace/offload_cache/`)
- Prompt: 10 tokens; generated 32 tokens, temperature 0.7
- Runner: `backend/benchmark_layerstream.py` (reproducible)

## Results

| Metric | Value |
|---|---|
| Load time | 4.4 s |
| **Tokens/second** | **0.40 tok/s** |
| Peak RAM | 2.30 GB (baseline 0.46 GB) |
| Disk read time | 7.73 s (864 layer loads, avg 9 ms) |
| Compute time | 77.83 s (98% of wall time) |

## Honest read

- **Sub-1 tok/s, as predicted.** 0.40 tok/s is unusable for interactive chat.
- Two caveats in the model's favor: (1) hybrid Qwen3.5 linear-attention falls
  back to slow torch kernels here (`fla` / `causal-conv1d` not installed), and
  (2) this is the smallest split model on disk. Still: the 70B-on-8GB headline
  is not supported by measurement.
- **Memory economics work as designed:** 1.9 GB model → 2.30 GB peak RSS.
  LayerStream does bound RAM; it just can't make CPU decode fast.

## Decision (from the 08-12 report)

Re-position the pitch to what the hardware actually supports: **"3-8B Q4
models on 8 GB RAM"**. That claim is true, useful, and measurable. The 70B
claim stays off the marketing surface until a benchmark says otherwise.
