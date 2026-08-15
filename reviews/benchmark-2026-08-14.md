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

## Follow-up: GPU + fla-only, 2026-08-15

Ran the same benchmark on this box's GTX 1650 (torch 2.5.1+cu124,
`triton-windows`, `flash-linear-attention 0.2.2`).

| Metric | CPU (08-14) | GPU + fla (08-15) |
|---|---|---|
| Tokens/second | 0.40 | 0.38 |
| Compute time | 77.8 s | 83.1 s |
| Disk read time | 7.7 s | 5.0 s |

**The kernels never engaged — zero delta.** transformers' Qwen3_5 fast path is
`all(causal_conv1d_fn, causal_conv1d_update, chunk_gated_delta_rule,
fused_recurrent_gated_delta_rule)` — fla alone is insufficient. Without
`causal-conv1d`, all 18 linear-attention layers ran the pure-torch fallback on
a 4 GB Turing card (≈ CPU speed), plus per-token RAM→VRAM layer swap overhead.

`causal-conv1d` is unbuildable here: no binary wheels on PyPI (22 sdists) or
GitHub releases (1080 assets, 0 Windows), and the box has no `nvcc`/MSVC.
Getting the real fast-attention delta requires a Linux CUDA box (prebuilt
wheels) or installing CUDA Toolkit + VS Build Tools globally — parked, not
abandoned.

Environment note: the backend venv now carries CUDA torch + triton-windows +
fla (all venv-local; `requirements.txt` pins are unchanged).

## Decision (from the 08-12 report)

Re-position the pitch to what the hardware actually supports: **"3-8B Q4
models on 8 GB RAM"**. That claim is true, useful, and measurable. The 70B
claim stays off the marketing surface until a benchmark says otherwise.
