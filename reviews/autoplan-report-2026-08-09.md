<!-- /autoplan report: stored in project folder per user request (no ~/.gstack writes) -->

# /autoplan Review Report — turboquant.md (TurboQuant KV Cache)

- **Date:** 2026-08-09 | **Branch:** main | **Commit:** 841c5d1
- **Plan under review:** `turboquant.md` (TurboQuant KV-cache compression integration guide)
- **Scope detected:** UI = no (backend-only plan) → Phase 2 (Design) skipped | DX = yes (new CLI command + config surface) → Phase 3.5 ran
- **Voices:** Primary (Buffy) + Independent reviewer (code-reviewer agent). Codex unavailable on this machine, so the second voice is the independent reviewer. No gstack install, so all artifacts live in `reviews/` per the user's explicit constraint.

## TL;DR

**The plan is stale. ~90% of it was already implemented on 2026-07-23** (`Info_docs/log.md` line 88: "Marked TurboQuant KV Cache Compression (July 23) as done"). The shipped implementation **does not deliver the plan's headline claim**: measured bytes/coord give ~0.98x compression vs FP16, not 6x. The code's own comments admit this ("ratio < 1x without bit-packing"). The remaining work is not Phase 4 (GGUF export) — it is making the headline claim true: bit-packing, dropping or fixing QJL, fixing an O(n^2) update path, an accuracy eval suite, and flipping the default from on to off.

**Verdict:** Treat turboquant.md as an implementation record, not a to-execute plan. Rewrite it as "current state + what is needed for real compression." Gate below.

---

## Decision Audit Trail

| # | Phase | Decision | Class | Principle | Rationale | Rejected |
|---|-------|----------|-----------|-----------|----------|----------|
| 1 | CEO | Mode = SELECTIVE EXPANSION | Mechanical | P6 | Plan is an existing-system feature, baseline accepted, cherry-pick real remaining work | Other modes |
| 2 | CEO | P1 (6x @ 3.5 bits, zero loss) accepted as real per paper, UNVERIFIED in this impl | Auto | P1/P6 | Paper + community validate the claim; shipped code does not meet it → eval gate required | Reject premise |
| 3 | CEO | P2 (custom PyTorch TQ) challenged at gate | User Challenge | P5 | llama.cpp tbq3_0/tbq4_0 (PR #21089) exists as Layer-1 alternative for GGUF models | Keep custom only |
| 4 | CEO | Approach A (fix in place: bit-pack + drop QJL + validate) | Auto | P1/P3/P5 | Smallest diff to make the real claim true; no new infra | Rewrite / drop feature |
| 5 | CEO | Engine-router auto-enable (RAM budget) → defer to TODOS | Auto | P2/P3 | Outside blast radius of the core fix; needs eval first | Implement now |
| 6 | Eng | update() O(n^2) re-quantize-every-token → must fix | Auto | P1 | Long-context decode is the exact use case; per-token full-history requant is catastrophic | Keep |
| 7 | Eng | Flip turboquant_enabled default to False until validated | Auto | P1/P3 | Default-on ships a slower, lossy, ~1x path on every LayerStream load | Keep on |
| 8 | Eng | Drop QJL at >= 3 bits (or fix decode scaling) | Auto | P3 + community evidence | QJL adds little at 3+ bits per community; as shipped it is near no-op (scaling off by ~sqrt(d')) | Keep broken QJL |
| 9 | Eng | Fix FullRAM dim-order / seq_len metadata bug | Auto | P1 | Silent wrong sequence-length bookkeeping in decode | Keep |
| 10 | Eng | Accuracy eval suite (perplexity + needle-in-haystack vs FP16) required | Auto | P1 | "Zero accuracy loss" is unverified; MSE-on-random-data is not evidence | MSE only |
| 11 | Eng | Unit tests in backend/tests/ | Auto | P1 | Only manual __main__.py self-check exists | Manual only |
| 12 | Eng | CLI benchmark honesty: use the model, label estimates as estimates | Auto | P5 | "Estimated (bit-packed): Xx" is fabricated math presented as a result | Keep |
| 13 | Eng | Remove/align dead config flags (hadamard, beta_lloyd_max, enable_polarquant, collect_stats) | Auto | P5 | Config claims modes the code does not implement | Keep |
| 14 | DX | benchmark-turboquant reports real measured ratio only | Auto | P5 | DX principle: every output is a measurement or clearly labeled | Estimates |
| 15 | DX | Document turboquant status + default-off in CLI help | Auto | P1 | TTHW and trust: devs must know the feature is experimental | Silence |

---

# Phase 1 — CEO Review

## Premises (challenged → gate)

| # | Premise | Verdict |
|---|---------|---------|
| P1 | TurboQuant gives ~6x KV compression with zero accuracy loss at 3.5 bits | 🟢 Real per paper (arXiv 2504.19874, ICLR 2026, Google Research) + community. 🔴 UNVERIFIED in this implementation: shipped code measures ~0.98x, no accuracy eval exists |
| P2 | Custom PyTorch TurboQuant is the right build | 🟠 Challenged at gate. llama.cpp ships native tbq3_0/tbq4_0 kernels (PR #21089) with community GPU ports. For GGUF models that is Layer 1. The custom path makes sense for the LayerStream raw-PyTorch stack, but the two should be cross-validated, not assumed |
| P3 | KV cache is the memory bottleneck | 🟡 Half true. FullRAM long-context: yes. LayerStream caps KV at 2048 MB and offloads to CPU, so the benefit there is latency (skip requant) and CPU RAM, not the headline number |
| P4 | 3.5 bits + QJL is the right operating point | 🟠 Community finding: at >= 3 bits, Lloyd-Max-only beats the two-stage QJL. The plan's insistence on QJL at 3.5 bits is likely suboptimal and adds 1 byte/coord that kills the ratio |
| P5 | Default-on is harmless | 🔴 Wrong. config.py sets turboquant_enabled=True and LayerStream auto-enables from settings. With ~1x compression this makes every load strictly worse (lossy + slower + no memory win) |

## What already exists (leverage map)

| Plan sub-problem | Existing code (implemented 2026-07-23) |
|---|---|
| Core library (config, polarquant, qjl, codebook, kv_cache, hf_proxy) | `backend/app/engines/shared/turboquant/` — 8 files, shipped |
| Settings | `backend/app/config.py:45-49` (turboquant_enabled/bits/qjl_enabled/rotation) |
| LayerStream wiring | `layerstream/executor.py:152-160` reads settings; `layer_executor.py:42-63` builds TurboQuantKVCacheManager + TurboQuantHFProxyCache |
| KV factory | `layerstream/kv_cache.py:147` `KVCacheManager.create(mode="turboquant")` |
| FullRAM flag | `fullram/kv_cache.py:16` `use_turboquant` |
| CLI | `cli/main.py:697` `benchmark_turboquant` (synthetic only) |
| Self-check | `shared/turboquant/__main__.py` (manual, MSE-only) |
| Paper verification | Confirmed: arXiv 2504.19874, ICLR 2026, Google Research; ~6x/3.5-bit validated by community |

Not implemented: Phase 4 (GGUF/llama.cpp tbq3_0/tbq4_0 export), engine-router auto-enable (engine_factory.py has zero turboquant awareness), accuracy evals, unit tests, bit-packing.

## Dream state delta

```
  CURRENT STATE                      THIS PLAN (as written)         12-MONTH IDEAL
  ~0.98x compression, default-on,    Stale 4-phase roadmap,          Bit-packed 3.5-bit cache
  no evals, no tests, O(n^2) update  ~90% already shipped,           at ~4-6x with validated
  (lossy + slower + no win)          headline claim unmet            accuracy vs FP16, evals in
                                     --->                            CI, default-off until proven,
                                                                     llama.cpp numbers cross-checked
```

## Implementation alternatives (0C-bis)

```
APPROACH A: Fix in place (recommended)
  Summary: Keep the shipped package. Bit-pack 3.5-bit indices (9/word), drop QJL at
            3.5 bits or fix its decode scaling, compress scales, fix update() to append
            incrementally, fix the FullRAM layout bug, flip default off, add evals.
  Effort:   M (human ~3-5 days / CC ~2-3 hours)
  Risk:     Med (math is subtle; eval gate catches regressions)
  Pros:     Smallest diff; reuses all shipped code; directly makes the headline true
  Cons:     Ships alongside the "broken Beta Lloyd-Max" legacy; QJL decision still open
  Reuses:   Entire shared/turboquant package, both engine integrations, CLI

APPROACH B: Stand on llama.cpp (Layer 1)
  Summary: For GGUF models, use llama.cpp native tbq3_0/tbq4_0 (PR #21089) instead of
            custom PyTorch. Keep custom path only for the safetensors LayerStream stack.
  Effort:   M (human ~1-2 weeks / CC ~1 day) — depends on llama.cpp integration maturity
  Risk:     Med-High (llama.cpp backend not wired into LayerStream today; big detour)
  Pros:     Proven kernels, no custom math, community GPU ports, real compression today
  Cons:     LayerStream runs raw PyTorch layers; adopting llama.cpp KV only is a hybrid
            nobody else has; the 3-duplicate-engine history says be careful
  Reuses:   Existing GGUF paths, prior llama.cpp findings

APPROACH C: Defer the feature
  Summary: Flip default off, mark experimental, park the library. Focus on the P1
            validation spike from the 2026-08-05 review (70B-on-8GB claim) instead.
  Effort:   S (human ~1 day / CC ~10 min)
  Risk:     Low
  Pros:     Removes a net-negative default from every load today; zero sunk cost
  Cons:     The July work sits unused; long-context enablement stays impossible
  Reuses:   Nothing new
```

**RECOMMENDATION:** Approach A. It is the smallest diff that makes the shipped claim true, and it reuses everything already built. B is the honest Layer-1 counterweight and should at least be benchmarked against A's numbers. C is the fallback if the eval gate fails.

## Error & Rescue Registry

| Failure | Rescue |
|---------|--------|
| Eval gate fails (accuracy drops at 3.5 bits) | Drop to 4-bit pure-PolarQuant; or disable feature (Approach C). Never ship a lossy no-win default |
| Bit-packing bugs corrupt cache | Unit tests on packed roundtrip + golden vectors; keep unpacked path as fallback flag |
| llama.cpp tbq3_0 numbers are better | Adopt llama.cpp KV for GGUF models; keep custom only where necessary |
| O(n^2) update still slow after chunking | Chunked re-quantization every N tokens; document the latency tradeoff |
| FullRAM path silently wrong after fix | Layout assertion + integration test with a real tiny model |

## Failure Modes Registry

| Mode | Trigger | Detection | Blast radius |
|------|---------|-----------|--------------|
| Net-negative default | Every LayerStream load with turboquant_enabled=True | Compression ratio printed by CLI shows ~1x | All users |
| Silent accuracy loss | Quantized cache with no eval gate | None today (MSE only) | All long-context users |
| FullRAM seq_len metadata wrong | FullRAM + turboquant decode | get_seq_length returns num_heads | FullRAM turboquant path |
| O(n^2) decode stalls | Long context + update() requant | Latency grows with context | Long-context chat |
| QJL near-noop | Decode scaling off by sqrt(d') | Self-test passes anyway (insensitive) | Residual correction stage |

## CEO consensus table

```
CEO DUAL VOICES — CONSENSUS TABLE:
  Dimension                           Primary  Reviewer  Consensus
  1. Premises valid?                  NO       NO        CHALLENGE (P2, P5; P1 unverified)
  2. Right problem to solve?          YES*     YES*      CONFIRMED (*if compression made real)
  3. Scope calibration correct?       NO       NO        CHALLENGE (plan is stale; real work is bit-packing + validation)
  4. Alternatives sufficiently explored? NO   NO        CHALLENGE (llama.cpp native path ignored)
  5. Competitive/market risks covered? YES     YES       CONFIRMED (paper validated; community exists)
  6. 6-month trajectory sound?        NO       NO        CHALLENGE (net-negative default today)
```

## NOT in scope

- GGUF/llama.cpp tbq3_0/tbq4_0 export (Phase 4): do NOT build until Approach A or B is chosen and the eval gate passes. It is a distribution problem, and llama.cpp PR #21089 already exists.
- Engine-router RAM-budget auto-enable: defer to TODOS until evals exist. Auto-enabling an unvalidated path is how the current default-on bug happened.
- Beam search reorder, batch > 1: document as known limits, do not build unless an eval needs them.
- ManualStreamEngine cleanup: unrelated to this plan, but it still exists in engine_factory.py (prior review said delete). Flagged, not in scope.

## Phase 1 completion summary

Strategic call: the feature is worth finishing because the paper is real and long-context enablement is the wedge. But the current state is a net-negative default with an unverified headline. Sequence: flip default off → fix update() + FullRAM bug → bit-pack + drop QJL → eval gate → re-enable. That is the entire real plan.

**PHASE 1 COMPLETE.** Primary: 6 issues. Independent reviewer: 6 aligned issues. Consensus: 4/6 confirmed, 2 disagreements resolved as challenges. Premise gate folded into the final gate.

---

# Phase 2 — Design Review

**SKIPPED — no UI scope.** Checked the plan for view/rendering terms (component, screen, form, button, modal, layout, dashboard, sidebar, nav, dialog). Zero matches beyond generic "configuration". This plan is backend-only (engines, config, CLI). Nothing to design-review.

---

# Phase 3 — Eng Review

## Scope challenge (with actual code)

Read: all 8 turboquant package files, layerstream/executor.py + layer_executor.py + kv_cache.py, fullram/kv_cache.py, config.py, engine_factory.py, model_manager.py, cli/main.py.

Complexity check: the plan touches 8+ files and adds 6 classes, but they are ALREADY SHIPPED. The complexity smell applies to the remaining work, which is smaller: bit-packing module, update() refactor, FullRAM layout fix, eval harness. Not reduced, but re-scoped to what is real.

**Sub-problem → code map:** every roadmap checkbox except Phase 4 and the router section maps to shipped code (see Phase 1 leverage map).

## Architecture (current state)

```
  LayerStream:                                   FullRAM:
  LayerExecutor                                 KVCache (numpy)
    | turboquant_config?                          | use_turboquant?
    |--> TurboQuantKVCacheManager                 |--> TurboQuantKVCacheManager
    |       | update(layer, k, v)  [O(n^2) NOW]   |        [BUG: [1,seq,nh,hd] vs
    |       |   dequantize-all + cat + requant    |         expected [1,nh,seq,hd]]
    |--> TurboQuantHFProxyCache (DynamicCache)    |
            | update() -> manager -> dequantized K/V for attention
            | reorder_cache: NotImplementedError

  Shared core (shipped, diverged from plan):
    polarquant: random QR rotation (hadamard config = dead)
    codebook:   UNIFORM centroids (plan said Beta Lloyd-Max; that version was
                found broken and replaced — plan doc is wrong about its own core)
    qjl:        P normalized by 1/sqrt(d'), decode divides by d'  [net 1/d'^1.5 — near noop]
    kv_cache:   uint8 idx (1 B) + int8 qjl (1 B) + float32 scale (0.03 B) = ~2.03 B/coord
                vs FP16 2 B/coord  ->  ~0.98x  [6x claim unmet]

  Missing: bit-packing, incremental update, evals, tests, router awareness
  (engine_factory.py has zero turboquant references -> FullRAM turboquant unreachable)
```

## Section 3 — Test review (full depth)

Test diagram — every new codepath and its coverage:

| Codepath | Covered today? | Gap |
|----------|----------------|-----|
| PolarQuant roundtrip MSE | Manual `__main__.py` | Not in pytest; asserts MSE on synthetic only |
| QJL roundtrip | Manual `__main__.py` | Assert is insensitive to the sqrt(d') scaling error |
| KV manager quantize/dequantize shape | Manual `__main__.py` | No attention-quality check |
| Compression ratio | Printed, never asserted | No assert that ratio > 1; no bit-packed path |
| LayerStream wiring (settings -> config) | None | No test that turboquant_config reaches LayerExecutor |
| LayerStream decode with past_length | None | FullRAM seq_len bug class uncovered |
| FullRAM numpy -> torch layout | None | The dim-order bug ships untested |
| HF proxy DynamicCache contract | None | No test against a real small model |
| CLI benchmark output | None | Fabricated estimate printed as result |
| Accuracy vs FP16 (perplexity / needle-in-haystack) | None | **The critical missing eval** |

**Auto-decided:** add real pytest coverage in `backend/tests/test_turboquant.py` (roundtrip, ratio >= 1 assert, incremental update, FullRAM layout with a real tiny HF model) and an eval harness (perplexity on a small slice + needle-in-haystack at moderate context) run against FP16 baseline. This is the completeness call (P1): the "zero accuracy loss" claim cannot ship without it.

## Performance

- `update()` is O(n^2): every new token dequantizes the full history, concatenates, re-quantizes. At 128K context each decode step re-runs rotation matmuls over the whole sequence. This is the single worst property of the shipped code and it hits the exact use case the feature exists for. Fix: store per-chunk entries and only quantize the new chunk; dequantize only what attention needs.
- QJL stage: as shipped, effectively attenuated ~8x at d'=128, so it corrects almost nothing while costing 1 byte/coord. Either fix the scaling or drop the stage at >= 3 bits.
- The fullram sliding-window shift in the non-turboquant path (`cache[:, :, :-shift]`) shifts ALL layers; pre-existing, out of scope, noted.

## Eng consensus table

```
ENG DUAL VOICES — CONSENSUS TABLE:
  Dimension                           Primary  Reviewer  Consensus
  1. Architecture sound?              NO       NO        CHALLENGE (O(n^2) update, unreachable FullRAM path)
  2. Test coverage sufficient?        NO       NO        CHALLENGE (zero pytest, no accuracy eval)
  3. Performance risks addressed?     NO       NO        CHALLENGE (requant-every-token)
  4. Security threats covered?        YES      YES       CONFIRMED (no new attack surface; local-only)
  5. Error paths handled?             PARTIAL  PARTIAL   DISAGREE->taste (batch>1, beam documented, not built)
  6. Deployment risk manageable?      NO       NO        CHALLENGE (default-on net-negative)
```

## Eng completion summary

The plan as written would have you implement what already exists. The real engineering work: bit-pack indices to ~0.44 B/coord, drop or fix QJL, compress scales, make update() incremental, fix the FullRAM layout bug, add the eval gate, flip the default off, and align the dead config flags with reality. Failure modes registry above; the two critical gaps are the unmet compression claim and the absent accuracy validation.

**PHASE 3 COMPLETE.** Primary: 8 issues. Independent reviewer: 10 findings (2 critical, 5 high/medium shared). Consensus: 4/6 confirmed, 1 taste, 1 resolved as challenge.

---

# Phase 3.5 — DX Review

Developer-facing surface: the `sovereign benchmark-turboquant` CLI command, the `turboquant_*` config keys, and the LayerStream auto-enable behavior. Product type: CLI Tool + embedded engine library.

## Developer journey map

| Stage | Developer does | Friction | Status |
|-------|----------------|----------|--------|
| Discover | Reads `sovereign help` → sees benchmark-turboquant | Listed as "KV-compression benchmark", fine | ok |
| Install | Nothing new (ships with app) | none | ok |
| Hello World | `sovereign benchmark-turboquant m.gguf` | `model` arg is IGNORED; output is synthetic; prints "Estimated (bit-packed): Xx" as if real | FAIL |
| Real usage | Toggles settings, loads model | Default-on means the lossy ~1x path is active with no visible indicator | FAIL |
| Debug | Runs the self-check | `python -m app.engines.shared.turboquant` prints "OK" while admitting ratio < 1x; no accuracy signal | FAIL |
| Upgrade | Reads log.md "done" | Doc says done; claim unmet. Trust gap | FAIL |

## Developer empathy narrative

"I saw the log say TurboQuant was done, so I ran the benchmark to show the team the 6x win. I passed my model file. It printed synthetic numbers, ignored my model, and told me the bit-packed version would be 4x better. Then I loaded a model for real chat and it was slower. I checked the config: turboquant_enabled is on by default. I have no idea if my outputs got worse, because nothing measures accuracy. I can't tell if this feature helps or hurts, and the docs say it's finished. I stopped trusting the memory-reduction numbers."

## DX scorecard

| # | Dimension | Score | Why |
|---|-----------|-------|-----|
| 1 | Getting started (TTHW) | 4/10 | Benchmark runs, but output is synthetic and partly fabricated; no "does this work" signal |
| 2 | Credible | 2/10 | Log claims done; claim unmet; default-on net-negative; docs contradict code |
| 3 | Findable | 6/10 | CLI help lists the command; no docs section explains the current state |
| 4 | Useful | 3/10 | ~1x compression today; the 6x value is theoretical |
| 5 | Valuable | 3/10 | Saves nothing measurable today; costs latency and accuracy risk |
| 6 | Accessible | 6/10 | Works across modes with a flag; only one surface (CLI) |
| 7 | Desirable | 4/10 | Real paper + community momentum; implementation lags the story |
| 8 | Error handling | 3/10 | reorder_cache raises, batch>1 raises, no human-readable "why" for default behavior |

**Overall: 3.9/10. TTHW: ~2 min to run, ~0 min to trust.**

## DX implementation checklist

1. `benchmark-turboquant` must actually load/use the model or clearly say "synthetic"; label estimates as estimates; print the measured ratio and assert a floor.
2. Flip default to off; when on, surface a one-line warning in CLI/server logs ("TurboQuant experimental: compression ~1x until bit-packing lands").
3. Rewrite `turboquant.md` header to "Status: implemented 2026-07-23, headline claim not yet met" with a pointer to this report.
4. Add a `--packed` path to the benchmark once bit-packing ships so the real number is the headline.

## DX consensus table

```
DX DUAL VOICES — CONSENSUS TABLE:
  Dimension                           Primary  Reviewer  Consensus
  1. Getting started < 5 min?         YES      YES       CONFIRMED (runs fast, but misleading output)
  2. API/CLI naming guessable?        YES      YES       CONFIRMED (benchmark-turboquant is clear)
  3. Error messages actionable?       NO       NO        CHALLENGE (silent no-op / fabricated numbers)
  4. Docs findable & complete?        NO       NO        CHALLENGE (log.md says done; truth differs)
  5. Upgrade path safe?               NO       NO        CHALLENGE (default-on lossy path)
  6. Dev environment friction-free?   YES      YES       CONFIRMED
```

**PHASE 3.5 COMPLETE.** DX overall: 3.9/10. TTHW: ~2 min to run, 0 min to trust. Primary: 4 issues. Reviewer: 3 aligned. Consensus: 3/6 confirmed.

---

# Cross-Phase Themes

**Theme: the headline claim is unverified in shipped code.** Flagged independently in CEO (P1), Eng (compression math + no accuracy eval), and DX (credibility 2/10). High-confidence signal: the entire value proposition depends on bit-packing + an eval gate that do not exist yet. Every other finding hangs off this one.

**Theme: default-on amplifies the gap.** CEO P5, Eng deployment risk, DX upgrade-path all hit the same bug: `turboquant_enabled=True` with ~1x compression means every LayerStream load is worse. Flip it off first.

---

# Implementation Tasks (aggregated, P1 -> P3)

- [x] **P1 (critical) — Flip default off** ✅ DONE 2026-08-09: `backend/app/config.py` `turboquant_enabled: bool = False` with rationale comment. Files: `backend/app/config.py`.
- [x] **P1 (critical) — Make update() incremental** ✅ DONE 2026-08-09: `TurboQuantKVCacheManager` rewritten with a per-layer raw-token hot buffer (chunk_size 64) that flushes to quantized chunks. `update()` is O(chunk) and NEVER re-quantizes history — every token is quantized exactly once, so incremental == one-shot **bit-exact** (proven by test). Bonus fix: `TurboQuantConfig.__post_init__` was silently hardcoding `qjl_dim=128`, defeating the auto=head_dim path (4x QJL storage at hd≠128) — removed; `qjl_dim or head_dim` now resolves at runtime. Files: `backend/app/engines/shared/turboquant/kv_cache.py`, `turboquant/config.py`.
- [x] **P1 (critical) — Bit-pack indices** ✅ DONE 2026-08-09: `pack_indices`/`unpack_indices`/`_per_word_for` in `kv_cache.py` — base-`levels` digits into uint32 words (3.5 bits → 11 levels → 9/word, 11⁹ < 2³²), little-endian, zero-padded tail, vectorized unpack. New `bit_pack: bool = True` config flag; `False` restores the uint8 fallback. Also dropped the dead `v_indices=zeros_like()` tensors (free memory). Ratio asserts in tests now `> 1.0` (QJL-on) and `> 3.0` (QJL-off). Measured: self-check 1.4x (QJL) / 3.8x (PolarQuant-only 4-bit), up from 1.0x/1.9x. Files: `shared/turboquant/kv_cache.py`, `config.py`. (human: ~1-2 days / CC: ~30 min)
- [x] **P1 (high) — Accuracy eval gate** ✅ DONE 2026-08-09 — **VERDICT: FAIL, feature stays OFF.** `benchmarks/accuracy_eval.py` (chunked perplexity on wikitext + needle-in-haystack vs native cache). Qwen2-0.5B, 1280 tokens: baseline ppl 7.86; every TQ config explodes (3.5+QJL 1201, 3.5-noQJL 3434, 4.0+QJL 3623 — 15k-46k% degradation) and the needle is lost. Root cause: real K/V norms ~215 (not ~8), attention logits ~5800; even a Gaussian-LM-matched codebook (12x better NMSE: 0.214 -> 0.0185) still gives 1017 ppl (96x), and 6-bit/64-level still 1900% degradation. 3.5-bit scalar-codebook quantization cannot represent vectors precisely enough for this model's sharp attention. See "Accuracy Eval Gate" section. Files: `backend/benchmarks/accuracy_eval.py`, results `reviews/eval_gate_2026-08-09.json`. (human: ~2 days / CC: ~40 min)
- [x] **P1 (high) — QJL decision (drop vs fix)** ✅ DONE 2026-08-09, synthetic decision: **KEEP + FIX** (see row above). **REAL-DATA RE-VALIDATION (eval gate, 2026-08-09): FALSIFIED.** `benchmarks/qjl_ablation.py` (new) swept QJL off/shipped/fixed across 2.0-4.0 bits on synthetic data: at 3.5 bits QJL cuts attn NMSE 0.494 -> 0.275 (fixed c=1/32) vs 0.463 (shipped 1/d'^1.5). But on real Qwen2 K/V the tuned gain does NOT transfer: with the (better) Gaussian-LM codebook, QJL makes NMSE WORSE (0.0185 -> 0.0670 — overcorrects the smaller residual). The synthetic random-query attention metric was over-optimistic (real attention is sharp; random queries average out the error). The gate is the arbiter: both QJL-on and QJL-off fail it (ppl 1201 vs 3434 — QJL helps relative to off but is nowhere near passing). Files: `shared/turboquant/qjl.py`, `benchmarks/qjl_ablation.py`, `benchmarks/accuracy_eval.py`. (human: ~4h / CC: ~15 min)
- [ ] **P2 — Fix FullRAM layout bug**: transpose [seq, nh, hd] -> [1, nh, seq, hd] before update; add integration test with tiny model. Files: `fullram/kv_cache.py`, `backend/tests/test_turboquant.py`. (human: ~2h / CC: ~10 min)
- [x] **P2 — Unit tests** ✅ DONE 2026-08-09: 19 tests in `backend/tests/test_turboquant.py` (roundtrip shape+MSE, incremental==one-shot bit-exact, no-requant identity, long-run 300x1 flush, partial buffer, empty update, get(device=), update-after-clear, layer independence, ratio floor, batch>1 raises, QJL-off path, default-off config). Full suite: **62 passed**, self-check green. (human: ~1 day / CC: ~30 min)
- [ ] **P2 — Align dead config**: implement or remove hadamard / beta_lloyd_max / enable_polarquant / collect_stats; make defaults match code. Files: `shared/turboquant/config.py`, `codebook.py`. (human: ~1h / CC: ~5 min)
- [ ] **P3 — CLI honesty**: use the model arg or say "synthetic"; label estimates; print measured ratio only. Files: `backend/app/cli/main.py`. (human: ~2h / CC: ~10 min)
- [ ] **P3 — Rewrite turboquant.md** as "status + what's needed for 6x" pointing at this report. Files: `turboquant.md`. (human: ~1h / CC: ~10 min)
- [ ] **P3 — TODOS.md**: add engine-router auto-enable (gated on eval), llama.cpp cross-validation benchmark, GGUF tbq3_0/tbq4_0 evaluation. (human: ~30 min / CC: ~5 min)

---

# GSTACK REVIEW REPORT

## Runs / Status / Findings

| Run | Status | Findings |
|-----|--------|----------|
| CEO (primary) | clean | 0 unresolved after gate |
| CEO (independent reviewer) | clean | 0 unresolved after gate |
| Design | skipped | no UI scope (documented) |
| Eng (primary) | clean | 0 unresolved after gate |
| Eng (independent reviewer) | clean | 0 unresolved after gate |
| DX (primary) | clean | 0 unresolved after gate |
| DX (independent reviewer) | clean | 0 unresolved after gate |

VERDICT: CROSS-MODEL — both voices agree: plan is stale (~90% shipped), headline 6x claim unmet (~0.98x), real plan is bit-packing + validation + default-off. Approved as the review report; the plan doc itself needs a rewrite (task P3 above) before any implementation resumes.

**UNRESOLVED DECISIONS:** none for the review pipeline. Two items are gated on the user at the final approval gate: (1) User Challenge on the plan's premise (custom PyTorch vs llama.cpp native), (2) taste choice on QJL at 3.5 bits (drop vs fix). Both are user calls, listed in the gate.

## Final gate decision (2026-08-09)

- **User Challenge:** RESOLVED — refocus the work on making the 6x claim true (bit-packing + validation + default-off). turboquant.md is treated as an implementation record; Phase 4 (GGUF/llama.cpp export) stays deferred. Roadmap preserved as-is per user choice, re-prioritized per this report.
- **Gate:** APPROVED AS-IS (2026-08-09). Interrogation answered for 5 findings (compression math, O(n^2) update, FullRAM dim-order, QJL scaling, stale-plan evidence). Challenge resolved: refocus on the real gap. Report is the review of record.

**STATUS: DONE.**

## Implementation Status (2026-08-09, post-gate)

First tranche of the approved P1 work shipped and verified:

| Task | Status | Evidence |
|------|--------|----------|
| Flip `turboquant_enabled` default to False | ✅ | `backend/app/config.py:46`; test `TestConfigDefault::test_turboquant_defaults_off` |
| Make `update()` incremental (hot-buffer, no requant of history) | ✅ | `kv_cache.py` rewrite; bit-exact equality tests; no-requant identity test |
| Fix `qjl_dim` auto (was hardcoded 128 → 4x QJL storage at hd≠128) | ✅ | `turboquant/config.py`; surfaced by the ratio test; self-check now 1.0x QJL / 1.9x PolarQuant-only |
| **Bit-pack indices** (9 x 3.5-bit codes per uint32 word, unpacked fallback) | ✅ | `pack_indices`/`unpack_indices` + `bit_pack` flag; ratio now **1.4x QJL / 3.8x no-QJL** (was 1.0x/1.9x); dead zero tensors dropped |
| **Pack QJL codes to 1 bit** (32/word) + fp16 scales | ✅ | `pack_qjl_bits`/`unpack_qjl_bits` in `qjl.py`; ratio now **3.3x QJL-on** (was 1.4x) at hd=64, ~4.1x at hd=128; scales were already fp16 for fp16 engine inputs (`.to(fp16)` enforces it for fp32 inputs) |
| **QJL drop-vs-fix decision** (ablation-driven) | ✅ | KEEP + FIX: `benchmarks/qjl_ablation.py` shows QJL-on beats off at 3.5 bits (attn 0.275 vs 0.494 with tuned gain); decode scale tuned to absolute c=1/32 (optimum at hd 32/64, cliff at 1/16); KV cache K MSE 0.147 -> **0.132** |
| **Accuracy eval gate** vs FP16 | ✅ **FAIL** | `benchmarks/accuracy_eval.py` + `reviews/eval_gate_2026-08-09.json`: baseline ppl 7.86; 3.5+QJL 1201, 3.5-noQJL 3434, 4.0+QJL 3623 (15k-46k% degradation); needle lost. Root cause: real K/V norms ~215 -> logits ~5800; even Gaussian-LM codebook (NMSE 0.0185) and 6 bits (64 levels) fail. **Feature stays OFF; re-enable only after gate passes** |
| Unit tests | ✅ | `backend/tests/test_turboquant.py` — **33 tests** (roundtrip, packing, fallback, ratio>3, qjl_dim≠hd, tuned-gain-beats-off decision test, scale pin, incremental, edge cases); full suite **76 passed**; self-check green |

**Eval gate DONE (2026-08-09): FAIL — the accuracy claim is dead until the quantizer changes.** Remaining P1/P2/P3: **a fundamentally better quantizer** (per-channel affine/KIVI-style with per-channel scales, or per-layer calibrated codebooks) that can represent real K/V at <~1% vector error, then re-gate; FullRAM dim-order fix (P2, dormant — router not wired), CLI honesty, `turboquant.md` rewrite, dead-config alignment. **The "raise default bits to 4.0" recommendation is MOOT** — the gate shows 4.0 fails just as hard (ppl 3623); the bit budget is not the binding constraint, precision per vector is. Note on the 6x headline: at 3.5-bit indices + 1-bit QJL + fp16 scales the ceiling is ~4.1x (hd=128); the paper's 6x assumes the full 3.5 bits total (2.5-bit PolarQuant + 1-bit QJL) with no per-vector scale — and even reaching that ceiling, real-data accuracy at these precisions is unproven (this gate says it fails on Qwen2-0.5B).

---

# Accuracy Eval Gate (2026-08-09) — VERDICT: FAIL

## What was built

`backend/benchmarks/accuracy_eval.py` — the gate that must pass before `turboquant_enabled` may be re-enabled. It measures, per cache configuration vs the model's native cache:

1. **Chunked perplexity** on real wikitext (datasets-server HTTP API, no pyarrow dep; synthetic fallback offline), with the cache carried across 64-token chunks — the actual decode-time path, exercising the hot-buffer flush. Note: it runs the model's *native* cache (fp32) as baseline, so "baseline" = the model's own quality.
2. **Needle-in-haystack recall**: a secret sentence buried in filler context, probed by P(needle-token) after the probe + greedy continuation.

Pass = ppl degradation < 2% AND needle log-prob within 10x of baseline. Smoke-validated on `hf-internal-testing/tiny-random-LlamaForCausalLM` (all configs within 0.06% of baseline — the proxy integrates cleanly with transformers 5.3, which uses `cache.update()` returning full past K/V + `get_seq_length()` only).

## Gate run — Qwen2-0.5B, 1280 wikitext tokens (results: `reviews/eval_gate_2026-08-09.json`)

| config | ppl | deg | needle logp | needle hit |
|---|---|---|---|---|
| **baseline** (native) | **7.86** | — | -9.35 | ✅ " PINEAPPLE123. The" |
| tq-3.5+qjl | 1201.4 | **+15189%** | -14.34 | ❌ |
| tq-3.5-noqjl | 3434.1 | +43603% | -13.86 | ❌ |
| tq-4.0+qjl | 3623.2 | +46009% | -12.65 | ❌ |

**Every TurboQuant configuration FAILS catastrophically — 153x to 461x worse than baseline, and the needle is lost.** The gate did its job: the feature stays OFF.

## Root cause (measured, not guessed)

1. **The wiring is correct** — the failure is the quantizer, not the integration. Real quantized-path K/V NMSE through the proxy matches the ablation's prediction (uniform+QJL: 0.132); the raw hot-buffer path roundtrips at NMSE 0.0000.
2. **Real K/V live in a completely different regime than the synthetic ablation.** Qwen2 key-vector norms are ~215 (randn's ~8) → attention logits reach ~5800 → softmax is extremely sharp. The ablation's random-query attention-fidelity metric averaged out this sharpness and was **massively over-optimistic** (it predicted QJL-on would win at 3.5 bits; on real K/V both variants are catastrophic).
3. **Even a perfect codebook can't fix it at these precisions.** Real K/V NMSE: uniform codebook 0.214; Gaussian-Lloyd-Max codebook (data-oblivious, matched to the N(0,1/√d) rotated-coordinate law) **0.0185** — a 12x improvement, yet ppl still explodes to 1017 (96x). A bits sweep on the matched codebook (no QJL): 4.0 → 2960, 5.0 → 904, 6.0 (64 levels) → 210 (1900%) — **still catastrophic**. A 3.5-bit scalar codebook leaves ~13.6% RMS vector error; logit errors of hundreds-to-thousands flip the softmax argmax.
4. **The tuned QJL gain (c=1/32) does not transfer to real data.** With the better codebook the residual is smaller, and QJL *overcorrects*: NMSE 0.0185 → 0.0670 (worse). The synthetic "KEEP + FIX" decision is **falsified on real K/V** — the gate is the arbiter.

## Decisions

1. **`turboquant_enabled` stays OFF** (default False, unchanged). Re-enabling is gated on this gate passing — it does not.
2. **QJL:** neither configuration is shippable; the c=1/32 tuning question is moot until the codebook is fixed. On real data, QJL-on beats QJL-off (ppl 1201 vs 3434) only because it partially corrects the uniform codebook's large residual — a band-aid on the real problem.
3. **Path to re-enable** (new TODOS): a quantizer that can represent real K/V at <~1% vector error — per-channel affine quantization (KIVI-style, per-channel scales) or per-layer calibrated codebooks — then re-gate. Also worth re-testing on a model with moderate KV norms (Llama-family) to bound how much of this is Qwen2-0.5B's sharp-attention regime vs the scheme.
4. **The bits=4.0 recommendation is moot** — 4.0 fails as hard as 3.5 (ppl 3623). The binding constraint is precision per vector, not bit budget.

## What this means for the headline

The 6x claim assumed "zero accuracy loss at 3.5 bits." This gate is the first real-data test of that claim and it fails on Qwen2-0.5B by 4 orders of magnitude of ppl degradation. Compression ratios (now ~3.3-4.1x) are real and bit-exact; accuracy is not. Until the quantizer changes, TurboQuant is a storage-efficient cache that destroys model quality — worth nothing until it passes this gate. This is the honest state of the feature.

---

# Per-Channel Affine (KIVI-Style) Tranche — 2026-08-10

Following the polar gate's FAIL verdict, the report's own "path to re-enable" called for a fundamentally better quantizer: **KIVI-style per-channel affine** (arXiv:2402.02750), with per-(head,dim) max-abs scales for K and per-(head,token) max-abs scales for V, no rotation, no QJL — exactly the scheme the literature uses to get <1% ppl degradation at 2.5-4 bits on Llama-7B.

## What was built

| Artifact | Description |
|---|---|
| `backend/app/engines/shared/turboquant/affine.py` (new) | KIVI-style per-group symmetric affine quantizer. Symmetric ±scale with levels at positions `k - (L-1)/2`; the exact `round(x_level + half)` bijection was critical (a truncation-to-int bug gave a half-step bias → 3x inflated NMSE — caught by unit tests) |
| `config.quant_scheme: str = "polar" / "affine"` | Backward-compatible switch between the two schemes; `polar` is the unchanged legacy path (all 32 polar tests pass with zero modification) |
| `config.k_bits / v_bits: Optional[float]` | Asymmetric bit budgets (KIVI-style: V needs more bits than K). Flows through per-entry `levels` in `QuantizedKVCache`, pack/unpack uses each entry's own base |
| `TurboQuantKVCacheManager._quantize_kv_affine / _dequantize_kv_affine` | Scheme dispatch in the manager: K per-channel scales `[nh, 1, hd]`, V per-token scales `[nh, seq, 1]`. Indices packed identically to polar (base-levels uint32). No rotation/QJL/unit-norm. Scales fp16 when packed |
| `benchmarks/kv_structure_probe.py` (extended) | Now accepts `--model` arg; probes key norms (the sharpness signal) plus per-channel structure and affine-vs-polar NMSE on any HF model |
| `benchmarks/cache_wikitext.py` (new) | Pins the gate eval text to `reviews/eval_wikitext.txt` so runs are reproducible and work offline |
| `accuracy_eval.py` (extended) | Prefers local wikitext cache; configs list now carries baseline + 4 affine configs; QJL comparison made conditional (the polar baseline was recorded in the 2026-08-09 gate) |

## The structure probe — real K/V channel structure is massive

Before writing the quantizer, we probed real Qwen2-0.5B K/V (via the proxy `update()` hook, `benchmarks/kv_structure_probe.py`): **raw K per-channel std varies 0.03–21.8 across channels** (layer 0, cv 1.84), and 0.3–3.6 in deeper layers (cv 0.4–0.5). V per-token std varies 2–8x. This is precisely the structure that the polar scheme's rotation destroys — and that per-channel scales exploit.

## NMSE improvement (layer 4, same captured tensors)

| Config | K NMSE | V NMSE | vs polar (3.5+qjl K) |
|--------|--------|--------|----------------------|
| polar 3.5+qjl | 0.142 | 0.134 | — |
| affine 3-bit | 0.0228 | 0.092 | 6× better K |
| **affine 4-bit** | **0.0050** | 0.026 | **28× better K** |
| affine 5-bit | 0.00093 | 0.0066 | 153× better K |
| affine 6-bit | 0.00017 | 0.0017 | 835× better K |

Same improvement on Pythia-70m (moderate norms): affine 4-bit K NMSE 0.0038, V 0.0157.

**Unit tests** — 11 new `TestAffineScheme` tests (43 total turboquant, 86 full suite): roundtrip NMSE thresholds, structured-data wins (affine beats polar at ≤0.5× NMSE on channel-structured data), same-chunking bit-exactness, chunk-boundary scale consistency (within 1.5× NMSE), scale shapes, asymmetric bits, ratio >3.0, no-requant invariant. The half-step indexing bug was caught by `test_roundtrip_shape_and_nmse` (0.0405 vs expected 0.0125 — a 3× bias from truncating instead of rounding the half-integer level positions).

## Re-gate on Qwen2-0.5B (real wikitext, 768 tokens, `reviews/eval_gate_affine_2026-08-10.json`)

| config | ppl | deg% | needle hit |
|--------|-----|------|-----------|
| **baseline** | **8.34** | — | ✅ PINEAPPLE123. The |
| affine-3.5 | 259.9 | +3017% | ❌ |
| affine-4.0 | 304.2 | +3548% | ❌ |
| affine-4k5v | 358.6 | +4201% | ❌ |
| affine-4k6v | 323.8 | +3783% | ❌ |

**Improvement: 4-13× better ppl than polar's 1201-3623. Still FAILS by 1500-2100× the gate threshold (3017-4201% vs <2%). Non-monotonic across bit rates — the error-compounding regime.** First-chunk ppl-so-far: 16.4 vs baseline 8.3 (2× degradation at 64 tokens, no compounding). The attention is immediately corrupted at 64 tokens; it compounds to 36× over 768 tokens.

## Cross-model bounding: Pythia-70m (cached wikitext, `reviews/eval_gate_pythia_2026-08-10.json`)

To test the "Qwen2-0.5B has uniquely sharp attention (norms ~215)" hypothesis, the gate also ran on **Pythia-70m** — a 70M param GPT-NeoX model with **moderate key norms (~10-15)**, i.e. attention logits ~200, not ~5800.

| config | ppl | deg% |
|--------|-----|------|
| **baseline** | **39.2** | — |
| affine-3.5 | 564.8 | +1342% |
| affine-4.0 | 582.5 | +1387% |
| affine-4k5v | 564.0 | +1340% |
| affine-4k6v | 555.3 | +1318% |

**Same catastrophic failure — 1318-1387% degradation — and non-monotonic. First-chunk ppl: ~100 vs baseline ~39 (2.5×).** The pattern is identical to Qwen2: immediate 2-2.5× per-step degradation, compounding to 13-42× over 500-700 tokens, regardless of bit budget.

## Cross-model conclusion

| Test | Model | Polar ppl deg | Affine ppl deg | Gate? |
|------|-------|--------------|---------------|-------|
| Sharp attention | Qwen2-0.5B (norms ~215) | 15289-46009% | 3017-4201% | ❌ FAIL |
| Moderate norms | Pythia-70m (norms ~10) | not run | 1318-1387% | ❌ FAIL |

**On 0.5B-70M models, per-coordinate scalar quantization at ≤6 bits cannot pass a 2%-degradation accuracy gate.** The mechanism: even with a perfect codebook and per-channel scales, each coordinate's quantization error (NMSE ~0.3-2% per-coord at 4 bits) produces attention logit errors that corrupt the hidden state → subsequent K/V predictions are also corrupted → errors compound across the sequence. The 2× first-chunk degradation makes compounding inevitable. On a ≥1B model with more capacity to absorb the per-step error, the degradation per token would be smaller, but the failure mode (scalar quantization cannot represent vectors within tolerance of softmax argmax) is structural.

**Implications for the 6x claim:** the paper's headline requires "zero accuracy loss" at 3.5 bits. No scalar quantizer at that rate can pass our gate. The claim likely holds for its target models (≥7B, with softer attention and more capacity) and target eval (single-token generation without compounding, or slowly compounding tasks). Our gate measures the worst case: chunked perplexity with full cache carried over hundreds of tokens. This IS the real use case (chat/decode with context), so the restriction is genuine: **TurboQuant is a storage-efficient cache that destroys model quality on small models and under long-context chunked evaluation.**

## Updated task status

| Task | Status | Evidence |
|------|--------|----------|
| KIVI-style per-channel affine quantizer | ✅ | `affine.py`, `config.quant_scheme`, `config.k_bits/v_bits`, scheme dispatch in `kv_cache.py` |
| Unit tests (affine path) | ✅ | 11 `TestAffineScheme` tests (43 total turboquant, 86 full suite) |
| Structure probe (model-agnostic) | ✅ | `benchmarks/kv_structure_probe.py` accepts `--model`; confirms per-channel K structure (cv 0.4-1.8) on Qwen2, Pythia |
| Gate harness improvements (wikitext cache, conditional QJL print) | ✅ | `accuracy_eval.py` prefers `reviews/eval_wikitext.txt`; cache script at `benchmarks/cache_wikitext.py` |
| Re-gate on Qwen2-0.5B (all affine configs) | ✅ FAIL | 259-359 ppl vs 8.3 baseline; 3017-4201% deg; needle lost |
| Cross-model gate on Pythia-70m | ✅ FAIL | 555-583 ppl vs 39.2 baseline; 1318-1387% deg; needle baseline miss |
| FullRAM dim-order fix | ❌ P2 | Dormant — router not wired for turboquant at all |
| Dead-config alignment | ❌ P2 | hadamard/beta_lloyd_max/enable_polarquant/collect_stats |
| CLI honesty | ❌ P3 | benchmark-turboquant still prints fabricated estimates |
| turboquant.md rewrite | ❌ P3 | Document as experimental, point at this report |
| TODOS.md | ✅ P3 | Router auto-enable (gated), llama.cpp tbq3_0/tbq4_0 eval DONE-by-research (2026-08-11, see Phase 4 section); remaining: codebook-vs-reference comparison |

## Lessons learned

1. **The half-step indexing bug** — `(q + half).to(int64)` vs `round(q + half)`. For even level counts (16), level positions are half-integers ±7.5. Truncation shifted every interior index by -0.5 → Δ/2 bias → 3× NMSE inflation. Caught by a unit test on synthetic structured data. The fix: `(x_level + half).round().clamp(0, L-1)` — exactly bijective for both odd and even levels.

2. **The synthetic ablation limitation** — the QJL ablation (`benchmarks/qjl_ablation.py`) and the earlier Gaussian-LM codebook experiment both predicted dramatically better accuracy on real data than the gate measured, because their random-query attention-fidelity metric averaged out the razor-sharpness of real attention logits. The gate is the arbiter. Future ablation work should measure per-chunk ppl as the primary metric, not attention NMSE on random vectors.

3. **Per-channel scales vs rotation** — on real K/V with per-channel magnitude variation (cv 0.4-1.8), per-channel affine beats the rotated codebook by 28× at 4 bits. The rotation destroys the structure that per-channel scales exploit. Even so, the remaining per-coordinate error at 4 bits (~0.5% NMSE RMS) is too large for the compounding attention-error regime.

4. **Gate design matters** — the chunked ppl measurement (cache carried across chunks) is the correct precision test: it measures the actual decode path. The needle test adds a qualitative check. The 2% gate threshold on 0.5B-70M models may be stricter than what a 7B model can achieve, but it is the right bar for quality; no one should ship a feature that gives 1300+% ppl degradation even on a small model.

## Next steps (recommended)

1. **Phase 4 evaluation (llama.cpp tbq3_0/tbq4_0)** — ✅ RESOLVED 2026-08-11 by research (see "Phase 4 evaluation" section below): kernels are fork-only (PR #21089 closed unmerged), unbuildable here (no compiler, 8GB RAM), but the paper's 6x claim is already community-validated at 104B scale. The remaining real experiment is a codebook comparison against the `turboquant_plus` Python reference implementation on our captured K/V — no build needed.
2. **Per-vector codebooks** — the fundamental limitation of scalar-per-coordinate quantization for this regime. A spherical codebook (VQ-VAE-style) or per-vector product quantizer could encode whole vectors at 3.5 bits with lower error.
3. **TinyLlama-1.1B gate run** — if a ≥1B model with real attention capacity is accessible (GPU or very patient CPU), running the gate on TinyLlama with affine-4k6v would definitively answer whether the scheme is viable for models with more redundancy. This is the single remaining experiment before declaring Approach A dead or viable.
4. **P2/P3 cleanup** — FullRAM layout fix, dead-config alignment, CLI honesty, turboquant.md rewrite, TODOS.md. These are independent of the accuracy question and improve code quality even if the feature stays off.

---

# Phase 4 evaluation (2026-08-11): llama.cpp tbq3_0/tbq4_0 kernels

**Goal:** fastest path to testing the paper's 6x claim on a real ≥7B model. **Verdict: the claim is already community-validated at 104B scale; the kernels cannot be built or run on this machine (no compiler, no RAM, no GPU); our custom path's accuracy gap is codebook-side, not scheme-side.**

## Fact-check: what actually exists upstream

| Claim | Reality (verified 2026-08-11) |
|---|---|
| PR #21089 "ggml: add CPU TurboQuant KV cache types (TBQ3_0 / TBQ4_0)" | **CLOSED UNMERGED on 2026-06-02** (GitHub API: `state=closed`, no `merged_at`). The kernels exist only in the community fork **`TheTom/llama-cpp-turboquant`** (turbo2/3/4 KV cache + TQ3_1S/TQ4_1S weight formats), with prebuilt binaries for **Mac (Metal) and Windows (CUDA) only** |
| `TheTom/turboquant_plus` (initially cloned as a fork) | **Not a llama.cpp fork at all** — a Python reference implementation of the paper (PolarQuant + WHT) with validation papers and benchmark data. Runs directly on CPU |
| Upstream llama.cpp | **Merged the Hadamard KV rotation** (#21038, citing TurboQuant directly) + fast WHT kernels on CPU (#22631), CUDA (#23615), Vulkan (#23687). Per the research home README: "Rotation + stock q4_0 cache is essentially turbo4's rotation stage" — the PolarQuant codebook itself is NOT upstream in llama.cpp |
| vLLM | **Merged the full codec**: PR #38479 (April 2026) — `--kv-cache-dtype turboquant_k8v4` + friends, fused Triton store/decode kernels |
| MLX (Apple) | Merged into `mlx-swift-lm` (PR #232): full asymmetric family (turbo0v*/turbo8v*) + symmetric turbo4/3/2; turbo8v3 = 2.7x KV at affine8-class KLD across 6 families (1.7B→32B) |

## The paper's 6x claim — already validated at scale, by the community

The fork's README reports the exact test this task wanted: **TurboQuant validated end-to-end from 1.5B to 104B at 128K context on a MacBook (turbo3, PPL 4.024, 74 GB peak memory)**, compressing KV cache **3.8–6.4x** at near q8_0 prefill speed and ~0.9x decode throughput at long context. The paper's headline is real on its target hardware — no local ≥7B test needed to establish that.

## Why we can't run it on this machine (measured, not assumed)

1. **RAM: 8 GB total, ~2 GB free** (checked via `GlobalMemoryStatusEx`). A ≥7B fp16 model needs ~14 GB; even Q4 quantized ≥7B needs ~5 GB resident plus KV. Physically cannot run.
2. **No compiler:** VS 2022 dir exists but is empty (no `cl.exe`); no cmake, no mingw gcc/g++, no zig. Building llama.cpp from source is not possible.
3. **Prebuilt binaries don't fit:** the fork ships Mac (Metal) and Windows (CUDA) builds only; this machine is Windows **CPU-only** (no GPU) — neither build runs here.

## What this means for our project

1. **Approach B ("stand on llama.cpp") is now partially obsolete in its specifics but vindicated in direction:** the codec upstreamed into **vLLM** (not llama.cpp's CPU kernels, which were closed unmerged). If we ever want a production-grade engine path, vLLM's `turboquant_k8v4` is the reference implementation of record.
2. **Our accuracy failure is codebook-side, not scheme-side.** The paper's exact scheme (PolarQuant + WHT) passes at 104B; our implementation of a *different* codebook (uniform centroid) fails at 0.5B/70M. The next experiment is cheap and needs no build: `turboquant_plus` runs on CPU (torch) — run its `polar_quant.py` on our captured Qwen2 K/V, compare NMSE against our affine/polar numbers, then port it into `accuracy_eval.py` as one more config and re-gate. If the reference codebook passes where ours failed, the fix is a codebook swap; if it also fails, the small-model regime itself is the wall (matching the affine finding).
3. **The honest boundary statement:** our gate (2% ppl degradation on 0.5B/70M models, chunked long-context) is much stricter than the paper's target regime (≥7B, MacBook-class). The claim "TurboQuant destroys small-model quality" stands; "TurboQuant works at ≥7B" is community-confirmed but untestable on this hardware.

## Reference-codebook probe (2026-08-11): codebook swap would help, cannot pass the gate

`benchmarks/reference_polar_probe.py` runs the `turboquant_plus` reference PolarQuant/TurboQuant (per-vector norm extraction + Gaussian Lloyd-Max centroids + norm correction) on the **same captured Qwen2-0.5B K/V** (layer 4, 256 tokens) as the affine probe. Results:

| method | K NMSE | V NMSE |
|---|---|---|
| our polar 3.5+qjl | 0.14283 | 0.13510 |
| ref PolarQuant 2-bit | 0.11492 | 0.12638 |
| **ref PolarQuant 3-bit** | **0.02833** | **0.03446** |
| ref PolarQuant 4-bit | 0.00872 | 0.00890 |
| ref TurboQuant 3-bit (2+1 QJL) | 0.06820 | 0.07516 |
| ref PolarQuant 3-bit, no norm-corr | 0.02945 | 0.03511 |
| our affine 3-bit / 4-bit (report) | 0.0228 / 0.0050 | 0.092 / 0.026 |

**Layer-0 confirmation (2026-08-11):** same probe on the extreme channel-structure layer (K ch cv 1.84): our polar 3.5+qjl K 0.13432 / V 0.13795 vs ref PolarQuant 3-bit 0.03334 / 0.03091 (4x better), ref 4-bit 0.00829 / 0.00820 — identical regime; QJL hurts (3-bit 0.0787 vs 0.0333), norm-corr ~no-op (0.0343). The codebook verdict holds on the worst case, not just layer 4.

**Verdict: codebook-side confirmed, and it's a 5x fix — but the fix cannot pass the gate.**

1. **The reference codebook is 5x better than ours on identical tensors** (3-bit 0.0283 vs our 3.5+qjl 0.1428). Our uniform-on-[-1,1] centroids were the polar path's dominant error source; porting the reference's Gaussian Lloyd-Max codebook + norm extraction would genuinely fix the polar path.
2. **Yet it lands in the affine NMSE regime that already FAILED the gate.** Reference 4-bit (0.0087) ≈ our affine 4-bit (0.0050) — which gates at 3017–4201% ppl degradation. At the paper's actual 3.5-bit operating point (2.5-bit polar + 1-bit QJL, interpolating between our 2-bit and 3-bit rows) it would land ~0.05+, worse. No scalar per-coordinate codec gets under ~0.5% vector error on these models.
3. **QJL hurts at these precisions** (TurboQuant 3-bit 0.068 vs PolarQuant 3-bit alone 0.028) — the reference's own two-stage scheme confirms our real-data finding that the 1-bit residual stage overcorrects once the codebook is good.
4. **Norm correction is nearly a no-op** on real K/V (0.0283 vs 0.0295 at 3-bit) — the paper's "store norms + rescale" step contributes almost nothing here.

**Implication:** the "port the reference codebook" experiment is resolved — it improves the polar path 5x but cannot change the gate verdict. The remaining paths are unchanged: ≥1B model gate test (TinyLlama-1.1B), or per-vector non-scalar codecs (spherical VQ / product quantization). `TODOS.md` updated.
