# SovereignAI Research Results — Aggregated Benchmark & Review Data

> Aggregate of all measured research, eval gates, and autoplan reviews performed
> 2026-08-09 through 2026-08-17. Numbers pulled verbatim from `reviews/*.json` and
> `reviews/*.md`. No fabricated values — every cell below is grounded in a cited artifact.

Sources:
- `reviews/benchmark-2026-08-14.md` — LayerStream end-to-end throughput (incl. 08-17 device-cache fix)
- `reviews/perf-research-2026-08-11.md` — whole-app perf audit
- `reviews/eval_gate_2026-08-09.json` — TurboQuant box eval, Qwen2-0.5B
- `reviews/eval_gate_affine_2026-08-10.json` — TurboQuant affine eval, Qwen2-0.5B
- `reviews/eval_gate_pythia_2026-08-10.json` — TurboQuant affine eval, Pythia-70m
- `reviews/eval_smoke.json` — smoke eval, tiny-random-Llama
- `reviews/autoplan-report-2026-08-09.md` — TurboQuant autoplan review
- `reviews/autoplan-report-2026-08-12.md` — whole-project autoplan review
- `reviews/completed-2026-08-12-to-2026-08-15.md` — closeout of 22-item TODO

---

## 1. LayerStream End-to-End Throughput

### 1.1 Headline result — Qwen3.5-0.8B, CPU-only, 2026-08-14
Source: `reviews/benchmark-2026-08-14.md` · Runner: `backend/benchmark_layerstream.py`

| Metric | Value |
|---|---|
| Model | Qwen-Qwen3.5-0.8B (hybrid linear+full attn, 1.9 GB split on disk) |
| Hardware | dev box, 8 GB RAM (~2 GB free), CPU-only (no CUDA) |
| Prompt / generated tokens | 10 / 32, temperature 0.7 |
| Load time | 4.4 s |
| **Tokens/second** | **0.40 tok/s** |
| Peak RAM | 2.30 GB (baseline 0.46 GB → +1.84 GB resident) |
| Disk read time | 7.73 s (864 layer loads, avg 9 ms/load) |
| Compute time | 77.83 s (98% of wall time) |

Read: sub-1 tok/s → unusable interactive chat. Memory economics work (1.9 GB model
→ 2.30 GB peak RSS), but CPU decode is the wall.

### 1.2 CPU vs GPU+fla follow-up — 2026-08-15
Same model, same prompt; GPU = GTX 1650, torch 2.5.1+cu124, triton-windows, fla 0.2.2.

| Metric | CPU (08-14) | GPU + fla (08-15) | Δ |
|---|---|---|---|
| Tokens/second | 0.40 | 0.38 | −0.02 (zero) |
| Compute time | 77.8 s | 83.1 s | +5.3 s |
| Disk read time | 7.7 s | 5.0 s | −2.7 s |

Kernels never engaged — zero delta. transformers' Qwen3_5 fast path requires
`all(causal_conv1d_fn, causal_conv1d_update, chunk_gated_delta_rule,
fused_recurrent_gated_delta_rule)`; fla alone insufficient. `causal-conv1d`
unbuildable on this box (0 Windows wheels on PyPI/GitHub, no nvcc/MSVC). All 18
linear-attention layers ran pure-torch fallback on 4 GB Turing card ≈ CPU speed,
plus per-token RAM→VRAM swap overhead. Needs Linux CUDA box or global CUDA Toolkit
+ VS Build Tools.

### 1.3 Device-cache fix — 2026-08-17
Per-token decode was re-dequantizing the entire model on GPU every token: profiled
259 ms dequant/assign of a 380 ms decode step (68%) on Qwen2-0.5B int4. Added a
bounded VRAM LRU of dequantized (compute-dtype) tensors (budget = half free VRAM;
CPU boxes unchanged, budget 0). Also fixed an int4 shape-collapse crash
(`offload_weights` shrinks params to `torch.empty(0)` → dequant reshape target
became `(0,)` on the 2nd pass) and restored missing tokenizer files in the three
`bench-Qwen-Qwen2-0.5B*` split dirs.

Same box as 1.2 (GTX 1650, CUDA), `benchmark_layerstream.py`, 32 tokens:

| Model / split | Before | After | Δ | Peak RAM |
|---|---|---|---|---|
| Qwen2-0.5B fp16 | 1.05 tok/s | **5.02 tok/s** | +4.8x | 1.89 GB |
| Qwen2-0.5B int8 | 1.08 tok/s | **4.49 tok/s** | +4.2x | 1.65 GB |
| Qwen2-0.5B int4 | 2.09 tok/s | **8.00 tok/s** | +3.8x | 1.73 GB |
| Qwen3.5-0.8B hybrid | 0.13 tok/s | **0.48 tok/s** | +3.7x | 2.21 GB |

RAM bounding preserved: packed form stays in the CPU cache, compute-dtype form in
VRAM under the budget. The Qwen3.5 hybrid ceiling is still the missing
`causal-conv1d` kernels (18 linear-attention layers on pure-torch fallback), not
LayerStream I/O (disk = 2–9% of wall time throughout). 112 tests pass.

---

## 2. TurboQuant Eval Gates — 4 gates, all FAIL

TurboQuant compression **does not meet its headline claim** in any eval. Paper
target: ~6x @ 3.5 bits, zero accuracy loss. Shipped code: ~0.98x compression
(uint8 idx + int8 qjl + float32 scale = ~2.03 B/coord vs FP16 2 B/coord), lossy,
slower. All four gates recorded below.

### 2.1 Gate 1 — Qwen2-0.5B, original box scheme, 2026-08-09
Source: `reviews/eval_gate_2026-08-09.json` · 1280 tokens

| Label | bits | QJL | Perplexity | needle_logp | needle_hit | seconds |
|---|---|---|---|---|---|---|
| baseline | — | — | 7.86 | −9.35 | **true** | 29.83 |
| tq-3.5+qjl | 3.5 | on | 1201.39 | −14.34 | false | 47.53 |
| tq-3.5-noqjl | 3.5 | off | 3434.10 | −13.86 | false | 46.88 |
| tq-4.0+qjl | 4.0 | on | 3623.22 | −12.65 | false | 53.82 |

Perplexity blowup: 7.86 → 1201–3434 (153x–437x worse). All quantized variants miss
needle. Slowest variant 53.82 s vs baseline 29.83 s (+80%).

### 2.2 Gate 2 — Qwen2-0.5B, affine scheme, 2026-08-10
Source: `reviews/eval_gate_affine_2026-08-10.json` · 704 tokens, wikitext

| Label | bits | v_bits | Perplexity | needle_logp | needle_hit | seconds |
|---|---|---|---|---|---|---|
| baseline | — | — | 8.34 | −9.35 | **true** | 32.41 |
| tq-affine-3.5 | 3.5 | 3.5 | 259.87 | −15.52 | false | 43.03 |
| tq-affine-4.0 | 4.0 | 4.0 | 304.16 | −16.10 | false | 36.24 |
| tq-affine-4k5v | 4.0 | 5.0 | 358.58 | −18.25 | false | 37.87 |
| tq-affine-4k6v | 4.0 | 6.0 | 323.78 | −16.19 | false | 49.48 |

Perplexity blowup: 8.34 → 260–359 (31x–43x worse). All quantized variants miss
needle. Asymmetric v_bits does not help (4k6v best perplexity still 323.78).

### 2.3 Gate 3 — Pythia-70m-deduped, affine scheme, 2026-08-10
Source: `reviews/eval_gate_pythia_2026-08-10.json` · 448 tokens, wikitext-cache

| Label | bits | v_bits | Perplexity | needle_logp | needle_hit | seconds |
|---|---|---|---|---|---|---|
| baseline | — | — | 39.17 | −13.91 | false | 2.64 |
| tq-affine-3.5 | 3.5 | 3.5 | 564.81 | −16.55 | false | 6.07 |
| tq-affine-4.0 | 4.0 | 4.0 | 582.49 | −12.18 | false | 9.21 |
| tq-affine-4k5v | 4.0 | 5.0 | 564.01 | −12.67 | false | 8.74 |
| tq-affine-4k6v | 4.0 | 6.0 | 555.34 | −12.43 | false | 7.54 |

Perplexity blowup: 39.17 → 555–582 (14x worse). Baseline misses needle (model too
small for needle task), all variants slower. Scalar quantizers structurally can't
pass the 2% gate on small models — root cause: codebook uses uniform centroids,
not Beta Lloyd-Max per the paper.

### 2.4 Gate 4 — tiny-random-Llama, smoke, 2026-08-10
Source: `reviews/eval_smoke.json` · 256 tokens, wikitext

| Label | bits | QJL | Perplexity | needle_logp | needle_hit | seconds |
|---|---|---|---|---|---|---|
| baseline | — | — | 31979.67 | −10.31 | false | 0.17 |
| tq-3.5+qjl | 3.5 | on | 31960.69 | −10.31 | false | 0.29 |
| tq-3.5-noqjl | 3.5 | off | 31960.18 | −10.31 | false | 0.21 |
| tq-4.0+qjl | 4.0 | on | 31966.62 | −10.31 | false | 0.27 |

Random model → perplexity meaningless; variant perplexities within 0.05% of
baseline. Confirms no crash on tiny model, says nothing about accuracy. QJL
on/off changes nothing at this scale (scaling off by sqrt(d') → near no-op).

### 2.5 Cross-gate summary
Gate acceptance threshold: perplexity within 2% of baseline, needle preserved.

| Gate | Model | Scheme | Baseline ppl | Best TQ ppl | Δ ppl | Verdict |
|---|---|---|---|---|---|---|
| 1 (08-09) | Qwen2-0.5B | box+QJL | 7.86 | 1201.39 | +15276% | FAIL |
| 2 (08-10) | Qwen2-0.5B | affine | 8.34 | 259.87 | +3015% | FAIL |
| 3 (08-10) | Pythia-70m | affine | 39.17 | 555.34 | +1318% | FAIL |
| 4 (08-10) | tiny-Llama | box+QJL | 31979.67 | 31960.18 | −0.06% | SMOKE only |

**All four gates FAIL** on real models (gate 4 is crash-smoke, not accuracy).
Compression ratio across all: ~0.98x (target 6x). Feature flipped default-OFF
(`config.py: turboquant_enabled=False`). Decision: park as research until a
quantizer shows <1% vector error on real K/V at ≥1B params.

---

## 3. Whole-App Performance — React / Electron / Streaming / Backend
Source: `reviews/perf-research-2026-08-11.md`

### 3.1 Optimization ranking by bang for buck in this codebase
| # | Item | Reality | Status |
|---|---|---|---|
| 1 | Batch token updates in React (rAF flush) | **biggest win** — `useChat.ts` called `setMessages` per token | DONE 08-11 |
| 2 | Memoize chat message rows (`React.memo` `MessageItem`) | pairs with #1; `ReactMarkdown` re-parsed every message every tick | DONE 08-11 |
| 3 | Deserialize Electron boot (window before backend resolves) | bigger than V8 snapshot — `main.js` awaited backend before window | DONE 08-11 |
| 4 | Window the chat tail (skip `react-window`) | conditional; memo + batching makes it O(tail) already | NOT NEEDED (conditional) |
| 5 | Dedup `/status` fetches + throttle metrics WS | WS already 1/s server-side; dedup = dead code | MEASURED, REJECTED |
| 6 | `next/dynamic` heavy deps | modest; settings dialog already dynamic'd | DONE 08-11 |
| 7 | uvloop | not available on Windows; dep already correct | N/A |
| 8 | gzip/brotli on API | loopback + `file://`; net loss | REJECTED |
| 9 | SQLite WAL / pooling | already fully done (`connection.py:57-72`) | DONE prior |
| 10 | `apscheduler` vacuum every 5 min | doesn't exist; don't add — main-loop blocker | N/A |
| 11 | V8 snapshot Electron | macOS/Linux only; target is win32 | N/A |
| 12 | Splash flash / devtools | already done (`main.js:28,35,40`) | DONE prior |

### 3.2 Streaming hot path cost model (before fixes)
Per token tick at ~20–40 tok/s:
1. `setMessages` rebuilds whole array (`[...prev]`, `useChat.ts:194`)
2. `MessageList` re-renders (not memoized, `MessageList.tsx:147`)
3. Every message row re-renders inside `AnimatePresence` (each `motion.div`)
4. `ReactMarkdown` re-parses every message's content — O(N) markdown parses per token tick

Effective cost: O(N) markdown re-parse + DOM diff every ~30 ms while streaming.
After fixes #1+#2: streaming row re-renders once per frame, completed messages
never re-render or re-parse. Cost dropped to O(tail).

### 3.3 SSE frame batching
`chat.py:220-245` yielded one JSON-encoded SSE frame per engine token. After fix:
batches ~96 chars of tokens per frame. Frame count + JSON serialization cut ~10x.
Guarded by `backend/tests/test_stream_batch.py` (lossless reconstruction, finish
frame trails content). Reordering: deltas kept in order.

---

## 4. Autoplan Review — TurboQuant (`2026-08-09`) consensus
Source: `reviews/autoplan-report-2026-08-09.md`

### 4.1 Premises
| # | Premise | Verdict |
|---|---|---|
| P1 | TurboQuant ~6x KV @ 3.5 bits, zero loss | 🟢 paper real (arXiv 2504.19874, ICLR 2026) · 🔴 UNVERIFIED in impl (~0.98x, no eval) |
| P2 | Custom PyTorch TurboQuant right build | 🟠 challenged — llama.cpp tbq3_0/tbq4_0 (PR #21089) exists as Layer-1 alt |
| P3 | KV cache is the memory bottleneck | 🟡 half — FullRAM long-context yes; LayerStream caps KV 2048 MB + offloads to CPU |
| P4 | 3.5 bits + QJL right operating point | 🟠 wrong — Lloyd-Max-only beats two-stage QJL ≥3 bits; QJL adds 1 B/coord killing ratio |
| P5 | Default-on harmless | 🔴 wrong — config.py `turboquant_enabled=True`; ~1x compression = strictly worse (lossy, slower, no win) |

### 4.2 CEO / Eng / DX consensus tables
```
CEO: Architecture P? NO, Problem? YES*, Scope? NO, Alternatives? NO,
     Risks? YES, 6mo Trajectory? NO    → 4/6 CHALLENGE
ENG: Sound? NO, Tests? NO, Perf? NO, Security? YES, Errors? PARTIAL,
     Deployment? NO                    → CHALLENGE net-negative default
DX:  TTHW<5min? YES, Naming? YES, Errors? NO, Docs? NO, Upgrade? NO,
     DevEnv? YES                        → 3.9/10, TTHW~2min, trust~0min
```

### 4.3 Compression accounting (shipped)
```
PolarQuant: random QR rotation (hadamard config = dead flag)
Codebook:   UNIFORM centroids  ← plan said Beta Lloyd-Max (broken, replaced)
QJL:        decode divides by d', P normalized 1/sqrt(d') → net 1/d'^1.5 ≈ no-op
KV cache:   uint8 idx (1 B) + int8 qjl (1 B) + f32 scale (0.03 B) = 2.03 B/coord
            vs FP16 2 B/coord  →  0.98x   ← 6x claim UNMET
Missing:    bit-packing, incremental update() (shipped is O(n²)), tests, evals,
            engine_factory awareness (FullRAM turboquant unreachable)
```

`update()` O(n²): every new token dequantizes full history, concats, re-quantizes.
At 128K context each decode re-runs rotation over whole sequence — hits the exact
use case the feature exists for.

---

## 5. Autoplan Review — Whole Project (`2026-08-12`) consensus
Source: `reviews/autoplan-report-2026-08-12.md` · Commit `c849e95` · 106 tests pass (48.95s)

### 5.1 Premises
| # | Premise | Verdict |
|---|---|---|
| P1 | LayerStream runs 70B+ on 8GB usable speed | 🔴 unvalidated — dev box can't run 7B; sub-1 tok/s expected |
| P2 | Custom PyTorch over llama.cpp | 🟠 prior settled 08-05; ManualStream deleted regardless (dead weight) |
| P3 | 100% offline differentiator | 🟡 table stakes — Ollama/LM Studio/Jan all offline |
| P4 | USB portability wedge | 🟡 micro-segment; "zero-install" contradicts multi-GB torch/Node bundle |
| P5 | Air-gapped enterprise addressable early | 🟡 procurement/cert barriers; long-term lane |
| P6 | 3 UIs + plugins + RAG + 9 task modules in parallel w/ engine work | 🟠 sequencing risk — breadth before validation |

### 5.2 Wedge alternatives (0C-bis)
| Wedge | Effort | Risk | Reuses | Decision |
|---|---|---|---|---|
| A: OpenAI-compat offline server | S-M (CC ~2-3 hr) | Low | chat.py, model_manager, CLI, Electron | **RECOMMENDED** |
| B: Air-gapped RAG intel | M (CC ~1 day) | Med | vectorstore/, rag.py, documents, pdf plugin | second lane |
| C: no wedge, keep 3 UIs | M+ ongoing | High (regret trap) | nothing new | rejected |

### 5.3 Test coverage (verified 08-12)
| Codepath | Covered? | Gap |
|---|---|---|
| LayerStream loader / int4-int8 quant | `test_layerstream_loader.py` (264 lines) | — |
| LayerStream **executor** (swap, KV, split call) | None | 🔴 highest risk |
| FullRAM executor + fullram→layerstream fallback | None | 🔴 |
| Chat API e2e w/ real tiny model | None (CLI smoke/fake) | 🔴 |
| Plugin sandbox / RAG / WS / settings / auth | None | 🔴 |
| Frontend | None (no test runner) | 🔴 |
| TurboQuant (33 tests) | yes | default-off now |

### 5.4 Design litmus (7 dims) — 2026-08-12
| Dimension | Score | Note |
|---|---|---|
| 1 Information hierarchy | 5/10 | home hardware-first not chat-first |
| 2 Interaction states | 4/10 | no stop button, no no-model/loading/OOM |
| 3 First-run | 5/10 | no chat empty-state; model acqu online-only |
| 4 Responsive | 8/10 | md grids clean |
| 5 Accessibility | 4/10 | no `aria-live`, no skip-link, contrast unverified |
| 6 Specificity | 5/10 | chat surface real craft; generic shadcn elsewhere |
| 7 Design-system | 7/10 | Tailwind v4 tokens correct |

---

## 6. Closeout — Completed 2026-08-12 → 2026-08-15
Source: `reviews/completed-2026-08-12-to-2026-08-15.md`

**Verification:** backend suite **112 tests pass** (106 baseline + 6 new) ·
frontend `npm run build` green · CLI `sovereign --help` registers `import`.

### 6.1 P1 critical/high (all done)
| Item | What landed |
|---|---|
| Delete ManualStream | `engines/manualstream/` deleted (~1k lines); factory import + branch removed |
| Stop + disconnect cancellation | `AbortController`/`stop()` `useChat.ts`, Stop button `ChatModule`, `Request.is_disconnected()` `chat.py` |
| Hide speculative task modules | console renders ChatModule only; 6 non-exec modules unrendered |
| Reconcile stale docs | readme, TRD, AGENTS.md, CLAUDE.md — Next.js 16/React 19, honest LayerStream, no-SQLAlchemy |
| Auth + path safety | `security/middleware.py` Bearer (LAN only), `api_token`, `delete_model` rmtree guard, snapshot traversal rejection |
| OOM→507 + disk preflight + load lock | 507 in `/v1/models/load`, disk-space preflight, `asyncio.Lock` around loads |
| LayerStream benchmark | `benchmark_layerstream.py` + `benchmark-2026-08-14.md` — 0.40 tok/s, 2.30 GB peak Qwen3.5-0.8B |

### 6.2 P2 (all done)
| Item | What landed |
|---|---|
| Real-engine tests | `test_plugin_sandbox.py` (timeout) + full executor round-trip (below) |
| OpenAI-compat contract | `test_openai_compat.py` (4 tests) + endpoint documented |
| Fail loudly + gate remote code | `TaskRouter` raises on unknown/non-generative; `trust_remote_code` off default |
| Shrink task_router | 32 → `{causal_lm, seq2seq_lm}` |
| Factory create/load split | `create_engine` no longer loads; `ModelManager` owns load + errors; DEBUG prints gone |
| Pydantic v2 | `class Config` → `model_config = ConfigDict` |
| Chat lifecycle + OOM card | 507 "how to fix" bubble; stop control; input gated while generating |

### 6.3 P3 (all done)
| Item | What landed |
|---|---|
| `sovereign import <local.gguf>` | new CLI command (copy + registry refresh) |
| Structured logging | stdlib `logging` on error paths (`SOVEREIGN_LOG_LEVEL`); ~100 status prints remain |
| Repo hygiene | deleted `ts_errors*.txt`, `build_output*.txt`, `electron/build_linux_output.txt` + gitignored |
| Reload gating | `backend/main.py` reload dev-only (`SOVEREIGN_RELOAD=1`) |
| MemoryManager zones | dead zone bookkeeping deleted; `suggest_mode` kept |
| Home page chat-first + a11y | chat when model loaded, import hint, skip-link, `aria-live` |

### 6.4 Left open (documented decisions)
- gguf IQ2_BN patch — kept: no released gguf has the enum yet
- TurboQuant — parked research (U1 default-off stays)
- Tags/releases + pinned installer + CHANGELOG — needs release/deploy decision
- `llama-cpp-tq/` + `landing_page/` ownership — needs repo-ownership call
- Fast-attention delta — needs Linux CUDA box or global CUDA Toolkit + VS Build Tools

### 6.5 Bug found by follow-up test
`test_layerstream_roundtrip.py` (@slow fresh-split tiny Llama, generate_stream,
unload) exposed real bug: meta `rotary_emb` crash in `layer_executor.execute_forward`
— any non-hybrid Llama/Qwen2 model would have failed first generate. Fixed 08-15.

---

## 7. Honest当前位置 — what the numbers say

- **LayerStream usable today:** split by hardware. **CUDA + small model: yes** —
  Qwen2-0.5B int4 at **8.0 tok/s** (2.09 before the 08-17 device-cache fix), fp16
  5.0, int8 4.5; the 0.40 tok/s CPU number was a CPU-only box where the fix is
  inactive (device cache is CUDA-only). **CPU-only: still compute-bound** — decode
  is the wall, unchanged by this fix. **Hybrid Qwen3.5: 0.48 tok/s** — bounded by
  missing `causal-conv1d` kernels, not I/O.
- **70B-on-8GB claim:** unsupported by measurement. Re-positioned to **"3-8B Q4 on
  8 GB RAM"** — true, useful, measurable (GPU throughput for that scale still unmeasured; the VRAM cache holds only a recency window when the model exceeds the budget).
- **TurboQuant:** 4 eval gates FAIL on real models; perplexity 14x–437x worse;
  ~0.98x compression (target 6x). Default-OFF. Parked research.
- **Whole-app perf:** streaming path fixed (rAF + memo + SSE batching); cold-start
  fixed (window before backend); remaining wins measured-rejected (dead code).
- **Test suite:** 112 pass (up from 43 at 08-05, 106 at 08-12); executors + sandbox
  + RAG still zero coverage on production paths.
- **Wedge:** OpenAI-compatible offline server already 80% built; one deliverable
  with offline import + honest numbers is the lever, not more UI breadth.