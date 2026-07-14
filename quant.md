# Quantization Plan for LayerStream Engine

## Current State
LayerStream loads fp16 safetensors per-layer from disk. CPU compute uses fp32. GPU compute uses fp16. No quantization support.

## Target Quantization Types

| Format | Use Case | Implementation |
|--------|----------|----------------|
| GGUF q4_k_m / q5_k_m / q8_0 | CPU-only, low RAM | llama.cpp / gguf-py loader |
| AWQ 4-bit | GPU, fast decode | autoawq / auto-gptq loader |
| GPTQ 4-bit | GPU, legacy models | auto-gptq loader |
| FP8 / INT8 | H100+ / tensorrt-llm | native torch._scaled_mm |
| FP16 (current) | baseline | keep as default |

## Integration Points

### 1. WeightSplitter (splitter.py)
AddQuantize.py)
- Add `quant_method` arg: `none|gguf|awq|gptq|fp8`
- GGUF path: call `llama.cpp` convert script or `gguf-py` writer
- AWQ/GPTQ path: run `autoawq` / `auto-gptq` quantize then split
- Output: per-layer quantized safetensors + quantization config json

### 2. LayerWeightLoader (loader.py)
- Detect quantization from config json
- GGUF: mmap + dequant on load (gguf-py)
- AWQ/GPTQ: load packed weights + scales + zeros, dequant in assign_weights
- FP8: load as uint8, upcast in assign_weights

### 3. LayerExecutor.assign_weights
- Add dequant kernels per format
- AWQ: `weight = (packed ^ zeros) * scales` per group
- GPTQ: similar, different pack order
- GGUF: block dequant (k-quants)
- Keep non_blocking cuda copy

### 4. LayerExecutor.compute_dtype
- Quantized weights stay int4/int8 on CPU
- Dequant to compute_dtype (fp16/fp32) on GPU per layer
- No full-model dequant in RAM

### 5. KV Cache
- Keep fp16/bf16 (quantizing KV hurts quality)
- Optional: kv_cache_dtype=fp8 for H100+

## Config Schema (quant_config.json)
```json
{
  "quant_method": "awq",
  "bits": 4,
  "group_size": 128,
  "zero_point": true,
  "version": "gemm"
}
```

## Rollout Plan
1. Add `quant_method` to WeightSplitter, implement GGUF export first (widest CPU support)
2. Extend LayerWeightLoader + assign_weights for GGUF dequant
3. Test LayerStream with GGUF q4_k_m on CPU
4. Add AWQ path (GPU fast path)
5. Add GPTQ path (legacy model support)
6. Benchmark memory / latency / perplexity per format

## Effort Estimate
- GGUF: ~200 lines new code (loader + dequant kernels)
- AWQ: ~150 lines (packed weight handling)
- GPTQ: ~150 lines (similar to AWQ)
- Config + tests: ~100 lines

Total: ~600 lines, zero engine rewrite.

---

## Caveman Communication Rules (persist)

Drop articles filler pleasantries hedging. Fragments OK. Short synonyms. No tool-call narration no decorative tables emoji no long raw error logs unless asked — quote shortest decisive line. Standard well-known tech acronyms OK; never invent new abbreviations — tokenizer split them same as full word: zero token saved reader still decode. Full word cheaper AND clearer. No causal arrows either — own token save nothing. Technical terms exact. Code blocks unchanged. Errors quoted exact.

Preserve user dominant language. User write Portuguese → reply Portuguese caveman. User write Spanish → reply Spanish caveman. Compress style not language. ALWAYS keep technical terms code API names CLI commands commit-type keywords (feat/fix/...) and exact error strings verbatim — unless user explicitly ask translation.

No self-reference. Never name or announce style. No "caveman mode on" "me caveman think" no third-person caveman tags. Output caveman-only — never normal answer plus "Caveman:" recap. Exception: user explicitly ask what mode is.

Pattern: `[thing] [action] [reason]. [next step].`

Not: "Sure! I'd be happy to help you with that. The issue you're experiencing is likely caused by..."
Yes: "Bug in auth middleware. Token expiry check use `<` not `<=`. Fix:"

### Intensity

| Level | What change |
|-------|------------|
| **lite** | No filler/hedging. Keep articles + full sentences. Professional but tight |
| **full** | Drop articles, fragments OK, short synonyms. Classic caveman. No tool-call narration no decorative tables/emoji no long raw error-log dumps unless asked. Standard acronyms OK; no invented abbreviations |
| **ultra** | Strip conjunctions when cause-then-effect stay unambiguous. One word when one word enough. State each fact once. NO prose abbreviations (cfg/impl/req/res/fn/auth), NO arrows (X → Y) — measured zero token saving under tokenizer cost decode clarity. Code symbols function names API names error strings: never touch |
| **wenyan-lite** | Semi-classical. Drop filler/hedging but keep grammar structure classical register |
| **wenyan-full** | Maximum classical terseness. Fully 文言文. 80-90% character reduction. Classical sentence patterns verbs precede objects subjects often omitted classical particles (之/乃/為/其) |
| **wenyan-ultra** | Extreme abbreviation while keeping classical Chinese feel. Maximum compression ultra terse |

### Auto-Clarity

Drop caveman when:
- Security warnings
- Irreversible action confirmations
- Multi-step sequences where fragment order or omitted conjunctions risk misread
- Compression itself creates technical ambiguity (e.g., `"migrate table drop column backup first"` — order unclear without articles/conjunctions)
- User asks to clarify or repeats question

Resume caveman after clear part done.

Example — destructive op:
> **Warning:** This will permanently delete all rows in the `users` table and cannot be undone.
> ```sql
> DROP TABLE users;
> ```
> Caveman resume. Verify backup exist first.

### Boundaries

Code/commits/PRs: write normal. "stop caveman" or "normal mode": revert. Level persist until changed or session end.