# LayerStream Performance — Design Decision — 2026-08-16

Office-hours session outcome. Topic: LayerStream runs at 0.40 tok/s; a proposed
fix list claimed disk I/O is the bottleneck. This doc records the diagnosis,
the agreed premises, the chosen approach, and what is explicitly parked.

## Problem statement

LayerStream, the low-RAM layer-by-layer engine, generates at 0.40 tok/s on the
dev box. The proposed fix list (quantize weights, GDS/O_DIRECT, deeper
prefetch, batched layer reads, TurboQuant KV, LLM-in-a-Flash windowing)
asserts "disk read = bottleneck, not math. Fix I/O, not compute."

## Evidence

Measured on `bench-Qwen-Qwen3.5-0.8B` (reviews/benchmark-2026-08-14.md):

| Metric | CPU (08-14) | GPU + fla (08-15) |
|---|---|---|
| Tokens/second | 0.40 | 0.38 |
| Disk read time | 7.7 s (9%) | 5.0 s (6%) |
| Compute time | 77.8 s (98%) | 83.1 s (98%) |

Code reading (backend/app/engines/layerstream/):

- `loader.py` runs a `ThreadPoolExecutor(max_workers=prefetch_depth)`; futures
  for layers i+1..i+3 are submitted before layer i computes
  (`layer_executor.py` main loop). I/O already overlaps compute. Wall time
  equals compute time, which proves the overlap: there is no
  read-compute-read serial pipeline to fix.
- int4/int8 quantization is already implemented: `dequantize_on_device` +
  `quant_config.json`, and the default bench model is already int4 (339 MB).
- `mmap_loader.py` and `prefetch.py` are legacy/duplicate paths, not the
  routed engine.

## Diagnosis

1. Compute is 98% of wall time. The I/O fix list targets ~10% and cannot
   produce the claimed 4x.
2. On GPU, the Qwen3.5 hybrid linear-attention fast path never engaged
   (`causal-conv1d` unbuildable on this Windows box), so all 18
   linear-attention layers ran the pure-torch fallback at ~CPU speed.
3. On CPU, raw torch eager per-layer forward (assign weights, dequant,
   forward, offload, per layer, per token) is structurally 10-100x slower
   than ggml's fused kernels. llama.cpp (the status quo, free, mature) gets
   10-50 tok/s on the same box.
4. The I/O fix list is the second-order problem. It becomes the right list
   only after compute drops to a fraction of wall time.

## Agreed premises

1. Compute, not I/O, is the bottleneck. "Quantize to Q4 -> 4x speedup" does
   not fire while compute dominates.
2. A Python/torch layer-by-layer engine cannot beat llama.cpp on the same
   hardware for decode. Torch LayerStream cannot be the default low-RAM path.
3. The shippable wedge is 3-8B Q4 in RAM (FullRAM). LayerStream goes
   experimental and off the marketing surface until a real compute path
   exists.
4. The I/O fix list is deferred, not wrong. TurboQuant (KV compression) is a
   separate memory goal: it buys RAM and long context, not tok/s.

## Decision: Approach A + B

**A — Ship the honest wedge (this week).** FullRAM Q4 3-8B is the product.
LayerStream off by default, labeled experimental in the UI. Benchmark the
FullRAM Q4 path on the 8 GB box so the pitch has real numbers.

**B — llama.cpp-backed offload (next, ~1-2 weeks).** When a model exceeds
RAM, route decode through the already-vendored `ik-llama-cpp-python` with
mmap + Q4_K_M instead of torch LayerStream. Beyond-RAM becomes usable:
still slower than in-RAM, but 10-50x faster than torch LayerStream.

**C — torch compute-path fix (parked).** torch.compile / CUDA graphs, fused
assign-forward-offload, non-hybrid GPU models. Reopens only if a spike shows
torch gets within ~3x of llama.cpp, or as a research lane, never as the
product default.

## Explicitly out of scope (parked)

- Q4/Q8 weight quantization of torch LayerStream splits (already supported,
  no tok/s impact while compute dominates)
- Deeper prefetch windows, batched/grouped layer reads
- GDS / O_DIRECT / io_uring
- LLM-in-a-Flash windowing and row/column bundling
- TurboQuant KV compression (separate memory/long-context goal, keep on
  roadmap)
- causal-conv1d / Linux CUDA fast-attention setup

Revisit trigger: a paying user requests beyond-RAM models before B ships, or
a compute spike lands within ~3x of llama.cpp. Per-item triggers, measured
criteria, and a sequencing rule live in the canonical record:
reviews/parked-io-fixes-2026-08-16.md.

## Risks

- FullRAM Q4 on an 8 GB CPU-only box is still slow for 8B models. The A
  benchmark decides whether the pitch says "3B fast, 8B usable, both honest."
- llama.cpp offload past RAM is proven but slow. B sets expectations in the
  UI rather than hiding it.
- Positioning: competitors (Ollama, LM Studio) already own beyond-RAM
  users. SovereignAI's differentiation must be integration (portable USB,
  UI, plugins, privacy), not raw engine speed.

## Benchmark results (measured 2026-08-16)

FullRAM Q4, `qwen2.5-0.5b-instruct-q4_k_m.gguf` (469 MB), same box/prompt as
the LayerStream ref. See reviews/benchmark-fullram-2026-08-16.md.

| Metric | FullRAM CPU | FullRAM CUDA | LayerStream ref |
|---|---|---|---|
| Tokens/second | 3.84 | 7.03 | 0.40 |
| Load time | 63.4 s | 66.8 s | 4.4 s |
| Peak RAM delta | +1.93 GB | +2.25 GB | 2.30 GB |

Outcome: FullRAM is ~10-18x faster than LayerStream and keeps the memory
bound, but transformers dequantizes GGUF to fp32/fp16, so RAM scales at ~4x
file size. Projection kills the "3-8B Q4 on 8GB RAM" claim: 3B Q4 needs
~7-12 GB, 8B Q4 ~16-19 GB. The realistic FullRAM ceiling on this box is
~1B Q4. Only a llama.cpp-style backend (B) keeps weights quantized in RAM
(3B ~2 GB, 8B ~5 GB), so B is now required for the headline claim, not
optional.

## What I noticed

The builder has domain expertise (built the layer-streaming engine, knows
GGUF/quantization/offload literature), showed agency (measured, benchmarked,
re-positioned already), and demonstrated taste (honest read of the numbers,
"memory economics work as designed"). The signal to watch: the pull toward
engine-deep work is strong; the discipline here is shipping the wedge first.

## The Assignment (completed 2026-08-16)

Run `backend/benchmark_layerstream.py`-style benchmark on the **FullRAM Q4**
path (3-8B GGUF on the 8 GB box) and record real tok/s + peak RAM. One
session, one model. The pitch gets rewritten off those numbers: if 3B Q4
chats at usable speed, that is the launch claim. LayerStream stays
experimental until B (llama.cpp offload) lands.

Result: done in reviews/benchmark-fullram-2026-08-16.md via new runner
`backend/benchmark_fullram.py`. 0.5B Q4 measured at 3.84 tok/s CPU / 7.03
CUDA. The 3-8B claim does not fit via transformers (fp32/fp16 dequant ~4x
file size); pitch corrected to "0.5-1B Q4 in RAM, 3-8B Q4 via llama.cpp
backend (B)".

## Status

DONE_WITH_CONCERNS — design approved; FullRAM benchmark measured; Approach B
spike validated (see reviews/spike-llamacpp-offload-2026-08-16.md): llama.cpp
holds Q4 at 1.0x file size in RAM and decodes at 24 tok/s on the same box
(60x LayerStream, 6x transformers CPU). Open items: engine-router wiring for
beyond-RAM GGUF -> llama.cpp. 3B Q4 end-to-end measured 2026-08-16: 5.44
tok/s, 2.3 GB RSS on the 8 GB box (see reviews/spike-llamacpp-offload-2026-08-16.md).

## Implementation status (Approach A config, 2026-08-16)

Landed: MemoryManager.suggest_mode now uses honest FullRAM residency (~4x Q4
file in RAM, measured; ~2x full repos) so auto picks FullRAM only for models
that fit and LayerStream otherwise. LayerStream is flagged experimental:
engine attr, load-result and /v1/models/current fields, server log warning,
and UI badges (mode switcher, models table, settings select). Also fixed a
pre-existing crash in suggest_mode (``a and b or c`` precedence: None
metadata raised AttributeError on the ``or`` arm). 112 backend tests pass;
frontend typecheck clean. Still open: Approach B router wiring (beyond-RAM
GGUF -> llama.cpp). The 3B Q4 end-to-end run is done: 5.44 tok/s at 2.3 GB
RSS on the 8 GB box.
