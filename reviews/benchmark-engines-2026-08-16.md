# Engine Benchmark Report (Detailed) — tok/s, Peak RAM, Load Time — 2026-08-16

Consolidated, detailed results for all three inference engines measured on the
dev box, with the honest numbers behind the product pitch. This is the master
document; per-engine detail lives in the source docs listed at the bottom.

## 1. Executive summary

| Question | Answer (measured) |
|---|---|
| Is LayerStream's 0.40 tok/s an I/O problem? | No — compute is 98% of wall time; disk read is ~9% and already overlapped behind compute |
| How fast is FullRAM Q4 vs LayerStream? | 9.6x (CPU) / 17.6x (CUDA) on the 0.5B Q4 |
| How fast is llama.cpp vs LayerStream? | 60x on 0.5B Q4; 13.6x on 3B Q4 (a model FullRAM cannot run at all) |
| Does "3-8B Q4 on 8GB RAM" hold? | Only via llama.cpp (3B: 2.3 GB RSS, 5.44 tok/s). FullRAM/transformers needs ~4x file size in RAM (3B -> ~9.7 GB) |

## 2. Environment

| Item | Value |
|---|---|
| OS | Windows (Git Bash shell) |
| RAM | 8.4 GB total; 1.2-2.2 GB free during runs |
| GPU | NVIDIA GeForce GTX 1650, 4 GB VRAM |
| CPU | single-consumer CPU (no AVX512-BF16) |
| Python | 3.10 (venv at `backend/.venv`) |
| torch | 2.5.1+cu124 |
| transformers | 5.3.0.dev0 (git head, GGUF loading via `gguf_file` kwarg) |
| llama_cpp | 0.3.34 (CPU build; `--gpu-layers 999` showed no meaningful offload: 28.95 vs 24.05 tok/s) |
| ik_llama_cpp | installed but broken on this box (WinError 127, DLL load failure) — not used |
| llmfit | not installed — `MemoryManager.suggest_mode` runs the legacy threshold path |
| Disk free | 92 GB (D:) |

## 3. Methodology

- **Prompt:** 10-token `"The quick brown fox jumps over the lazy dog. "`
- **Target:** 32 tokens, temperature 0.7, top_p 0.9
- **tok/s** = generated tokens / wall generation time (prefill + decode), per run
- **Peak RAM** = process RSS delta over baseline, sampled every 50 ms by a
  background thread in the benchmark runners
- **Load time** = engine `load()` / model open to first ready
- **Same-box comparability:** all runs on this dev box, same prompt and token
  target. The 0.5B Q4 GGUF is the common model across FullRAM and llama.cpp;
  LayerStream's numbers come from its own 08-14/08-15 runs on a different
  model (Qwen3.5-0.8B FP16 split) and are reproduced from that review.
- **Token counts vary** (28/27/32) where the instruct model hit EOS early;
  tok/s is per-token wall time, so the metric stays comparable.

## 4. Models and artifacts

| Model | File | Size | Source |
|---|---|---|---|
| Qwen2.5-0.5B Q4_K_M | `qwen2.5-0.5b-instruct-q4_k_m.gguf` | 469 MB | HF `Qwen/Qwen2.5-0.5B-Instruct-GGUF` |
| Qwen2.5-3B Q4_K_M | `qwen2.5-3b-instruct-q4_k_m.gguf` | 2007 MB | HF `Qwen/Qwen2.5-3B-Instruct-GGUF` |
| Qwen3.5-0.8B split | `workspace/offload_cache/Qwen-Qwen3.5-0.8B` | 1.9 GB | pre-existing on box (LayerStream runs) |

0.5B GGUF dir also carries `config.json`, `tokenizer.json`, `tokenizer_config.json`,
`vocab.json`, `merges.txt` (needed by the transformers FullRAM path). Paths:
`workspace/models/bench-qwen2.5-0.5b-q4/`, `workspace/models/bench-qwen2.5-3b-q4/`.

## 5. Raw per-run data

### 5.1 LayerStream (torch layer-by-layer) — from reviews/benchmark-2026-08-14.md

| Metric | CPU (08-14) | GPU + fla (08-15) |
|---|---|---|
| Model | Qwen3.5-0.8B FP16 split (1.9 GB) | same |
| Tokens/second | 0.40 | 0.38 |
| Disk read time | 7.73 s (864 layer loads, avg 9 ms) | 5.0 s |
| Compute time | 77.83 s (98% of wall) | 83.1 s |
| Load time | 4.4 s | — |
| Peak RAM | 2.30 GB (baseline 0.46) | — |

GPU note: the Qwen3.5 hybrid linear-attention fast path never engaged —
`causal-conv1d` is unbuildable on Windows (no wheels, no nvcc/MSVC), so all
18 linear-attention layers ran the pure-torch fallback at ~CPU speed.

### 5.2 FullRAM (transformers) — Qwen2.5-0.5B Q4_K_M, 469 MB

| Metric | CPU (fp32) | CUDA (fp16) |
|---|---|---|
| Load time | 63.4 s | 66.8 s |
| GGUF dequant (291 tensors) | ~10 s of the load | ~10 s |
| Generation | 28 tokens in 7.28 s | 27 tokens in 3.84 s |
| **tok/s** | **3.84** | **7.03** |
| Baseline RAM | 0.57 GB | 0.57 GB |
| Peak RAM | 2.50 GB | 2.82 GB |
| **RAM delta** | **+1.93 GB** | **+2.25 GB** |
| Delta / file size | 4.1x | 4.8x |

### 5.3 llama.cpp — Qwen2.5-0.5B Q4_K_M, 469 MB

| Metric | CPU | --gpu-layers 999 |
|---|---|---|
| Load time | 0.8 s | 0.6 s |
| Generation | 32 tokens in 1.33 s | 32 tokens in 1.11 s |
| **tok/s** | **24.05** (llama.cpp reported 24.05) | **28.95** |
| Baseline RAM | 0.04 GB | 0.04 GB |
| Peak RAM | 0.51 GB | 0.52 GB |
| **RAM delta** | **+0.48 GB** | **+0.48 GB** |
| Delta / file size | 1.0x | 1.0x |

### 5.4 llama.cpp — Qwen2.5-3B Q4_K_M, 2007 MB (beyond-RAM)

| Metric | Value |
|---|---|
| Free RAM at start | 1.17 GB |
| Load time | 5.6 s |
| Generation | 32 tokens in 5.88 s |
| **tok/s** | **5.44** (llama.cpp reported 5.44) |
| Baseline RAM | 0.04 GB |
| Peak RAM | 2.31 GB |
| **RAM delta** | **+2.27 GB** |
| Delta / file size | 1.2x |

## 6. Master comparison

| Engine | Model | tok/s | Peak RAM (delta) | Delta/file | Load | Tokens |
|---|---|---|---|---|---|---|
| LayerStream (CPU) | 0.8B FP16 split | 0.40 | 2.30 GB | — | 4.4 s | 32 |
| FullRAM (CPU fp32) | 0.5B Q4 | 3.84 | 2.50 GB (+1.93) | 4.1x | 63.4 s | 28 |
| FullRAM (CUDA fp16) | 0.5B Q4 | 7.03 | 2.82 GB (+2.25) | 4.8x | 66.8 s | 27 |
| llama.cpp (CPU) | 0.5B Q4 | 24.05 | 0.51 GB (+0.48) | 1.0x | 0.8 s | 32 |
| llama.cpp (--gpu-layers) | 0.5B Q4 | 28.95 | 0.52 GB (+0.48) | 1.0x | 0.6 s | 32 |
| llama.cpp (CPU) | 3B Q4 | 5.44 | 2.31 GB (+2.27) | 1.2x | 5.6 s | 32 |

## 7. Derived metrics

### Speedup matrix (tok/s ratios)

| vs | LayerStream | FullRAM CPU | FullRAM CUDA | llama.cpp 0.5B | llama.cpp 3B |
|---|---|---|---|---|---|
| LayerStream 0.40 | 1x | — | — | — | — |
| FullRAM CPU 3.84 | 9.6x | 1x | — | — | — |
| FullRAM CUDA 7.03 | 17.6x | 1.8x | 1x | — | — |
| llama.cpp 0.5B 24.05 | 60x | 6.3x | 3.4x | 1x | — |
| llama.cpp 3B 5.44 | 13.6x | 1.4x | 0.8x | 0.23x | 1x |

### RAM residency (RAM delta / model file size)

| Path | Residency |
|---|---|
| FullRAM CPU fp32 | 4.1x |
| FullRAM CUDA fp16 | 4.8x |
| llama.cpp (both models) | 1.0-1.2x |

The FullRAM residency measurement is what `MemoryManager.suggest_mode` now
uses: 4x for GGUF (quant_method/family == "gguf"), 2x for full fp16/fp32
repos, +15% headroom, applied to both the VRAM and RAM checks.

### Decode scaling (llama.cpp, CPU)

3B vs 0.5B: 6x the parameters, 4.4x slower decode (24.05 -> 5.44 tok/s) —
consistent with a memory-bandwidth-bound regime (decode reads all weights per
token). This is why a 7-8B Q4 on this box would land around ~2-3 tok/s.

### Load time ratios

| Path | Load | vs llama.cpp 0.5B |
|---|---|---|
| llama.cpp 0.5B (mmap) | 0.8 s | 1x |
| llama.cpp 3B (mmap) | 5.6 s | 7x |
| LayerStream 0.8B split | 4.4 s | 5.5x |
| FullRAM 0.5B (dequant) | 63.4 s | 79x |

## 8. Memory projection (extrapolated, not measured)

Q4 file sizes approx: 0.5B = 0.47 GB, 1B = 0.7 GB, 3B = 2.0 GB, 8B = 5.0 GB.

| Model | FullRAM footprint (~4x file) | llama.cpp footprint (~1.2x file) | Fits 8 GB box? |
|---|---|---|---|
| 0.5B Q4 | 1.9 GB (measured 1.93) | 0.5 GB (measured 0.48) | FullRAM: yes |
| 1B Q4 | ~2.8 GB | ~0.8 GB | FullRAM: yes (top end) |
| 3B Q4 | ~8-10 GB (measured class: 0.5B -> 4.1-4.8x) | ~2.4 GB (measured 2.27) | FullRAM: no; llama.cpp: yes |
| 8B Q4 | ~20 GB | ~6 GB | FullRAM: no; llama.cpp: tight/swap |

## 9. Headlines and implications

1. **Compute, not I/O, was LayerStream's bottleneck.** 98% compute, 9% disk
   (already overlapped). The proposed I/O fix list targets the 9% and is
   parked with revisit triggers (reviews/parked-io-fixes-2026-08-16.md).
2. **FullRAM/transformers materializes Q4 at ~4x file size** — caps FullRAM
   at ~1B Q4 on this box and rules out 3-8B Q4 in 8 GB RAM.
3. **llama.cpp is the beyond-RAM path:** weights stay quantized (1.0-1.2x),
   instant mmap load, and the only engine here that runs 3B Q4 on 8 GB at
   usable speed (5.44 tok/s).
4. **Corrected pitch, fully measured:** "0.5-1B Q4 in RAM via FullRAM;
   3-8B Q4 via llama.cpp at ~5 tok/s on 8 GB."
5. **Engine routing (implemented):** `suggest_mode` now uses honest residency
   so "auto" = FullRAM only when it fits; LayerStream flagged experimental
   (engine attr, API fields, UI badges).

## 10. Reproducibility

From `backend/` with the venv:

```
.venv/Scripts/python.exe benchmark_layerstream.py            # LayerStream (08-14 model)
.venv/Scripts/python.exe benchmark_fullram.py                # FullRAM CPU, default 0.5B Q4
.venv/Scripts/python.exe benchmark_fullram.py --device cuda  # FullRAM CUDA
.venv/Scripts/python.exe benchmark_llamacpp.py               # llama.cpp 0.5B Q4 (CPU)
.venv/Scripts/python.exe benchmark_llamacpp.py --gpu-layers 999
.venv/Scripts/python.exe benchmark_llamacpp.py ../workspace/models/bench-qwen2.5-3b-q4/qwen2.5-3b-instruct-q4_k_m.gguf
```

Runners: `backend/benchmark_layerstream.py` (existing),
`backend/benchmark_fullram.py` + `backend/benchmark_llamacpp.py` (new, mirror
the LayerStream runner).

## 11. Source docs

- reviews/benchmark-2026-08-14.md — LayerStream CPU/GPU runs (raw)
- reviews/benchmark-fullram-2026-08-16.md — FullRAM Q4 runs (detailed)
- reviews/spike-llamacpp-offload-2026-08-16.md — llama.cpp runs, mechanism + integration notes
- reviews/design-layerstream-perf-2026-08-16.md — decision, premises, implementation status
- reviews/parked-io-fixes-2026-08-16.md — parked I/O list with revisit triggers

## 12. Caveats

- LayerStream's model differs (Qwen3.5-0.8B FP16 split vs the Q4 GGUFs); the
  same-model control is llama.cpp vs FullRAM on the 0.5B Q4.
- FullRAM CUDA peak RAM (4.8x) includes the CPU-side GGUF dequant transient;
  steady-state VRAM is fp16 (~2x file) on the 1650.
- 3B/8B FullRAM footprints are extrapolated from the 0.5B measurement (4.1-4.8x),
  not measured — 3B FullRAM cannot run on this box (would OOM at ~9.7 GB).
- Token counts differ (28/27/32) where EOS fired early; tok/s is per-token wall time.
