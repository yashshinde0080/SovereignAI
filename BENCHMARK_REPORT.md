# Inference Engine Benchmark Report

**Date:** 2026-08-25
**Hardware:** NVIDIA GeForce GTX 1650 (4 GB VRAM, Turing) · 8 GB system RAM · Windows
**Model:** Qwen2.5-0.5B-Instruct (fp16 safetensors, ~988 MB)
**Prompt:** `Write a short paragraph about the sea.`
**Token budget:** 64 new tokens (post-generation warm-up run excluded)

---

## Results

| Metric | FullRAM | LayerStream (legacy) | AirLLM |
|---|---|---|---|
| **Load time** | 3.7 s | 3.1 s | 1.4 s |
| **Generate time** | 8.04 s | 8.86 s | 41.55 s |
| **Tokens generated** | 64 | 64 | 64 |
| **Throughput** | **7.96 tok/s** | **7.22 tok/s** | **1.54 tok/s** |
| **RAM used** | 1.67 GB | 1.94 GB | 1.99 GB |
| **VRAM peak** | 959 MB | ~300 MB | 301 MB |

---

## How each engine works

| Engine | Strategy | When RAM ≥ model | When RAM < model |
|---|---|---|---|
| **FullRAM** | Loads entire model into GPU/RAM via `transformers.AutoModelForCausalLM` | ✅ Default (fastest) | N/A (needs RAM) |
| **LayerStream (legacy)** | Splits model to per-layer `.safetensors` on disk; loads/unloads layers in an LRU RAM cache during generation | ✅ Viable | ✅ Caches hot layers in RAM |
| **AirLLM** | Streams every layer shard from disk to GPU via forward hooks on every forward pass; no persistent cache | ✅ Viable | ✅ Only one layer resident at a time |

---

## Why AirLLM is slower here

AirLLM was designed for **models that don't fit in RAM** — e.g. a 70 B model on 16 GB RAM where no engine can cache layers. On a 0.5 B model that fits entirely in memory:

1. **Per-token overhead:** AirLLM moves all 26 modules (embed → 24 layers → norm → lm_head) from disk to GPU on every single generated token. LayerStream caches them in RAM after the first pass.
2. **`clean_memory()` per module:** AirLLM's vendored code runs `gc.collect()` + `cuda.empty_cache()` after every module move per token. A patched version (included in the engine) removes the gc.collect, recovering ~6×, but the base gap remains.
3. **VRAM layout:** AirLLM pins to ~300 MB VRAM (one layer at a time). FullRAM uses the full 959 MB and runs compute without disk I/O.

**AirLLM's advantage:** lowest load time (1.4 s vs 3.1–3.7 s) — it doesn't build a split cache up front. For interactive use where model swaps are frequent and the model is too large for RAM, this matters.

---

## Selection guidance

| Regime | Best engine | Notes |
|---|---|---|
| Model fits in RAM/VRAM | **FullRAM** | Fastest tok/s, all weights in device memory |
| Model near RAM limit | **LayerStream (legacy)** | LRU cache keeps hot layers resident; best throughput in the fit-in-RAM edge case |
| Model **exceeds** RAM | **AirLLM** | Only engine that never loads the full model; threshold auto-selector uses this when RAM < model size |
| GGUF format | **FullRAM** (via llama-cpp fallback) | AirLLM does not support GGUF; LayerStream requires custom splitting |

The `auto` mode selector (`MemoryManager.suggest_mode`) picks FullRAM when
RAM > 1.1× model size, AirLLM when RAM > 0.1× model size, and refuses
otherwise.

---

## Regression note

> **AirLLM (1.54 tok/s) is ~4.7× slower than LayerStream Legacy (7.22 tok/s)
> on a model that fits in RAM.** This is an architectural limitation, not a
> bug. AirLLM is only the correct choice when the model exceeds available RAM,
> a regime that could not be benchmarked here (all local models fit in the
> available 8 GB).
