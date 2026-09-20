# FullRAM Q4 Benchmark (Detailed) — 2026-08-16

Approach A assignment from the office-hours session (design-layerstream-perf-2026-08-16.md):
measure the FullRAM GGUF Q4 path on the 8 GB box and get honest numbers for the
"3-8B Q4 on 8GB RAM" pitch. This is the detailed record; the cross-engine
comparison lives in reviews/benchmark-engines-2026-08-16.md.

## 1. Setup

- **Machine:** same dev box as the 08-14/08-15 LayerStream runs: 8.4 GB RAM
  (~1.5 GB free during the run), GTX 1650 4 GB, torch 2.5.1+cu124,
  transformers 5.3.0.dev0
- **Model:** `qwen2.5-0.5b-instruct-q4_k_m.gguf` (469 MB) + `config.json`,
  `tokenizer.json`, `tokenizer_config.json`, `vocab.json`, `merges.txt`,
  downloaded from HF to `workspace/models/bench-qwen2.5-0.5b-q4/`
- **Engine path:** `FullRAMEngine` -> transformers `AutoModelForCausalLM
  .from_pretrained(dir, gguf_file=...)` with `device_map="cpu"`+fp32 or
  `device_map="auto"`+fp16 on CUDA (exactly what the app does)
- **Runner:** `backend/benchmark_fullram.py` (new; mirrors
  `benchmark_layerstream.py`; `--device cpu|cuda`)

## 2. Methodology

- Prompt: 10-token `"The quick brown fox jumps over the lazy dog. "`
- Target: 32 tokens, temperature 0.7, top_p 0.9 (generate_stream path)
- tok/s = tokens / wall generation time (prefill + decode)
- Peak RAM: process RSS sampled every 50 ms in a background thread; delta
  over the pre-load baseline
- Load time: `engine.load()` to ready, including GGUF dequantization

## 3. Raw run — CPU (fp32)

| Metric | Value |
|---|---|
| Load time | 63.4 s |
| — GGUF dequant (291 tensors, progress bar) | ~10 s |
| — weight load + tokenizer + config | remainder |
| Generation | 28 tokens in 7.28 s (EOS fired early) |
| **tok/s** | **3.84** |
| Baseline RAM | 0.57 GB |
| Peak RAM | 2.50 GB |
| **RAM delta** | **+1.93 GB** |

## 4. Raw run — CUDA (fp16)

| Metric | Value |
|---|---|
| Load time | 66.8 s |
| Generation | 27 tokens in 3.84 s (EOS fired early) |
| **tok/s** | **7.03** |
| Baseline RAM | 0.57 GB |
| Peak RAM | 2.82 GB |
| **RAM delta** | **+2.25 GB** |

## 5. Residency math (the load-bearing numbers)

| Path | RAM delta | File size | Residency |
|---|---|---|---|
| CPU fp32 | 1.93 GB | 0.469 GB | **4.1x** |
| CUDA fp16 | 2.25 GB | 0.469 GB | **4.8x** |

Why: transformers dequantizes GGUF to the compute dtype (fp32 on CPU, fp16 on
CUDA) and the CUDA path materializes on CPU first before device transfer, so
RAM usage is ~4x the Q4 file on both paths. Steady-state VRAM on CUDA is fp16
(~2x file), but peak process RAM still reflects the CPU-side dequant.

This measurement is the basis for the shipped `MemoryManager.suggest_mode`
change: FullRAM residency = 4x for GGUF, 2x for full fp16/fp32 repos, +15%
headroom, applied to VRAM and RAM checks.

## 6. Comparison vs LayerStream (same box)

| Metric | FullRAM CPU | FullRAM CUDA | LayerStream ref* |
|---|---|---|---|
| Tokens/second | **3.84** | **7.03** | 0.40 |
| Load time | 63.4 s | 66.8 s | 4.4 s |
| Peak RAM (delta) | 2.50 GB (+1.93) | 2.82 GB (+2.25) | 2.30 GB |
| vs LayerStream | **9.6x** | **17.6x** | 1x |

\* LayerStream ref: 08-14 CPU run, Qwen3.5-0.8B FP16 split, same prompt/32
tokens (reviews/benchmark-2026-08-14.md).

## 7. Projection table (extrapolated from the 4.1-4.8x measurement)

Q4 file sizes approx: 0.5B = 0.47 GB, 1B = 0.7 GB, 3B = 2.0 GB, 8B = 5.0 GB.

| Model | FullRAM footprint (~4x) | llama.cpp footprint (~1.2x) | Fits 8 GB box via FullRAM? |
|---|---|---|---|
| 0.5B Q4 | 1.9 GB (measured) | 0.5 GB (measured) | yes |
| 1B Q4 | ~2.8 GB | ~0.8 GB | yes (top end) |
| 3B Q4 | ~8-10 GB | ~2.4 GB (measured) | **no** (OOM at ~9.7 GB) |
| 8B Q4 | ~20 GB | ~6 GB | **no** |

## 8. Load-time analysis

- 63-67 s to load a 0.5B model; GGUF dequant alone is ~10 s, the rest is
  weight materialization and pipeline setup. A 3B Q4 would scale to minutes.
- Contrast: llama.cpp mmap loads the same 0.5B in 0.8 s and the 3B in 5.6 s
  (reviews/spike-llamacpp-offload-2026-08-16.md).
- **First-token latency, not decode, is the FullRAM UX problem.**

## 9. Honest read

1. **FullRAM Q4 is ~10-18x faster than LayerStream on this box and the memory
   bound holds.** 0.5B Q4: 469 MB file -> 2.5 GB RSS. The approach is sound;
   LayerStream is simply not competitive for decode.
2. **"3-8B Q4 on 8GB RAM" does not survive the numbers.** RAM scales ~4x the
   Q4 file: 3B needs ~8-10 GB, 8B needs ~20 GB. The realistic FullRAM ceiling
   on this box is ~1B Q4.
3. **Load time is the second killer** (63-67 s for 0.5B, minutes for 3B+).
4. **The only path that keeps weights quantized in RAM is llama.cpp-style
   mmap offload (Approach B):** 3B Q4 stays ~2 GB, 8B Q4 ~5 GB, decode 1-6
   tok/s. B is required for the headline claim, not a nice-to-have.

## 10. Decision and follow-through

- **Pitch:** "0.5-1B Q4 in RAM, usable today (3-8 tok/s); 3-8B Q4 via the
  llama.cpp backend (Approach B), weights stay quantized." Drop "8B in 8GB
  RAM" from the marketing surface.
- **Engine routing (implemented 2026-08-16):** `MemoryManager.suggest_mode`
  now applies the measured 4x GGUF residency, so "auto" picks FullRAM only
  for models that fit and LayerStream otherwise; LayerStream is flagged
  experimental across the API and UI. Pinned by
  `backend/tests/test_suggest_mode.py` (7 tests).
- **Beyond-RAM path (validated):** llama.cpp runs the 3B Q4 at 5.44 tok/s /
  2.3 GB RSS on this box (reviews/spike-llamacpp-offload-2026-08-16.md).
  Open: engine-router wiring so beyond-RAM GGUF models actually route there.

## 11. Reproducibility

From `backend/` with the venv:

```
.venv/Scripts/python.exe benchmark_fullram.py                 # CPU fp32
.venv/Scripts/python.exe benchmark_fullram.py --device cuda   # CUDA fp16
```
