# Parked I/O Fix List — Revisit Triggers — 2026-08-16

Origin: office-hours session on LayerStream 0.40 tok/s (design-layerstream-perf-2026-08-16.md).
"Parked" does not mean wrong. It means **second-order**: each item targets the
part of wall time that is currently hidden behind compute.

## Why the list is parked (the measured stack)

`reviews/benchmark-2026-08-14.md`, same box, Qwen3.5-0.8B split:

| | CPU (08-14) | GPU + fla (08-15) |
|---|---|---|
| Disk read | 7.7 s (**9%**) | 5.0 s (**6%**) |
| Compute | 77.8 s (**98%**) | 83.1 s (**98%**) |

I/O is already overlapped behind compute by the ThreadPoolExecutor prefetch in
`layer_executor.py` / `loader.py` (wall time ≈ compute time proves it). The
fix list optimizes the 9%. It becomes the right list only after compute stops
dominating. That ordering is enforced by the triggers below: **item N+1 does
not open until item N has landed and re-measured.**

Umbrella trigger (design doc): *a paying user requests beyond-RAM models before
Approach B (llama.cpp offload) ships*, or *a compute spike lands LayerStream
within ~3x of llama.cpp on the same hardware* (24 tok/s reference, see
reviews/spike-llamacpp-offload-2026-08-16.md). Either reopens this whole list.

## The items

### 1. Q4/Q8 quantization of torch LayerStream splits
- **Status:** parked 2026-08-16. Supported already (`dequantize_on_device`,
  `quant_config.json`, `bench-*-int4/int8` splits exist).
- **Why parked:** quantizing shrinks disk read (already hidden) and RAM
  (LayerStream is already RAM-bounded). Measured: no tok/s impact while
  compute is 98% of wall.
- **Revisit trigger:** LayerStream compute < 50% of wall time in a fresh
  benchmark (compute no longer dominates). Then quantize splits to cut the
  now-visible I/O and RAM.
- **On trigger:** re-split a bench model at int4, re-run
  `benchmark_layerstream.py`, compare wall-time breakdown.

### 2. Deeper prefetch windows / batched group reads
- **Status:** parked 2026-08-16. `prefetch_depth` (default 3) and per-layer
  safetensors files in `loader.py` unchanged.
- **Why parked:** prefetch already hides I/O; the window is not the binding
  constraint.
- **Revisit trigger:** a benchmark shows disk read > 30% of wall time
  (I/O visible again), or the engine moves to a host where layers are
  tiny-but-numerous (many small opens dominate).
- **On trigger:** raise `prefetch_depth`, batch small layers into one
  sequential read, re-measure.

### 3. GDS / O_DIRECT / io_uring
- **Status:** parked 2026-08-16. Platform gate: GDS is Linux + NVIDIA +
  NVMe; io_uring is Linux. The dev box is Windows.
- **Why parked:** NVMe bandwidth is not the bottleneck, and the platform
  isn't available.
- **Revisit trigger:** item 2 has landed AND the engine runs on Linux with a
  real NVMe AND I/O is still > 30% of wall.
- **On trigger:** measure raw NVMe seq-read first; only if < 1 GB/s pursue
  queue-depth / async-IO work.

### 4. LLM-in-a-Flash windowing (neuron reuse across layers)
- **Status:** parked 2026-08-16.
- **Why parked:** it reduces I/O *volume*, and I/O volume is not the binding
  constraint. It also only pays off for models whose weights overflow RAM
  (30B+ class), where decode is bandwidth-bound regardless.
- **Revisit trigger:** Approach B (llama.cpp offload) is wired, users are
  running beyond-RAM models, and its throughput is deemed too slow to ship.
  Windowing is then the research lane.
- **On trigger:** prototype against the biggest GGUF on the box; compare
  bytes-read-per-token before/after windowing.

### 5. TurboQuant KV compression
- **Status:** parked as a *tok/s* item; **still on the roadmap as a memory
  item**. Partial implementation exists (`turboquant_config` path in
  `layer_executor.py`, 3-bit KV).
- **Why parked:** KV compression buys RAM and long context, not decode speed
  on the measured workloads.
- **Revisit trigger:** a supported model hits RAM/VRAM overflow on its KV
  cache at >= 8K context (long-context use case), or long-context is a pitch
  requirement.
- **On trigger:** finish TurboQuant wiring for the non-hybrid KV path,
  benchmark context-length ceiling at fixed RAM.

### 6. causal-conv1d / Linux CUDA fast-attention
- **Status:** parked 2026-08-16. Unbuildable on Windows (no wheels, no
  nvcc/MSVC). The Qwen3.5 hybrid fast path never engaged, so GPU ran at
  ~CPU speed.
- **Why parked:** even fixed, torch layer-by-layer stays behind llama.cpp on
  the same box; B covers hybrid models with its own kernels.
- **Revisit trigger:** a Linux CUDA box joins the dev loop AND the torch
  LayerStream path is being resurrected as the default for some model class.
  If B ships first, this item likely dies: llama.cpp already runs
  hybrid/linear-attention models.
- **On trigger:** install `causal-conv1d` + `flash-linear-attention`, re-run
  the 08-15 GPU benchmark, compare against llama.cpp on the same box.

## Sequencing rule

Reopen in order, one at a time. After each landing, re-run the wall-time
breakdown before opening the next. Do not stack items 2-4 simultaneously —
they all optimize the same hidden 9% and cannot be evaluated together.
