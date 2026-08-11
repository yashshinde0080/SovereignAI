# LayerStream Engine — Improvement Design (Office Hours, 2026-08-11)

> Builder-mode research + design doc. No code was written for this document. All
> "current state" claims are from reading `backend/app/engines/layerstream/`
> and `backend/app/core/` on this commit. Effort is CC-time (this repo is AI-driven).

## TL;DR

LayerStream is a genuinely clever idea (stream one layer at a time so a 70B runs
on 8GB RAM) with one fatal contradiction and a pile of untapped wins:

1. **The loader caches every layer in CPU RAM permanently** (`loader.py`), so a
   70B model is fully resident after the first pass. The "memory-bounded" claim
   is currently false past the first forward pass.
2. **Prefetch depth is 1** (only the next layer, single future) — the disk is the
   bottleneck and we're not hiding its latency.
3. **A whole second architecture exists as dead code**: `scheduler.py`,
   `prefetch.py`, `mmap_loader.py` (with mock offsets!), `memory.py`. None of it
   is wired into the hot path.
4. **Quantization stops at per-tensor int8, dequantized on CPU to float32** —
   doubles RAM and burns CPU; GGUF Q4-style would halve per-layer read size.
5. **Big wins available**: mmap + madvise page-cache streaming, deep prefetch,
   GPU-side dequant, bf16 on CPU, speculative decoding, chunked prefill.

Ranked recommendations (impact × effort, CC time):

| # | Change | Impact | Effort | Axis |
|---|--------|--------|--------|------|
| 1 | Bounded LRU cache in `LayerWeightLoader` | ⭐⭐⭐ (fixes the core contradiction) | ~30 min | Memory |
| 2 | Deep prefetch pipeline (2-3 ahead) | ⭐⭐⭐ (hides disk latency) | ~45 min | Throughput |
| 3 | Dequant on GPU, keep int8 in RAM | ⭐⭐⭐ (halves RAM + CPU cost) | ~45 min | Memory/Perf |
| 4 | GGUF-style 4-bit per-layer storage (Q4_K_M-ish) | ⭐⭐⭐ (halves disk bytes/read) | ~1-2 h | Throughput |
| 5 | `mmap` layer reads + `madvise(MADV_WILLNEED)` | ⭐⭐ (OS page cache does the work) | ~1 h | Throughput |
| 6 | bf16 on CPU (comment says it, code uses fp32) | ⭐⭐ (free-ish on modern CPUs) | ~10 min | Throughput |
| 7 | Delete dead code (scheduler/prefetch/mmap/memory) | ⭐ (clarity) | ~20 min | Health |
| 8 | Speculative decoding (draft + verify) | ⭐⭐⭐⭐ (fewer full passes) | ~3-4 h | Throughput |
| 9 | Wire `update_ram()` into hot path + load/compute split in tracker | ⭐ (measure first) | ~15 min | Health |
| 10 | Chunked prefill | ⭐⭐ (bounds prefill RAM) | ~1 h | Memory |

---

## 1. Current state (measured from code)

### Hot path (what actually runs)

```
LayerStreamEngine.generate()          executor.py
  └─ executor.execute_forward()       layer_executor.py
       for each layer i:
         loader.prefetch_async(layer i+1)   ← depth-1 double buffer
         loader.get_weights(layer i)        ← reads + CACHES FOREVER
         assign_weights(layer)              ← non_blocking copy to device
         layer(hidden, mask, cache, ...)    ← eager attention
         offload_weights(layer)             ← frees device memory
       norm → lm_head → logits
```

Key facts:

- **`LayerWeightLoader.cpu_cache` never evicts** (`loader.py:21,46`). `clear_cache()`
  is only called on `unload()`. After one prefill pass, every layer's weights sit
  in CPU RAM. A 70B fp16 model = ~140GB RAM held permanently. The doc claim
  ("VRAM = 1 layer, RAM = KV cache") only holds for the *first* pass.
- **Prefetch is single-future double-buffering** (`loader.py:37-43`): prefetch
  layer i+1 while computing layer i. Depth 1 means one disk read in flight.
- **int8 quant exists but dequantizes on CPU to float32** (`loader.py:27-33`):
  `tensor.to(float32) * scale` on every load, kept as float32 in RAM. Doubles
  the footprint of quantized models and adds CPU work.
- **KV cache stays on GPU** (`kv_cache.py:66-69`: "Keep on GPU for speed"). Long
  context competes with weights for GPU memory — the opposite of the LayerStream
  premise.
- **compute_dtype**: fp16 on CUDA, **fp32 on CPU** (`layer_executor.py:31`) —
  even though the comment says "Use bfloat16 or float32 for CPU-only runs",
  bf16 is never selected.
- **Attention mask + position ids rebuilt every forward call** (`layer_executor.py:70-84`).
- **`BenchmarkTracker.update_ram()` exists but is never called** in the hot path
  (`benchmark.py:27`), so peak-RAM reporting is incomplete.

### Dead code (verified unwired)

| File | Class | Status |
|------|-------|--------|
| `scheduler.py` | `LayerScheduler` (LRU eviction, states) | never imported outside itself |
| `prefetch.py` | `PrefetchQueue` (async buffers, priorities) | never imported |
| `mmap_loader.py` | `MMapLoader` | `_mock_layer_offsets()` = fabricated demo data; **unsafe** (would read garbage) |
| `memory.py` | `MemoryManager`, `CPUOffloadedCache` | never imported; the factory uses `app.core.memory_manager` instead |

`engine_factory.py` imports only `LayerStreamEngine` + `app.core.memory_manager`.
Nothing imports `scheduler.py`, `prefetch.py`, `mmap_loader.py`, or
`layerstream/memory.py`.

### Hybrid/stateful models

`layer_executor.py` already detects `linear_attention` layer types (Qwen3.5-style
hybrids) and uses a GPU-resident `StatefulCache`. TurboQuant is skipped for these.
This path is newer and less exercised — improvements below target the standard
full-attention path, with hybrid noted where relevant.

---

## 2. Throughput axis (tokens/sec)

### 2.1 Deep prefetch pipeline — `loader.py` (⭐ impact, ~45 min)

Current: one `ThreadPoolExecutor(max_workers=1)` future. Fix: a small ring buffer
of N futures (N = 2-3), prefetching layers `i+1 .. i+N` as compute proceeds.

```python
# shape of the change — not code to ship verbatim
self._prefetched = deque()           # up to N futures
def prefetch_ahead(self, base_idx):  # called once per layer
    for j in range(1, self.depth + 1):
        if base_idx + j not in self._scheduled:
            self._prefetched.append(executor.submit(self._load_file, path(base_idx + j)))
```

Why it works: on PCIe Gen3 NVMe a 7B fp16 layer is ~140-300MB ≈ 100-200ms of
read. With depth 3 the disk stays saturated while GPU computes. Disk-bound
engines are fixed by *more reads in flight*, not faster reads.

Pitfall: N must be tuned to RAM budget — each in-flight layer costs one layer's
worth of CPU RAM. That's exactly what change #1 (bounded cache) should control.
`ponytail:` depth 3 fixed; make it a config knob only if a benchmark shows it
matters.

### 2.2 mmap layer reads + madvise — new small module (⭐⭐, ~1 h)

Replace `safe_open()`-per-layer with a single memory-mapped safetensors file per
layer (`mmap` + `tensor.numpy()` views) or one GGUF-style mmap. The OS page
cache then does the prefetching, eviction, and dedup for free — and the
"cached forever in RAM" problem becomes "RAM is reclaimable by the OS".

- `mmap_loader.py` already exists but is a **mock with fabricated offsets** — do
  not build on it; write the real thing (or delete the mock first).
- Simplest first step: keep per-layer `.safetensors` files, mmap each on first
  read, `madvise(MADV_WILLNEED)` the range for the next layer. llama.cpp's GGUF
  path is the reference implementation of this exact idea.
- Correctness note: `torch.frombuffer` on mmap needs care with alignment and
  safetensors header offsets; a `copy()` is only needed for int8-dequant tensors.

### 2.3 GPU-side dequantization — `loader.py` + `layer_executor.py` (⭐⭐⭐, ~45 min)

Current int8 path: CPU dequant to float32 (2 bytes → 4 bytes in RAM), then copy
to device. Fix: keep int8 + per-tensor scale in RAM (half the bytes), dequant on
the GPU as part of `assign_weights`:

```python
# loader returns int8 + scale; assign does the dequant on device
dev = state_dict[name].to(device, non_blocking=True)      # int8
dev = dev.to(torch.float32) * scale.to(device)            # dequant on GPU
```

This halves quantized RAM footprint AND removes CPU dequant work from the
critical path. The existing `_quantize_int8` splitter output is already
(int8, `.scale`) pairs — no splitter change needed.

### 2.4 GGUF-style 4-bit storage — `splitter.py` (⭐⭐⭐, ~1-2 h)

Per-tensor int8 is the floor of the current design. 4-bit group-wise (Q4_K_M
style, group 32/128) halves per-layer bytes again: 7B fp16 ≈ 14GB → int8 ≈ 7GB →
Q4 ≈ 3.5GB. For a disk-bound engine, bytes-per-layer is the throughput currency.

Options (cheapest first):
1. `torchao` int4 weight-only (group-wise, GPTQ-style kernels) — least new code,
   but adds a dependency.
2. Hand-rolled group-wise int4 in `splitter.py` + GPU dequant in `assign_weights`
   — more code, zero deps, matches the existing "own the kernels" style of this
   package.
3. GGUF Q4_K_M via existing GGUF support paths (`executor.py` already handles
   `.gguf` tokenizers) — biggest change, reuses llama.cpp's proven codec.

`QuantConfig` already carries `group_size` and `zero_point` fields — the schema
was designed for this; only the kernel is missing.

### 2.5 bf16 on CPU — `layer_executor.py:31` (⭐⭐, ~10 min)

```python
self.compute_dtype = torch.float16 if self.device.type == "cuda" else torch.float32
# → if CPU supports bf16 (AVX512-BF16 / AMX): bfloat16, else float32
```

The comment already says bf16 is the right CPU choice; the code never does it.
bf16 halves CPU memory bandwidth pressure (fp32 4B → bf16 2B) on modern cores
and on CPU-only boxes memory bandwidth is often the real ceiling.

### 2.6 Speculative decoding — new (⭐⭐⭐⭐, ~3-4 h)

Each decoded token currently costs a full N-layer pass over disk. Speculative
decoding (draft K tokens with a tiny model, verify in one pass, accept the
prefix) cuts the number of passes per accepted token. With layer streaming the
win is bigger than usual because every saved pass also saves N disk reads.

- Draft model: a small local model already on the machine (the repo has 0.5B-70M
  models in HF cache), or an n-gram draft (zero RAM cost).
- Verification reuses the existing `execute_forward` with K-token input
  (prefill-shaped) — the machinery already exists.
- This is the single highest-leverage change but also the largest. Ship after
  #1-#4 so the per-pass cost is already minimized.

### 2.7 Micro: cache the attention mask & position ids — `layer_executor.py`

Rebuilding `_create_attention_mask` + `position_ids` per call is pure waste.
Cache by `(seq_length, past_length)` shape; invalidate on change. ~15 min,
small but real on CPU where the mask build is non-trivial.

---

## 3. Memory-bounded axis (the contradiction)

### 3.1 Bounded LRU cache — `loader.py` (⭐⭐⭐, ~30 min) — DO FIRST

The single most important change. The engine's identity is "weights stream, RAM
stays small" — but `cpu_cache` grows to the full model. Fix:

```python
# cache only what the pipeline needs: current + prefetch depth + pinned (embed/norm/lm_head)
self.cache_max = 1 + self.prefetch_depth + len(self._pinned)
# evict LRU on insert past the cap
```

- Pin `embed`, `norm`, `lm_head` (tiny, used every pass — re-reading them each
  token is also wasted I/O).
- Evict any `layer_*` beyond the window with LRU. `LayerScheduler` in
  `scheduler.py` already implements exactly this state machine — wire it in or
  copy its 20 lines, then delete it.
- This makes LayerStream honest again: RAM ≈ (depth+1) layers + KV. That is the
  headline claim of the engine, and currently it's false.

### 3.2 KV cache residency — `kv_cache.py` (⭐⭐, ~1 h)

Current: `KVCacheManager.set()` keeps KV on GPU. For long context on a small GPU
that collides with the active layer's weights. Options:

- **CPU-offload KV when GPU is tight** (`CPUOffloadedCache` exists in
  `memory.py` and is dead — wire it or delete it). Move KV to CPU and stream
  back per layer, mirroring the weight strategy. Cost: extra H2D/D2H per layer
  per token; the `ProxyList` machinery already does lazy device movement.
- **KV compression**: TurboQuant exists but is **gate-blocked** (see
  `reviews/autoplan-report-2026-08-09.md` — fails ppl gate on Qwen2-0.5B/Pythia,
  reference codebook can't pass either). Do not re-enable until the gate passes.
- **Sliding window / eviction** for very long context is the pragmatic lever
  that needs no new quantizer.

### 3.3 Chunked prefill — `executor.py` (⭐⭐, ~1 h)

Prefill currently processes the whole prompt in one `execute_forward`, which
builds the full KV at once. Chunking the prompt (e.g. 512-token chunks, carrying
KV) bounds peak KV RAM and enables interleaving prefill with decode (streaming
first tokens earlier). The existing chunked-loop pattern in `accuracy_eval.py`
is a reference.

---

## 4. Quantization axis (combined view)

The full ladder, each step halving disk bytes/read:

| Step | Bytes (7B) | Change | Where |
|------|-----------|--------|-------|
| fp16 (current default) | ~14GB | — | `splitter.py` |
| int8 per-tensor (exists) | ~7GB | + GPU dequant (#2.3) | `splitter.py` + `layer_executor.py` |
| int4 group-wise (Q4_K_M-ish) | ~3.5GB | new codec | `splitter.py` + `assign_weights` |
| KV compression | KV only | **gated** on accuracy gate | `shared/turboquant/` |

Rule for this engine: **quantize before you optimize the kernel.** Disk bytes
are the bottleneck; every bit removed from a layer doubles the tokens/sec ceiling
at the same prefetch depth. And with #3.1 (bounded cache) smaller layers also
mean more layers can stay resident — a double win.

---

## 5. Code health axis

1. **Delete or wire the dead layerstream modules** (`scheduler.py`, `prefetch.py`,
   `mmap_loader.py`, `memory.py`). The mock `MMapLoader._mock_layer_offsets` is
   a footgun — if anyone ever calls it, it reads garbage offsets. This is
   `AGENTS.md`'s "3 nearly-duplicate engines" cleanup, mostly done — the
   remaining duplicates are these 4 files.
2. **Wire `BenchmarkTracker.update_ram()` into the hot path** and split
   `disk_read_time` from `compute_time` (tracker already has both fields;
   `generate()` only reports `tokens_per_second`). You cannot tune what you
   don't measure; the load-vs-compute split is the single most useful number
   for every change above.
3. **Add a `--layers` sweep to `benchmarks/`** reusing `benchmark.py`: tokens/sec
   and peak RAM at prefetch depth 1/2/3, int8 on/off, mmap on/off. That makes
   each of the above changes an A/B, not a leap of faith.

---

## 6. Suggested phasing

**Phase A — make the claim true (~1.5 h CC):** #3.1 bounded LRU cache + #2.1
deep prefetch + #2.7 mask caching. Result: honest memory-bounded streaming,
disk stays saturated. This is the "engine does what it says" pass.

**Phase B — shrink the bytes (~2-3 h):** #2.3 GPU dequant + #2.5 bf16 on CPU +
#2.4 int4 codec. Result: per-layer read halves → tokens/sec roughly doubles.

**Phase C — cut the passes (~4 h):** #2.6 speculative decoding + #3.3 chunked
prefill. Result: biggest end-user latency win, built on the now-cheap pass.

**Phase D — hygiene (~1 h):** #2.2 real mmap loader, #5.1 delete dead code,
#5.2/#5.3 measurement. Land before any of A-C goes in.

---

## 6.5 Phase A results (2026-08-11) — implemented & measured

All of Phase A shipped: bounded LRU cache + pinned paths in `LayerWeightLoader`,
prefetch depth 3 threaded through `LayerExecutor`, cached attention mask, and a
benchmark harness (`backend/benchmarks/layerstream_phase_a.py`, per-config fresh
subprocesses). Qwen2-0.5B, 24 layers, `bench-*` split dirs in `workspace/offload_cache/`.

| config | pass1 | pass3 (steady) | cached MB | RSS delta MB |
|---|---|---|---|---|
| fp16: depth=1, unlimited (before) | 0.06s | 0.00s | 682.6 | 2.4 |
| fp16: depth=3, bounded (after) | 0.03s | 0.02s | **256.0** | 1.9 |
| int8: depth=1, unlimited (before) | 1.15s | 0.00s | **1365.3** | 1433 |
| int8: depth=3, bounded (after) | 0.64s | 0.66s | **227.5** | 676 |

> The int8 rows reflect the pre-Phase-B loader, which dequantized to fp32 on CPU
> (1365MB = 4.1 bytes/elem). Phase B re-baselines int8 to the raw stored form —
> 341MB unlimited / 242MB bounded (see §6.6).

**Two important findings beyond the numbers:**

1. **safetensors `get_tensor(device="cpu")` returns mmap-backed views.** RSS barely
   moves for the fp16 path even when 682MB is "cached" — the OS reclaims file
   pages. So the pre-Phase-A unlimited cache was *less catastrophic* than the
   doc's "70B = 140GB RAM" claim for fp16: the OS can evict those pages. The
   bounded cache still matters because (a) it caps the tracked footprint and
   (b) the **int8 path dequantizes to private fp32 copies** (`loader.py`
   `tensor.to(float32) * scale`), which ARE private RAM — 1365MB cached vs
   227MB bounded is the real win, and 70B-scale int8 would be ~35GB held vs a
   bounded window.
2. **The steady-state pass cost (0.02s fp16 / 0.66s int8) is the honest price of
   streaming.** Pre-Phase-A decode was 0.00s because everything was cached; the
   bounded cache re-reads layers from disk/page-cache per pass. That is
   LayerStream's intended design — the disk-bound trade is the feature.

Also fixed along the way: `gc.collect()` per eviction cost ~1.5s/pass in the
bounded path (tensors are refcounted; Python GC chases cycles, not tensors) —
removed. New tests: `backend/tests/test_layerstream_loader.py` (9 tests: budget
eviction, pinned survival, LRU order, prefetch depth bounds, future reaping,
mask caching/cap). Full suite: **95 passed**.

## 6.6 Phase B results (2026-08-11) — bytes per layer, measured

Phase B shipped all three changes: (1) the loader stops CPU-dequantizing int8 —
RAM holds int8 + scale, dequant happens on the compute device inside
`assign_weights` (`dequantize_on_device()`); (2) a group-wise int4 codec
(Q4_0-style: group 32, packed nibbles, fp16 scales) in `splitter.py`; (3) a
bf16 capability gate (`_compute_dtype_for` — bf16 only on AVX512-BF16/AMX
CPUs; measured **163× slower** than fp32 on this AVX2 box, so default stays
fp32). Same harness, same model, same budget (largest layer × 4.5, floor 256MB):

| quant | stored form | full model in RAM (unlimited cache) | per-layer MB | vs fp16 |
|---|---|---|---|---|
| fp16 | fp16 | 682.6 MB | 28.4 | 1.00× |
| int8 *before Phase B* | CPU-dequantized fp32 | 1365.3 MB | 56.9 | 2.00× |
| int8 (Phase B) | raw int8 + scale | **341.4 MB** | 14.2 | 0.50× |
| int4 (Phase B) | packed nibbles + fp16 scales | **192.1 MB** | 8.0 | 0.28× |

**What this means:**

1. **Phase B cut the int8 RAM footprint 4×** (1365 → 341MB) just by not holding
   the dequantized fp32 copy — and the dequant compute moved off the CPU
   critical path onto the device. Per-layer read: 28.4 → 14.2MB.
2. **int4 halves int8 again**: 8.0MB/layer, 3.55× smaller than fp16. At 7B that
   ladder reads ~14GB → 7GB → 3.5GB, matching the doc's §4 table.
3. **The bounded cache is a non-event at int4 on 0.5B**: 192MB total < 256MB
   budget, so nothing evicts (before == after). The budget only bites when the
   model footprint exceeds it — which is exactly the 7B+ regime it exists for.
4. **Buffers guarded**: tensors < 1024 elems (e.g. `inv_freq`) stay fp — the
   int8/int4 codecs skip them, so RoPE buffers are never loaded raw as int
   tensors.

New tests (6): int4 roundtrip NMSE, int4 padded-cols roundtrip, int8
device-dequant ≡ old CPU path, raw-int8 stays in cache, numel gate, bf16
dtype gate. Full suite: **105 passed**.

## 7. Open questions for the builder

1. **GPU present?** All speedups above are CPU+SSD-oriented; if there's a real
   GPU (vs iGPU), attention should switch to SDPA/flash-attn first.
2. **int4 dependency tolerance?** `torchao` (fast, adds dep) vs hand-rolled
   (matches the package's own-the-kernels style, more code).
3. **Hybrid models (Qwen3.5 linear-attention):** the stateful path is newer —
   should the improvements cover it, or standard full-attention only for now?
4. **TurboQuant:** the accuracy gate blocks it (see the autoplan report). Sliding
   window + CPU-offload (#3.2) are the unblocked KV levers; worth confirming the
   gate stays the arbiter for any quantized-KV re-attempt.

---

## 8. Sources

- Code: `backend/app/engines/layerstream/` (all files read on 2026-08-11),
  `backend/app/core/engine_factory.py`, `backend/app/core/memory_manager.py`.
- Prior review: `reviews/autoplan-report-2026-08-09.md` (TurboQuant gate FAIL,
  affine tranche, reference-codebook probe).
- Landscape (web, 2026-08-11): llama.cpp GGUF mmap/madvise streaming; Petals
  layer pipelining; GGUF int4 quants (Q4_K_M/IQ); speculative decoding; chunked
  prefill + double-buffered prefetch (oLLM-style).
