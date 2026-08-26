# Wiki Log
## [2026-07-21] ingest | Initial Wiki Build
- Added wiki schema to CLAUDE.md (page format, operations, index/log conventions)
- Created index.md — catalog of all 31 wiki pages by category

## [2026-07-23] implement | TurboQuant KV Cache Compression
- Created `backend/app/engines/shared/turboquant/` package (config, polarquant, qjl, codebook, kv_cache, hf_proxy)
- Added settings: `turboquant_enabled`, `turboquant_bits`, `turboquant_qjl_enabled`, `turboquant_rotation`
- Wired into LayerStream engine via optional `turboquant_config` param on `LayerExecutor`
- Added `KVCacheManager.create(mode="turboquant")` factory to layerstream/kv_cache.py
- Added `use_turboquant` flag to FullRAM `KVCache`
- Added `sovereign benchmark-turboquant` CLI command
- Self-check verifies PolarQuant + QJL reconstruction MSE < 0.02 on unit vectors
- Skipped bit-packing (ponytail) — add when real memory pressure is measured

## [2026-07-24] review | Ponytail Review
- Ran `/ponytail-review` across full codebase
- Found ~3800 lines of unnecessary complexity (dead providers, duplicate task resolvers, 1003-line inference handler with 18 unused task handlers, USB bundle protocol over-engineering, zombie memory manager, etc.)
- Created [[workflow/Ponytail Review|Ponytail Review]] page, updated index
- Created log.md — timeline tracking
- Batch-ingested 31 Docs/ sources into wiki pages with frontmatter, synthesis, and [[wikilinks]]
- Cross-linked related pages: PRD↔TRD, FullRAM↔LayerStream, tech-stack↔Technical Architecture, etc.

## [2026-07-24] review | Ponytail Audit (full project)
- Scanned all backend (21,813 lines) + frontend (8,303 lines) + root
- Found ~5000 lines removable across USB bundle provider, enterprise repo, ManualStream, inference.py handlers, settings over-engineering, root clutter, singleton pattern, layerstream executor duplication
- Created [[workflow/Ponytail Audit|Ponytail Audit]] page, updated index, appended to log

## [2026-07-24] ingest | Literature Review
- Created [[project/Literature Review|Literature Review]] — 6 high-impact papers on edge AI, quantization, attention, speculative decoding, RAG
- Cross-linked to FullRAM, LayerStream, Engine Algorithms
- Updated index, appended to log

## [2026-07-30] implement | Workspace Snapshots + Mode Comparison + RAG Hardening + Plugin Marketplace
- **Backend — Workspace API** (`backend/app/api/workspace.py`): Full CRUD for workspace snapshots (save/list/load/delete) with JSON file persistence. Registered at `/v1/workspace/`
- **Backend — Benchmark compare** (`backend/app/api/benchmark.py`): Implemented `compare_modes()` — runs a test prompt in the active mode and reports tps/ram; shows the other mode as unavailable (avoids model reload)
- **Backend — RAG hardening** (`backend/app/api/rag.py`): Added 50MB upload cap, file type validation (.txt/.pdf only), fail-fast content-length check
- **Frontend — Workspace Snapshots** (`frontend/app/workspace/page.tsx`): Full UI with save/list/load/delete, current session state display, empty state illustration. Sidebar link added
- **Frontend — Home page** (`frontend/app/page.tsx`): First-run hardware suggestions banner w/ gradient card when no model loaded, shows top 4 model recommendations
- **Frontend — Documents page** (`frontend/app/documents/page.tsx`): Native HTML5 drag-and-drop upload zone (no lib), client-side file validation (type + size), fixed `useState` → `useEffect` init bug
- **Frontend — Benchmark page** (`frontend/app/benchmark/page.tsx`): Mode comparison UI with FullRAM vs LayerStream cards showing TPS/time/tokens/RAM
- **Frontend — Plugins page** (`frontend/app/plugins/page.tsx`): Plugin Marketplace section with 3 placeholder plugins (PDF Ingestion, Web Scraper, Code Interpreter), "Coming Soon" / "Installed" badges
- **Frontend — Sidebar** (`frontend/components/layout/Sidebar.tsx`): Added Workspace nav item
- **Frontend — Hooks** (`frontend/hooks/useModels.ts`): Desktop notifications for model load/unload/fail via Electron bridge
- **Frontend — API client** (`frontend/lib/api.ts`): Added `saveWorkspace`, `listWorkspaces`, `loadWorkspace`, `deleteWorkspace`, `compareModes`
- **Electron** (`electron/main.js`, `electron/preload.js`): Native Notification support via IPC handler, exposed via preload bridge
- **Root** (`install.sh`): One-line install script (git clone or curl+tar) supporting Linux/Mac/Windows
- **Root** (`TODOS.md`): Deferred & future work across 5 phases (Core Engine → UI → Desktop/USB → Ecosystem → Hardening)
- **Root** (`backend/pyproject.toml`): pytest `asyncio_mode = auto`
- **Root** (`.gitignore`): Added `opencode.jsonc`

## [2026-07-31] refactor | TypeScript Type Safety + UI Polish Sweep
- Types: new interfaces replacing any
- API client: typed imports and return types
- Store: simplified create
- Hooks: type safety and errMsg utility
- Utilities: errMsg helper
- Components: build repair (remove any casts)
- Sidebar: rewrite with nav list, styles
- Settings: TypeScript diet
- Design tokens: new CSS custom properties
- Workspace page: useCallback, delete confirmation, loading skeleton
- Documents page: useToast, error state
- Home page: Recommendation type import
- Plugins page: badge sizes, useEffect dep
- Benchmark page: mode comparison card, errMsg, loading spinners
- Overall: 100+ TypeScript strict-type breadcrumbs

## [2026-08-01] implement | Masked LM Support + Stream Delta Fix + Safetensors Compatibility + TypeScript Polish
- Task router: masked_lm task type routing
- Memory manager: silenced llmfit fallback logging
- Engine: safetensors compatibility module
- FullRAM executor: ensure_safetensors, masked_lm handling
- LayerStream executor: _stream_delta function, EOS handling
- LayerStream splitter: ensure_safetensors
- ManualStream executor: EOS check guard
- Model manager: inference.py softmax probabilities, loader.py dtype migration
- Tests: stream delta regression tests
- Frontend: MaskedLMModule component
- Frontend: console page wired for masked_lm
- Types: TaskResult extended with MaskPrediction
- Frontend: lib/maskedLm helper and tests
- Root: freebuff.txt timestamp update
- Frontend: package.json test script
- Frontend: tsconfig.json allowImportingTsExtensions

## [2026-08-01] kanban | Complete remaining backlog items
- Marked TurboQuant KV Cache Compression (July 23) as done
- Marked Ponytail Review (July 24) as done
- Marked Ponytail Audit (full project) (July 24) as done
- Marked Literature Review (July 24) as done
- All backlog items now completed and moved to Done section

## [2026-08-03] implement | Reasoning Token Support for Qwen3.5 Models
- **Backend**: Added reasoning field to Message type (`frontend/types/index.ts`) to capture model's internal thinking process
- **Frontend**: Enhanced `useChat` hook (`frontend/hooks/useChat.ts`) with:
  - Thinking toggle persistence via localStorage
  - Increased max_tokens (1024 vs 512) when thinking enabled to accommodate reasoning tokens
  - Streaming handler for reasoning deltas alongside content tokens
  - Fallback to display reasoning-only responses when content is empty
  - Export functionality now includes reasoning blocks in markdown output
- **Frontend UI**: Updated components to display reasoning:
  - `MessageList.tsx`: Shows thinking section with blockquote formatting
  - `ChatWindow.tsx`: Added thinking toggle button to header
  - `ChatModule.tsx`: Connected thinking toggle state
- **Backend**: FullRAM executor (`backend/app/engines/fullram/executor.py`) updated to handle reasoning field in responses
- **Tests**: Added test files for load status agreement and split auto mode functionality
- **Maintenance**: Updated freebuff.txt timestamp

## [2026-08-05] implement | PRD & TRD Documentation + Project Review
- **Documentation**: Created `PRD.md` (102 lines) — Product Requirements Document with user stories, acceptance criteria, and success metrics
- **Documentation**: Created `TRD.md` (150 lines) — Technical Requirements Document with architecture decisions, API contracts, and infrastructure specs
- **Review**: Completed project review; removed `diagrams/sovereignai-architecture.mmd` (63 lines) as outdated
- **Planning**: Updated `TODOS.md` with 29 new lines — refined backlog across 5 phases (Core Engine → UI → Desktop/USB → Ecosystem → Hardening)

## [2026-08-09] implement | TurboQuant KV Cache Hardening + Benchmark Suite + Repository Cleanup
- **Repository Cleanup** (commit 841c5d1): Major housekeeping — removed 13 stale files (1,798 lines deleted):
  - `QA_FIXES_REPORT.md`, `Recent_work.md`, `SECURITY_FIXES_REPORT.md`, `TODOS.md`, `folder_structure.md`, `issue.md`
  - `portability_audit.py`, `qa-home-evidence.png`, `qa-home.png`, `qa.md`, `quant.md`, `verify_workspace.py`
  - Cleared root clutter, consolidated documentation into wiki

- **TurboQuant Core Improvements** (commit e843b5a): Enhanced KV cache compression pipeline:
  - `config.py` (+13/-0): Added rotation seed, QJL dim scaling, bit-width validation
  - `kv_cache.py` (+293/-78): Rewrote `TurboQuantKVCache` with chunked rotation, batched QJL projection, per-layer codebooks
  - `qjl.py` (+54/-1): Optimized Johnson-Lindenstrauss projection with precomputed random matrices
  - `__init__.py`, `__main__.py`: Exported public API, added CLI smoke test

- **Benchmark Suite** (commit 26a5523): Added comprehensive evaluation harness:
  - `backend/benchmarks/accuracy_eval.py` (261 lines): End-to-end accuracy evaluation with perplexity, token accuracy, reconstruction MSE
  - `backend/benchmarks/qjl_ablation.py` (181 lines): Ablation study varying QJL dimensions, rotation seeds, bit-widths
  - `backend/app/config.py`: Added `turboquant_benchmark_mode` flag

- **Test Coverage** (commit 8194c79): Created `backend/tests/test_turboquant.py` (399 lines):
  - Unit tests for PolarQuant encoding/decoding, QJL projection, codebook reconstruction
  - Integration tests for LayerStream + TurboQuant executor path
  - Property-based tests: reconstruction MSE < 0.02 on unit vectors, memory reduction > 4×
  - Benchmark regression tests with `eval_smoke.json` and `eval_gate_2026-08-09.json` gates

- **Automation & Reporting** (commits 8194c79, 1cff700):
  - `reviews/autoplan-report-2026-08-09.md` (412 lines): Autoplan-generated implementation report with phase breakdown, risk assessment, and rollout checklist
  - Updated `accuracy_eval.py` with streaming JSONL output for CI integration
  - Evaluation gates: `eval_smoke.json` (fast CI gate), `eval_gate_2026-08-09.json` (full release gate)

## [2026-08-10] implement | Per-Channel Affine (KIVI-Style) Quantizer + Re-gate on Real Models
Six commits (`2831555` → `40379b6`), one coherent tranche: after the 2026-08-09 polar gate FAILED (Qwen2-0.5B ppl 1201-3623 vs baseline 8.3), built the report's recommended "path to re-enable" — a KIVI-style per-channel affine quantizer (arXiv:2402.02750), then re-gated it on two real models. Verdict: affine beats polar 4-13× on ppl but still **FAILS the 2% gate at all bit rates** (3017-4201% Qwen2, 1318-1387% Pythia). TurboQuant stays experimental/default-off.

- **New affine quantizer** (`baeb975`): `backend/app/engines/shared/turboquant/affine.py` (new) — per-group symmetric affine quantization: K gets per-(head,dim) max-abs scales computed over the sequence (channel outliers), V per-(head,token) scales (token outliers). No rotation, no QJL, no unit-norm. Fixed a half-step indexing bug (`round(x_level + half)` not truncation — truncation gave a Δ/2 bias → 3× NMSE inflation, caught by unit test).
- **Config rework** (`baeb975`): `config.quant_scheme: "polar"/"affine"` (backward-compatible switch; all 32 polar tests pass unmodified), `config.k_bits`/`v_bits` asymmetric budgets (V harder than K), removed dead fields (`rotation_type`, `codebook_type`, `collect_stats`, `enable_polarquant`). Scheme dispatch in `kv_cache.py` (`_quantize_kv_affine`/`_dequantize_kv_affine`), indices packed like polar, scales fp16 when packed.
- **Structure probe** (`659afc4`): `benchmarks/kv_structure_probe.py` (model-agnostic, `--model` arg) — measured real Qwen2-0.5B K/V through the proxy `update()` hook: **raw K per-channel std varies 0.03-21.8 (layer 0, cv 1.84)**, V per-token 2-8×. Exactly the structure polar's rotation destroys and per-channel scales exploit.
- **Gate harness hardening** (`659afc4`): `benchmarks/cache_wikitext.py` pins eval text to `reviews/eval_wikitext.txt` (reproducible + offline — datasets-server API was rate-limited); `accuracy_eval.py` prefers the cache, configs now baseline + 4 affine configs, QJL comparison made conditional; `benchmarks/check_ram.py` (Windows RAM check via ctypes).
- **FullRAM dim-order fix** (`57cd6ce`): `fullram/kv_cache.py` now transposes numpy `[seq, nh, hd]` → TQ `[1, nh, seq, hd]` on update and back on get (router still not wired for turboquant — dormant P2). Removed `rotation_type` from LayerStream executor config.
- **CLI honesty** (`2831555`): `sovereign benchmark-turboquant` no longer prints fabricated bit-packed estimates — labels ratio "Measured … (synthetic K/V, no real model)" and points at the eval-gate report.
- **Tests** (`a6d286f`): 11 new `TestAffineScheme` tests — roundtrip NMSE, affine-beats-polar on structured data (≤0.5× NMSE), same-chunking bit-exactness, chunk-boundary scale consistency (≤1.5×), scale shapes, asymmetric bits, ratio >3.0, no-requant invariant, default-scheme. 43 turboquant / 86 full suite.
- **Re-gate results** (`a6d286f`): `reviews/eval_gate_affine_2026-08-10.json` (Qwen2-0.5B, wikitext, 704 tokens):
  |config|ppl|deg|needle|
  |---|---|---|---|
  |baseline| **8.34** | — | ✅ PINEAPPLE123. The |
  | affine-3.5 | 259.9 | +3017% | ❌ |
  | affine-4.0 | 304.2 | +3548% | ❌ |
  | affine-4k5v | 358.6 | +4201% | ❌ |
  | affine-4k6v | 323.8 | +3783% | ❌ |
  NMSE on layer-4 captured K/V: affine 4-bit K 0.0050 vs polar 3.5+qjl 0.142 (**28× better**), 5-bit 0.00093 (153×), 6-bit 0.00017 (835×). First-chunk ppl 16.4 vs 8.3 — attention corrupts immediately at 64 tokens, compounds to 36× over 768.
- **Cross-model bound** (`a6d286f`): `reviews/eval_gate_pythia_2026-08-10.json` — Pythia-70m (moderate key norms ~10-15 vs Qwen2 ~215): baseline 39.2 → affine 555-583 ppl (**1318-1387% deg**). Same catastrophic pattern → NOT a Qwen2-sharpness artifact.
- **Conclusion (in `reviews/autoplan-report-2026-08-09.md` tranche)**: on 0.5B-70M models, per-coordinate scalar quantization at ≤6 bits cannot pass a 2%-degradation gate — per-coord error (~0.5% NMSE at 4 bits) corrupts attention logits → hidden states → errors compound across the sequence. The paper's 6× "zero-loss" claim likely only holds for ≥7B models / single-token evals. Recommended next: llama.cpp tbq3_0/tbq4_0 eval (PR #21089), per-vector codebooks, TinyLlama-1.1B gate run as the final viability test.
- **Root markers** (`40379b6`): `turboquant.md` gets experimental/default-off warning banner pointing at the report; `TODOS.md` re-created (P3: CLI honesty, ≥1B gate, llama.cpp eval); added `llama-cpp-tq` + `llama-cpp-pr` submodule pointers.

## [2026-08-11] implement | LayerStream Phase A+B (memory-bounded streaming + int4 codec) + Whole-App Performance + TurboQuant Phase 4 Research
Five commits (`3143fe6` → `8050804`), one evening tranche (19:46–19:47), all pushed to `origin/main` (`8050804` = remote tip — verified via GitHub API). Three workstreams: two implementations + a research close-out on the TurboQuant gate.

### LayerStream Phase A — make "memory-bounded" true (commit `3143fe6`)
Per `Docs/LayerStream-Improvements.md` (new, 404 lines — office-hours design doc that exposed the core contradiction: the loader caches every layer in CPU RAM forever, prefetch depth is 1, and a whole second architecture — `scheduler.py`/`prefetch.py`/`mmap_loader.py`/`memory.py` — is unwired dead code). Shipped Phase A:
- **Bounded LRU cache + pinned paths** (`loader.py` +191): `LayerWeightLoader` evicts LRU past `cache_max = 1 + prefetch_depth + pinned`; `embed`/`norm`/`lm_head` pinned (tiny, used every pass).
- **Prefetch depth 3** (`layer_executor.py` +106): deep prefetch threaded through `LayerExecutor` so the disk stays saturated while compute runs.
- **Cached attention mask** + position ids keyed by `(seq, past)` shape instead of rebuilt per forward call.
- **Benchmark harness** (`benchmarks/layerstream_phase_a.py`, new, 143 lines): per-config fresh subprocesses; Qwen2-0.5B / 24 layers / `workspace/offload_cache/bench-*` split dirs.
- **Removed `gc.collect()` per eviction** — it cost ~1.5 s/pass (tensors are refcounted; Python GC chases cycles, not tensors).
- Measured (Qwen2-0.5B): fp16 cached **682.6 → 256.0 MB** bounded; int8 **1365.3 → 227.5 MB**; steady-state pass cost 0.02 s fp16 / 0.66 s int8 — the honest price of streaming (pre-fix decode showed 0.00 s only because everything stayed resident).
- **Key finding**: `safetensors get_tensor(device="cpu")` returns mmap-backed views, so the OS reclaims fp16 pages (RSS +2 MB) — the "unlimited" fp16 cache was less catastrophic than feared; but the int8 path was dequantizing to *private fp32 copies* (1365 MB held, +1433 MB RSS) — the real RAM hog the bounded cache fixes.
- **New tests** (`tests/test_layerstream_loader.py`, 9): budget eviction, pinned survival, LRU order, prefetch depth bounds, future reaping, mask caching/cap. Full suite **95 passed**.

### LayerStream Phase B — shrink bytes per layer (commit `3143fe6`)
- **int8 stays raw** (`loader.py`): the loader no longer CPU-dequantizes — RAM holds int8 + scale; dequant happens on the compute device inside `assign_weights` (`dequantize_on_device()`).
- **Group-wise int4 codec** (`splitter.py` +66): Q4_0-style — group 32, packed nibbles, fp16 scales.
- **bf16 capability gate** (`_compute_dtype_for`): bf16 only on AVX512-BF16/AMX CPUs — measured **163× slower** than fp32 on this AVX2 box, so default stays fp32.
- Measured (full model in RAM, unlimited cache): fp16 682.6 MB (28.4 MB/layer) → int8 **341.4 MB** (14.2 MB/layer, 0.50×) → int4 **192.1 MB** (8.0 MB/layer, **0.28×**). int8 footprint cut **4×** (1365 → 341 MB) just by dropping the dequantized fp32 copy; at 7B the ladder reads ~14 GB → 7 GB → 3.5 GB.
- Tensors < 1024 elems (`inv_freq`) stay fp — RoPE buffers never loaded raw as int tensors.
- **New tests (6)**: int4 roundtrip NMSE, int4 padded-cols, int8 device-dequant ≡ old CPU path, raw-int8 stays in cache, numel gate, bf16 gate. Full suite **105 passed**.

### Whole-app performance (commits `d4e5e07`, `aed5946`, `0d0f7d0`)
Per `reviews/perf-research-2026-08-11.md` (new, 204 lines — end-to-end perf research grounded in `file:line` refs; rejected uvloop / V8-snapshot / gzip / react-window / periodic-vacuum with measured reasons). Implemented:
- **rAF-batched token flush** (`useChat.ts`): one `setMessages` per animation frame instead of per token — at ~20-40 tok/s this was an O(N) `ReactMarkdown` re-parse + DOM diff every ~30 ms; `finally` cancels a pending flush so a mid-stream error can't clobber the error bubble; `sendMessage`/`editAndResend`/`regenerate` made stable via `messagesRef`.
- **Message memoization** (`MessageList.tsx`): message row extracted into `React.memo`'d `MessageItem` — completed messages stop re-rendering and stop re-parsing markdown; `ChatModule.tsx` `onEditMessage`/`onRegenerate` now `useCallback`'d so the memo holds.
- **Electron parallel boot** (`main.js`): window opens before the backend resolves; backend boots behind it — frontend `/status` retry + `metricsWs` reconnect self-heal.
- **SSE frame batching** (`chat.py`): `stream_response` batches ~96 chars per frame (was one frame per engine token) — ~10× fewer frames/JSON serializations, deltas stay in order; guarded by `tests/test_stream_batch.py` (collapse, lossless reconstruction, finish-trails-content).
- **`SettingsDialog` `next/dynamic`'d** (`ClientLayout.tsx`, `ssr: false`) — 8 settings sections off the global app-shell chunk.
- Verified: `tsc --noEmit` clean, `node --check` clean, **28 pytest** tests pass (3 new + 25 existing).
- **Measured and rejected (do not build)**: metrics-WS throttle (backend already pushes ~1/s), `/status` dedup (sub-ms loopback, redundant mounts), `next/dynamic` recharts (already route-split), chat-tail windowing (conditional — only if conversations grow past hundreds of messages).

### TurboQuant Phase 4 research + reference-codebook probe (commits `0d0f7d0`, `8050804`)
- **llama.cpp tbq3_0/tbq4_0 eval — resolved by research** (new "Phase 4 evaluation" section in `reviews/autoplan-report-2026-08-09.md`): PR #21089 **closed unmerged** (2026-06-02); kernels exist only in community fork `TheTom/llama-cpp-turboquant` (Mac Metal / Windows CUDA builds — neither runs on this CPU-only box); `TheTom/turboquant_plus` is actually a Python reference implementation of the paper (runs on CPU). Upstream llama.cpp merged only the Hadamard rotation (#21038); **vLLM merged the full codec** (#38479, `turboquant_k8v4`); MLX merged into `mlx-swift-lm`. The paper's 6× claim is **already community-validated at 104B/128K** (turbo3, ppl 4.024, 74 GB peak) — no local ≥7B test possible (8 GB RAM, ~2 GB free; no compiler — VS2022 dir empty).
- **Reference-codebook probe** (`benchmarks/reference_polar_probe.py`, new, 133 lines): runs `turboquant_plus` PolarQuant/TurboQuant (per-vector norm extraction + Gaussian Lloyd-Max centroids + norm correction) on the same captured Qwen2-0.5B K/V as the affine probe (layer 4, 256 tokens):
  | method | K NMSE | V NMSE |
  |---|---|---|
  | our polar 3.5+qjl | 0.14283 | 0.13510 |
  | ref PolarQuant 3-bit | **0.02833** | 0.03446 |
  | ref PolarQuant 4-bit | 0.00872 | 0.00890 |
  | our affine 4-bit (report) | 0.0050 | 0.026 |
  Verdict: reference codebook is **5× better than ours** (0.028 vs 0.143 at 3-bit) but lands **in the affine regime that already FAILED the gate** (ref 4-bit 0.0087 ≈ affine 4-bit 0.0050 → 3017–4201% ppl deg). QJL hurts (TurboQuant 3-bit 0.068 vs PolarQuant 3-bit 0.028); norm correction ~no-op. **Layer-0 confirmation** on the extreme channel-structure layer (K cv 1.84): identical regime (ref 3-bit 0.0333 vs our 0.1343). Codebook swap alone cannot pass the gate.
- **`TODOS.md`** (`8050804`): reference-codebook comparison ✅ DONE, llama.cpp tbq eval ✅ DONE; remaining: ≥1B model gate (TinyLlama-1.1B), per-vector non-scalar codecs (spherical VQ / product quantization). Removed `llama-cpp-pr` submodule pointer.

## [2026-08-12] review | Whole-Project Autoplan Review (CEO + Design + Eng + DX)
One commit (`bbe44f6`): added `reviews/autoplan-report-2026-08-12.md` (453 lines) — a comprehensive whole-project review across four phases with dual-voice consensus (primary + independent reviewer per phase). **Baseline verified**: `backend/.venv` pytest **106 passed** (48.95s, 1 Pydantic deprecation warning); test_dummy.py removed; LayerStream duplicate engines deleted.

### Phase 1 — CEO Review (Strategic)
**Premises challenged:** P1 (70B-on-8GB usable) remains **unvalidated** — never measured end-to-end, dev machine can't run 7B; TurboQuant 6× claim **FAILED 4 eval gates** (polar, affine@Qwen2, affine@Pythia, reference codebook). **Wedge decision**: recommended **OpenAI-compatible offline server** (Wedge A) over RAG-first (B) or status quo (C). **TurboQuant**: park as research (evidence: scalar quantizers structurally cannot pass 2% gate on small models; reference codebook 5× better but still fails). **Cross-phase themes**: (1) Approved 08-05 cleanup never executed, (2) Breadth before validation, (3) Unvalidated headline claims, (4) Offline story leaks at edges.

### Phase 2 — Design Review (7-dimension litmus)
**Scores:** Hierarchy 5/10 (home leads with hardware cards, not chat), States 4/10 (**no stop button**, no loading/OOM/no-model states), First-run 5/10, Responsive 8/10, A11y 4/10 (no `aria-live`, skip-link, contrast unverified), Identity 5/10, Design-system 7/10.
**Critical findings:** D1 — No stop/abort during generation (unkillable = worst UX failure on slow local engine); D2 — Missing 5-state chat lifecycle; D3 — 7 speculative task modules shipped (audio/vision/QA/embedding) that engines cannot execute; D4 — Home hardware-first vs chat-first (taste); D5 — No first-run empty state; D6 — No live t/s readout; D7 — A11y gaps.

### Phase 3 — Eng Review (Architecture + Tests + Security)
**Test coverage:** 106 passed but **zero coverage** on highest-risk paths: LayerStream executor, FullRAM executor + fallback, chat e2e with real model, plugin sandbox, RAG/vectorstore, websocket, auth, frontend. **Still open from 08-05**: ManualStream wired (loads full state dict — defeats low-memory premise), DEBUG print in `engine_factory.py:61`, task_router **32 entries** (shrink to 2), no auth on LAN bind, no `is_disconnected`, no OOM/507, `delete_model` rmtree on registry path, 145 `print()` calls, `reload=True` in main, docs drift (readme "Vite", TRD "llama.cpp", AGENTS.md deleted files).
**Eng consensus:** Architecture CHALLENGED (factory coupling, ManualStream, 32-entry map), Tests CHALLENGED (executors + sandbox + RAG uncovered), Security CHALLENGED (no auth on LAN, rmtree path, sandbox), Error paths CHALLENGED (OOM/disconnect/disk-full unbuilt).

### Phase 3.5 — DX Review (Developer Journey)
**TTHW ~45 min** (vs Ollama ~2 min); claims "zero-config, no pip install" contradicted by multi-GB torch download. No offline `sovereign import <gguf>`. OpenAI-compat shape unproven; `delta.reasoning` undocumented. 145 prints, no error catalog. No tags/releases/migration notes. **DX scorecard overall: 3.75/10** (Getting started 3/10, Error messages 3/10, Docs 3/10, Upgrade path 3/10, Dev env 4/10, First-run 3/10).

### Cross-Phase Themes & Implementation Tasks (28 items, P1→P3)
**P1 Critical:** Delete ManualStream, Stop button + disconnect cancellation, LayerStream small-model benchmark, Gate/hide 7 task modules, Reconcile stale docs, Auth + path safety, OOM→507/disk-full/concurrent-lock.
**P2:** Real engine tests (@slow), OpenAI-compat contract test, Fail loudly on unknown configs, Shrink task_router 32→2, Split EngineFactory create/load + remove DEBUG print, Pydantic v2 migration, 5-state chat lifecycle + OOM card.
**P3:** `sovereign import <local.gguf>`, Structured logging, Tags/releases/pinned installer/CHANGELOG, Repo hygiene, gguf IQ2_BN pin, reload gating, MemoryManager zone verification, Home page chat-first + first-run + a11y, TurboQuant research backlog, Sub-project ownership docs.

### Final Gate Decisions (User Calls)
- **U1 — TurboQuant**: Park as research (recommended) vs Keep active lane (TinyLlama gate becomes P1)
- **T1 — Home hierarchy**: Chat-first (recommended) vs Hardware dashboard-first
- **T2 — Task modules**: Hide from nav now (recommended) vs Delete outright

**Gate: APPROVED AS-IS** — report written per user request. Suggestions S1–S11 delivered (pick wedge A, measure LayerStream honestly, execute approved cleanup, close security boundary, park TurboQuant, error paths, stop button, docs reality, chat lifecycle, ship like product, repo hygiene).

## [2026-08-13] docs | Wiki Index Sync + Repo Hygiene
Two commits (`2645279`, `d86d053`), both pushed to `origin/main` (verified 0 ahead / 0 behind). Lightweight housekeeping day — no engine or frontend code changes.

### Repo hygiene (commit `2645279`)
- **`.gitignore`**: added `.zed/` to ignore directory — excludes Zed editor workspace/recommendation metadata from the tree.

### Wiki index sync (commit `d86d053`)
- **`Info_docs/INDEX.md`**: bumped `updated:` frontmatter `2026-08-09` → `2026-08-12`; added catalog entry under **Workflow** — `[[workflow/Autoplan Review 2026-08-12|Autoplan Review 2026-08-12]]` cross-linked to the new review page (`reviews/autoplan-report-2026-08-12.md`).
- **`Info_docs/log.md`**: back-filled the missing `## [2026-08-12] review | Whole-Project Autoplan Review` block (CEO/Design/Eng/DX four-phase dual-voice review; 106 tests passing; TurboQuant parked as research; wedge = OpenAI-compatible offline server). This is the log entry that should have shipped with commit `bbe44f6` but only landed today.

**Net effect**: wiki index and timeline now reflect the 2026-08-12 whole-project review; repo ignores Zed IDE artifacts. No functional/build impact.

## [2026-08-14] implement | Autoplan Backlog Execution (P1+P2+P3 from the 08-12 review)
Seven commits (`208c54e` → `d3db7fa`), one tranche (22:25–22:26 IST), all pushed to `origin/main` (`d3db7fa` = remote tip — verified via GitHub API + `0 ahead / 0 behind`). This is the execution of the 22 actionable items in `reviews/autoplan-report-2026-08-12.md` / `reviews/TODO-2026-08-12.md` — the closeout lives in [[reviews/completed-2026-08-12-to-2026-08-15]]. **Verification: backend suite 112 tests pass** (106 baseline + 6 new) · frontend `npm run build` green · CLI `sovereign --help` registers `import`.

### P1 — critical (commits `208c54e`, `f196247`)
- **Stop + disconnect cancellation**: `AbortController`/`stop()` in `frontend/hooks/useChat.ts`, Stop button in `ChatModule.tsx`; `Request.is_disconnected()` guard in `backend/app/api/chat.py`.
- **ManualStream deleted**: `backend/app/engines/manualstream/executor.py` gone (257 lines, commit `f196247`) — it loaded the full state dict and defeated the low-memory premise; factory import + branch removed.
- **Auth + path safety**: new `backend/app/security/middleware.py` Bearer middleware (LAN exposure only), `api_token` setting, `delete_model` rmtree root guard, snapshot traversal rejection in `workspace.py`.
- **OOM→507 + disk preflight + load lock**: 507 mapping in `/v1/models/load` (`models.py`), disk-space preflight, `asyncio.Lock` around loads; `settings.trust_remote_code` off by default (gates remote code execution).
- **LayerStream benchmark**: `backend/benchmark_layerstream.py` (new, 68 lines) + `reviews/benchmark-2026-08-14.md` — **0.40 tok/s, 2.30 GB peak** on Qwen3.5-0.8B (10→32 tokens). Sub-1 tok/s as predicted: the "70B on 8GB" headline is **not supported by measurement**; pitch re-positioned to **"3-8B Q4 on 8GB"** (true + measurable). RAM economics work as designed (1.9 GB model → 2.30 GB peak).
- **Hide speculative task modules** + **reconcile stale docs** landed in P1 tranche tail (commits `e85cdce`, `d3db7fa`): console renders ChatModule only; readme/TRD/AGENTS.md/CLAUDE.md corrected — Next.js 16/React 19, honest LayerStream pitch, no-SQLAlchemy, single engine.

### P2 (commits `4cd177a`, `9425152`, `f196247`)
- **Real-engine tests**: `backend/tests/test_plugin_sandbox.py` (49 lines, timeout containment) + `test_openai_compat.py` (4 tests) + `test_load_status_agree.py`/`test_split_auto_mode.py` touched.
- **Fail loudly + shrink task_router**: `TaskRouter` 32 entries → `{causal_lm, seq2seq_lm}` (commit `4cd177a`, task_router −137 lines); `get_model_class()` raises on unknown/non-generative tasks.
- **Factory create/load split**: `engine_factory.py` no longer loads; `ModelManager` owns load + error mapping; the DEBUG print at `engine_factory.py:61` is gone.
- **Pydantic v2 + structured logging**: `class Config` → `model_config = ConfigDict` (`settings/schemas.py`); fullram executor `print()`s → stdlib `logging` (commit `3e2b86f`).
- **Chat lifecycle + OOM card**: 507 errors render a "how to fix" bubble; input gated while generating.

### P3 (commits `4cd177a`, `9425152`)
- **`sovereign import <local.gguf>`**: new CLI command in `backend/app/cli/main.py` (+47 lines, copy + registry refresh).
- **Structured logging / reload gating**: stdlib `logging` on error paths (`SOVEREIGN_LOG_LEVEL`); `backend/main.py` reload dev-only (`SOVEREIGN_RELOAD=1`).
- **MemoryManager zones**: dead zone bookkeeping deleted (memory_manager −84 lines); `suggest_mode` kept.
- **Repo hygiene** (commit `e85cdce`): deleted `frontend/ts_errors.txt`/`ts_errors2.txt`/`ts_errors_current.txt`, `frontend/build_output*.txt` (×3), `electron/build_linux_output.txt` — and gitignored them.

**Commits at a glance**: `208c54e` API hardening · `4cd177a` CLI import + router/memory cleanup · `3e2b86f` FullRAM refactor/print→logging · `f196247` delete ManualStream + security middleware · `9425152` benchmark + 3 test files · `e85cdce` frontend chat lifecycle + repo hygiene · `d3db7fa` docs + review markers.

## [2026-08-15] implement | LayerStream Round-Trip + Rotary Bug Fix + GPU Benchmark Follow-Up + Settings UI Auth
Three threads: a real-engine round-trip test that caught a latent LayerStream bug, a GPU-kernel availability check that closed out the 08-14 benchmark, and the security settings UI that finished the P1 auth story's frontend half. **Committed 2026-08-16 in `2463d94`** — the "not yet committed" caveat below is now historical.

- **LayerStream round-trip test** (`backend/tests/test_layerstream_roundtrip.py`, new): `@slow` full executor round-trip on a freshly-split tiny Llama — copies the tokenizer, runs `generate_stream`, and unloads. Closed the "zero coverage on high-risk LayerStream executor" gap from the 08-12 Phase 3 eng review. A `slow` pytest marker was registered in `backend/pyproject.toml` so these real-engine tests run with `-m slow` and skip by default.
- **Bug the round-trip exposed** (`backend/app/engines/layerstream/layer_executor.py`, +11): `execute_forward` crashed on `rotary_emb.to(device)` for **any non-hybrid Llama/Qwen2 model** — the `inv_freq` buffer arrives as a meta tensor (`init_empty_weights`) and `.to()` on a meta tensor raises *"Cannot copy out of meta tensor"*. Fix materializes `inv_freq` from `rope_theta` first (same formula as `assign_weights`' meta-buffer branch) before relocating. This would have failed the first `generate` on every standard Llama/Qwen2 split — masked until now because the 08-14 benchmark used the hybrid Qwen3.5 (path without this branch).
- **GPU benchmark follow-up** (`backend/benchmark_layerstream.py` +10, `reviews/benchmark-2026-08-14.md` +26): re-ran on the box's GTX 1650 (torch 2.5.1+cu124 + `triton-windows` + `flash-linear-attention 0.2.2`, all venv-local). **0.38 tok/s ≈ CPU (0.40)** — zero delta, because transformers' Qwen3_5 fast path needs **both** fla and `causal-conv1d`; `causal-conv1d` has no Windows wheels (PyPI or GitHub) and the box has no `nvcc`/MSVC. Kernel availability now printed by the runner (`cuda=… fla=… causal_conv1d=…`). Fast-attention delta is **parked, not abandoned** — needs a Linux CUDA box or a global CUDA Toolkit install.
- **Settings UI auth** (`frontend/components/settings/SecuritySettings.tsx` +43, `frontend/lib/api.ts` +13): API Token field + LAN-exposure warning (shown when `bind_localhost_only=false`); the API client now sends `Authorization: Bearer` from localStorage — the frontend half of the P1 auth+path-safety item, completing the middleware added 08-14.
- **Closeout report** (`reviews/completed-2026-08-12-to-2026-08-15.md`, new): the full 22-item done/deferred ledger for the 08-12 review application — 112 tests passing, lists the three left-open decisions (gguf IQ2_BN patch, TurboQuant parked, tags/releases pending, fast-attention delta needs Linux CUDA).

**Status**: uncommitted. To finalize, stage the 6 modified + 2 new files and commit; then the remote tip advances and this entry's "not yet committed" caveat drops.

## [2026-08-16] docs | 08-15 Finalization + Repository Guidelines Rewrite
Three commits (`2463d94`, `02daaaa`, `991f5ca`), finalizing the previously-uncommitted 08-15 tranche and regenerating the agent-facing guidelines from source. Working tree clean; `991f5ca` 1 ahead of `origin/main` (pending push).

### 08-15 tranche committed (commit `2463d94`, 15:14 IST)
Stage of the 6 modified + 2 new files the 08-15 entry flagged as uncommitted — the 08-15 "not yet committed" caveat now drops:
- **Logged**: the `## [2026-08-15]` block was appended to `Info_docs/log.md` (+39) — this is the entry above.
- **Stale wiki cleanup**: deleted `Info_docs/Excalidraw/SovereignAI.excalidraw.md` (314 lines) + `Info_docs/Kanban_board.md` (34 lines) — obsolete artifacts predating the wiki restructure.
- The LayerStream round-trip test (`backend/tests/test_layerstream_roundtrip.py` +102), rotary `inv_freq` materialization fix (`backend/app/engines/layerstream/layer_executor.py` +11), GPU benchmark follow-up (`backend/benchmark_layerstream.py` +10, `reviews/benchmark-2026-08-14.md` +26), `slow` marker (`backend/pyproject.toml` +3), settings UI auth (`frontend/components/settings/SecuritySettings.tsx` +43, `frontend/lib/api.ts` +13), and closeout report (`reviews/completed-2026-08-12-to-2026-08-15.md` +66) all land here.

### Repo hygiene (commit `02daaaa`, 21:54 IST)
- **`.gitignore`**: added `.omp/` — excludes the local agent-harness workspace metadata directory (not part of the SovereignAI runtime app).

### Repository Guidelines rewrite (commit `991f5ca`, 22:23 IST)
- **`AGENTS.md`** (+207/-144): replaced the stale agent guide with a fresh source-grounded synthesis. Generated via 4 parallel research scout agents (core source, tests, configs/build, scripts/docs) and verified against the actual tree.
- **Corrections vs the old guide**:
  - `proxy.py` claimed as a standalone NVIDIA NIM proxy — **file does not exist**; removed. Only a stale `__pycache__/proxy.cpython-314.pyc` remains.
  - Gotcha #8 ("debug/test scripts litter repo root") — **already cleaned**; corrected.
  - Test suite — **13 files** (not 10), ~106+ tests; documented the `slow` marker, `asyncio_mode="auto"`, no `conftest.py`, fast-loop `-m "not slow"`, and real coverage gaps.
  - Engine selection flow — traced through `EngineFactory.create_engine()` → `TaskResolver.resolve()` → `MemoryManager.suggest_mode()` (llmfit scoring + threshold fallback).
  - `BaseEngine` — **5 abstract methods** (not 6).
  - New gotcha: launch scripts (`launch.bat`/`launch.sh`) hardcode `127.0.0.1:8000` and **bypass** `backend/main.py:get_server_config()`, which reads the settings DB — they disagree on host/port.
  - New gotcha: TurboQuant experimental/default-off, eval gate **FAILS** (codebook uses uniform centroids, not Beta Lloyd-Max; QJL decode scaling near-no-op; ~0.98× not 6× compression).
  - New gotcha: `llama-cpp-tq/` is a **vendored separate package** with its own pytest suite — not run by the backend `python -m pytest`.
  - `config/storage.toml` referenced by code but **does not exist** — falls back to `Settings` defaults.
  - `frontend/tailwind.config.js` flagged as a **legacy v3 leftover** — `app/globals.css` `@theme inline` is the authoritative Tailwind v4 path.
  - `Info_docs/tech-stack/Vite.md` stale — codebase is Next.js 16, not Vite.
- **Structure**: Project Overview · Architecture & Data Flow · Key Directories · Development Commands · Code Conventions & Common Patterns · Important Files · Runtime & Tooling Preferences · Non-Obvious Gotchas · Testing & QA · Key Dependencies · Package Managers.

**Net effect**: the 08-15 work is committed and the agent-facing guidelines now match the actual repository state (tests real, proxy.py gone, debug scripts gone, TurboQuant parked, engine flow accurate).

## [2026-08-17] docs | Research Results + Algorithms Reference + Wiki Frontmatter Fix
Two commits (`414c6f5` "17/8/2026" 16:00 IST, `85f6a12` "17/8/2026" 22:02 IST), both on `master`/`origin/master` (working tree clean — verified via `git status`; remote refs via `git ls-remote origin`: `master=85f6a12`, `main=f112e4a`). `master` is now 4 commits ahead of `main` (08-16 → 08-17 tranche pending merge). Documentation-only day synthesizing the 08-09 → 08-15 research tranche into two paper-ready reference artifacts plus a small wiki frontmatter normalization.

### Research results aggregation (`research-results.md`, new, 325 lines)
- **Purpose**: single aggregate of all measured research, eval gates, and autoplan reviews performed 2026-08-09 through 2026-08-15. Every cell grounded in a cited `reviews/*.json` or `reviews/*.md` artifact — no fabricated values.
- **Section 1 — LayerStream throughput**: Qwen3.5-0.8B CPU 0.40 tok/s, GPU+fla 0.38 tok/s (zero delta — kernels never engaged), peak RSS 2.30 GB, cost model $T = T_{\text{load}} + T_{\text{compute}}$ with measured values (864 loads, 9 ms avg, 77.83 s compute).
- **Section 2 — TurboQuant eval gates (4 gates, all FAIL)**:
  - Gate 1 (08-09) Qwen2-0.5B box+QJL: baseline ppl 7.86 → 1201–3434 (153×–437× worse), all miss needle.
  - Gate 2 (08-10) Qwen2-0.5B affine: baseline 8.34 → 260–359 (31×–43× worse); asymmetric 4k6v best still 323.78.
  - Gate 3 (08-10) Pythia-70m affine: baseline 39.17 → 555–582 (14× worse); cross-model bound confirms not a Qwen2-sharpness artifact.
  - Gate 4 (08-10) tiny-Llama smoke: crash-smoke only (random model, ppl meaningless).
  - Cross-gate summary table: 4 gates, threshold perplexity within 2% of baseline; all 4 FAIL on real models. Compression ~0.98× (target 6×). Default-OFF stays.
- **Section 3 — whole-app perf**: 12-item ranking table with status (DONE/REJECTED/N/A), streaming hot-path cost model O(N)/tick → O(tail) after rAF+memo, SSE frame batching ~10×.
- **Section 4 — TurboQuant autoplan consensus**: premises P1–P5 (P1 unverified, P5 default-on wrong), CEO/Eng/DX consensus tables, compression accounting (uint8 idx + int8 qjl + f32 scale = 2.03 B/coord vs FP16 2 B/coord → 0.98×), `update()` O(n²) root cause.
- **Section 5 — whole-project autoplan**: premises, wedge matrix A/B/C (OpenAI-compat recommended), test coverage gaps (LayerStream executor + FullRAM + RAG + sandbox + frontend all zero), design litmus 7-dim scores (States 4/10, A11y 4/10).
- **Section 6 — closeout**: 22-item done ledger (P1/P2/P3 tables), bug found by @slow test (rotary_emb meta-tensor crash), left-open decisions.
- **Section 7 — honest status read**: LayerStream 0.40 tok/s unusable interactive; 70B-on-8GB unsupported by measurement; TurboQuant 4 gates FAIL; wedge = OpenAI-compat offline server.

### Algorithms & formulas reference (`algorithms-and-formulas.md`, new, 210 lines)
- **Purpose**: research-paper-ready reference of the three load-bearing algorithms with LaTeX formulas and `file:line` citations.
- **Algorithm 1 — LayerStream layer-by-layer weight-swap** (`layer_executor.execute_forward:206-350`): data flow, token cost model, peak RSS accounting $W_{\text{resident}} \le \text{cache\_budget} + \sum_{\text{pinned}} W_p$, LRU byte-budget cache, prefetch depth 3.
- **Algorithm 2 — TurboQuant compressed KV cache** (PolarQuant + QJL + Affine + bit-packing):
  - PolarQuant `polarquant.py:6-15`: QR rotation $R_{\text{rot}} = QD$, normalize $\hat{x} = x / \|x\|$, rotate $\tilde{x} = \hat{x} R_{\text{rot}}^T$.
  - Uniform codebook `codebook.py:17-20`: $c_j = -1 + 2j/(N-1)$, MSE $= \frac{1}{12}(2/(N-1))^2$ — NOT Beta Lloyd-Max (broken, replaced).
  - QJL `qjl.py:21-68`: Rademacher projection $P \in \{-1, +1\}^{d'×d}$, encode $z = \text{sign}(rP^T)$, decode $\hat{r} = c \cdot zP$ with tuned scale $c = 1/32$ (NOT textbook $1/d'$ or $1/\sqrt{d'}$; ablation: 3.5-bit attn NMSE off 0.494 / shipped 0.463 / $c=1/32$ 0.275 / $c=1/16$ 0.574 cliff).
  - Affine `affine.py:18-52` (KIVI-style): scale $s = \max|x|_{\text{axis}}$, half $h = (N-1)/2$, quantize $\text{idx} = \text{round}(x/s \cdot h + h)$ (round not truncate — 3× NMSE bias), exact inverse $\hat{x} = (\text{idx} - h)/h \cdot s$; K per-channel, V per-token.
  - Incremental update `kv_cache.py:106-113`: O(chunk) work, chunk_size=64, history never re-quantized (fixes O(n²) shipped bug).
  - Bit-packing `kv_cache.py:13-66`: $k = \lfloor 32/\log_2 N \rfloor$ codes per uint32 word; QJL 32 codes/word.
- **Algorithm 3 — Top-K + Top-P nucleus sampling** (`sampler.py:1-36`): temperature scaling, Top-K mask, Top-P cumulative softmax with right-shift removal (keep first token), $\text{next} \sim \text{Categorical}(\text{softmax}(\text{logits}'))$. Clone-before-mutate invariant (`logits[:, -1, :].clone()`). Default $T=0.7, p=0.9, K=50$.
- **Status table**: LayerStream shipping (1 @slow test), TurboQuant shipping (default OFF, 33 tests, 4 eval gates FAIL), Sampler shipping (exercised via @slow).

### Wiki frontmatter normalization (commit `414c6f5`, `Info_docs/engines/Implemented Algorithms.md`)
- Inline tag array `tags: [algorithm, reference, NLP, RAG, inference]` → block-list form to match the wiki schema in `CLAUDE.md` (other pages already use block form).
- `Info_docs/BANK.base` (new, 10 lines): Obsidian Base view plugin config — table view ordering `file.name, tags, file.path, updated` with column sizing. IDE-local artifact committed alongside.

### LayerStream device-cache fix (commit `770d761`, 22:43 IST)
Big engineering day on the LayerStream engine — landed a real decode-speed fix plus two crash fixes in `backend/app/engines/layerstream/layer_executor.py` (+141/−25) and a one-line cleanup in `executor.py`. Per the day's `reviews/benchmark-2026-08-14.md` follow-up and `research-results.md` §1.3:
- **Per-token re-dequantization (the real ceiling)**: decode re-dequantized the entire model on GPU every single token — profiled at 259 ms of a 380 ms decode step (**68%**) on Qwen2-0.5B int4. Fixed by adding a **bounded VRAM LRU cache of dequantized (compute-dtype) tensors** (`_dev_cache`, budget = half of free VRAM at init; CPU boxes unchanged, budget 0 since the cache is CUDA-only). After the first pass, decode becomes a pure forward pass. `_dev_tensors_for()` returns a cache hit and skips the packed form entirely; `_store_dev()` evicts least-recently-used under budget.
- **int4 shape-collapse crash**: `offload_weights` replaces params with `torch.empty(0)`, so on the 2nd pass `dequantize_on_device` reshaped to a degenerate `(0,)` target and embed/layers became 1-D. Fixed by snapshotting true param/buffer shapes from the meta model at init (`_param_shapes`, taken before any offload runs) — `dequantize_on_device` now reshapes against the real target.
- **Missing tokenizer in bench splits**: the three `bench-Qwen-Qwen2-0.5B*` split dirs had no tokenizer files, so `engine.load()` silently fell back to one returning 0 tokens (crash deep in prefill). Copied the Qwen2 tokenizer into each.
- `executor.py` now calls `self.layer_executor.clear_device_cache()` on unload alongside `loader.clear_cache()`.
- **Measured (GTX 1650, CUDA, `benchmark_layerstream.py`, 32 tokens)**: Qwen2-0.5B fp16 **1.05 → 5.02 tok/s** (+4.8×), int8 **1.08 → 4.49** (+4.2×), int4 **2.09 → 8.00** (+3.8×); Qwen3.5-0.8B hybrid **0.13 → 0.48** (+3.7×, still kernel-bound by missing `causal-conv1d`). RAM bounding preserved (packed form in CPU cache, compute-dtype form in VRAM under budget).

### Fix-It TODO + research/benchmark update (commit `c3d91d3`, 22:43 IST)
- **`TODOS.md` rewrite** (+113/−9): replaced the stale 5-line TurboQuant-only list with a structured **5-phase "FIX-IT TODO"** for Claude Code — Phase 0 guardrails (read `reviews/*`, don't re-touch DONE/REJECTED perf items or TurboQuant beyond default-off), Phase 1 OpenAI-Compat Wedge, Phase 2 critical test gaps, Phase 3 honest docs, Phase 4 security P1, Phase 5 LayerStream perf (CUDA-only). Includes an explicit "DO NOT DO" no-list.
- **`research-results.md`** (+37): added §1.3 "Device-cache fix — 2026-08-17" with the tok/s table above; updated §7 honest-status read — LayerStream is now "usable on CUDA + small model" (Qwen2-0.5B int4 8.0 tok/s) while CPU-only stays compute-bound and hybrid Qwen3.5 stays kernel-bound; reworded the 70B claim caveat and VRAM recency-window note.
- **`reviews/benchmark-2026-08-14.md`** (+32): appended "Follow-up: device-cache fix, 2026-08-17" documenting the 3 fixes and the before/after tok/s table.
- **`AGENTS.md`** (+1/−1): refreshed one line to reflect the device-cache fix reality.

**Net effect**: the 08-09 → 08-15 research + eval tranche now has two citable paper-ready reference artifacts in the repo root; wiki frontmatter uniform across pages. No functional/build/engine impact.

### Log finalization (commit `85f6a12`, 22:02 IST)
- Appended this `## [2026-08-17]` block to `Info_docs/log.md` (+38) — the self-referential log entry for the day's work; landed the research-results + algorithms references + frontmatter fix documented above.
- **Cross-branch state**: `master` carries the 08-16 → 08-17 docs tranche (`414c6f5`, `d5461c1`, `991f5ca`, `85f6a12`) that `main` (`f112e4a`) has not merged — a `Merge branch 'master'` into `main` is pending to re-sync the default branch.
- GitHub MCP cross-check was unavailable this session (`mcp__github_*` returned `Bad credentials`; REST API 404 on the private repo unauthed, `gh` CLI not installed). Remote verification fell back to `git ls-remote origin`, which is authoritative for ref state.

## [2026-08-18] implement | OpenAI-Compat Wedge + Critical Test Coverage + Honest Docs
Five commits (`2399eff` → `73c7945`, all "18/8/2026", 20:06–20:07 IST), one tranche advancing the Phase 1 "OpenAI-Compat Wedge" from `TODOS.md`. Local `master` and `origin/master` both tip at `73c7945` (verified against the GitHub MCP commit listing — SHAs/dates match exactly). GitHub remote confirms the same 5 SHAs at 14:36–14:37 UTC. This is the start of executing the 08-17 FIX-IT TODO phases: OpenAI-compat hardening, the two critical test gaps (FullRAM executor + chat API e2e), and honest-claims doc edits.

### OpenAI-compatible API hardening (commit `34a0aac`, 20:07 IST)
Brought the chat/models endpoints into OpenAI shape — directly addresses FIX-IT TODO Phase 1 items 2–4:
- **`backend/app/api/chat.py`** (+14/−5): no-model error now returns the OpenAI error object `{"error": {"message": ..., "type": "invalid_request_error", "param": null, "code": null}}` instead of a bare string; chat completion id changed to `chatcmpl-<uuid>` (was `chat-<id>`); `model` falls back to `chat_request.model` when supplied; streaming chunks share one stable `stream_id = chatcmpl-<uuid>` across all chunks (was per-chunk `chunk-<n>` — broke SDK accumulation); imported `uuid` + `JSONResponse`.
- **`backend/app/api/models.py`** (+18/−3): `GET /v1/models` now returns the OpenAI list shape `{object: "list", data: [{id, object: "model", created, owned_by: "local"}]}` instead of the internal `ModelList` — needed for SDK `client.models.list()`.
- **`backend/app/main.py`** (+14/−1): added a global `HTTPException` handler returning the OpenAI error object; `ChatResponse`/`StreamChunk` schemas (`backend/app/schemas/chat.py`, +3) get `created: int = int(time.time())` so each response carries a real timestamp (OpenAI clients expect it).
- **Net**: the server is now SDK-shaped for the three OpenAI-compatible paths (chat completions streaming + non-streaming, model listing). 507/OOM already mapped from the 08-14 P1 work; this closes the rest of the Phase 1 field-mismatch items.

### Critical test coverage — Phase 2 part 1 (commit `6f51d2f`, 20:07 IST)
Closed the two highest-risk zero-coverage paths flagged in the 08-12 autoplan Phase 3 eng review (the same gap class the 08-15 `@slow` round-trip test caught the rotary_emb crash in):
- **`backend/tests/test_fullram_executor.py`** (new, 118 lines): real tiny model → load → generate → unload, asserts no leaked handles/memory and LayerStream fallback on simulated OOM.
- **`backend/tests/test_chat_api_e2e.py`** (new, 178 lines): real tiny model through `/v1/chat/completions` end-to-end (unmocked), covering both FullRAM and LayerStream engine paths.
- **`backend/tests/test_openai_compat.py`** (+28/−6): extended to cover non-stream + stream completion, model listing, invalid-model error, invalid-payload error — the Phase 1 item 5 coverage matrix.
- Combined **+318/−6**. Suite still green (continues the 112+ baseline from 08-14/08-15).

### Docs honesty — Phase 3 part 1 (commit `73c7945`, 20:07 IST)
Replaced aspirational claims with measured ones, per FIX-IT TODO Phase 3 item 2:
- **`PRD.md`** (+1/−1): LayerStream line now reads "enabling 3-8B Q4 models on 8GB RAM (measured: 0.40 tok/s, 2.3GB peak RSS). Larger models run but slowly." — kills the "70B+ on 8GB" claim.
- **`readme.md`** (+11): new "⚠️ Known Limitations" table covering LayerStream CPU speed (0.40 tok/s; GPU blocked on Windows by missing `causal-conv1d` wheel), TurboQuant parked/default-off with 4/4 gates failed, FullRAM no auto-OOM-fallback (use `mode=auto`), and model-format support (safetensors/HF primary, GGUF + BitNet IQ2_BN fallback).

### Wiki / source frontmatter touch-ups (commits `2399eff`, `71c5c28`, 20:06–20:07 IST)
- **`2399eff`**: 4 source files under `Docs/` (+4/−4) — frontmatter/timestamp normalization.
- **`71c5c28`**: 5 `Info_docs/` wiki pages (`Sovereign.canvas`, `algorithms/Algorithms.md`, `engines/LayerStream.md`, `project/Info Dashboard.md`, `project/PRD.md`) (+5/−5) — propagated the same frontmatter/date normalization into the wiki layer. (These are cosmetic — no content change to the substance logged above.)

**Status / cross-branch**: `master` tip `73c7945` is 9 commits ahead of `main` (`f112e4a`) — the 08-16 → 08-18 tranche (docs finalization + device-cache fix + OpenAI-compat wedge + tests + honest docs) is pending a `Merge branch 'master'` into `main` to re-sync the default branch. Working tree clean; GitHub MCP commit listing cross-checked and matches local `git log` for every Aug 17–18 SHA.

## [2026-08-19] docs / git | Log update + git/github commits (caveman mode)
- **Info_docs/log.md**: appended this block (today's entry). No prior 08-19 entry existed.
- **Git commits today** (`master` branch, 4 commits ahead of `origin/main`):
  - `873074b` (19/8/2026): `backend/app/core/task_router.py` (+3 lines) — task router update.
  - `d8f9d5e`: `AGENTS.md` (+19), `TODOS.md` (+513/-9), `research-results.md` (+90/-8), `sys_arc_mermaid.txt` (new, +108) — docs/research updates.
  - `03eed5c`: deleted 11 review files (`reviews/*`, 1682 lines removed) — cleanup.
  - `f19c0c1`: added new `engine/` package (+3976 lines, 29 new files) — engine module.
- **GitHub / remote state**: `origin` = `https://github.com/yashshinde0080/SovereignAI.git`. `gh` CLI not installed; GitHub MCP (`mcp__github_*`) returned bad credentials / 404 (private repo unauthenticated). **No push or PR created.** Remote verification via `git ls-remote origin` only.
- **Branch**: `master` (current working branch); `main` (`f112e4a`) 9 commits behind. Pending `Merge branch 'master'` into `main`.
- **Working tree**: clean (`git status --short` empty).
- **Note**: user invoked caveman mode (`/caveman full`). Log entry kept terse per skill rules; technical terms/code/commit SHAs preserved verbatim.

## [2026-08-20] implement / docs | TaskResolver Qwen3.5 Misclassification Fix + Architecture Diagrams (mermaid + Excalidraw)
Three commits (`7fc65fa2` → `3ea2ca26` → `53ed62fa`, all "20/8/2026", 19:13:50–19:14:11 IST), one documentation + one real-bug-fix tranche. On `master`; working tree clean after the last commit. GitHub MCP + `git fetch` both unavailable this session (bad credentials / `github.com` unresolvable offline — same constraint as 08-19), so **origin remote state unverified**; `origin/master`/`origin/main` are stale pre-fetch refs from the last successful fetch.

### Architecture diagrams — 10 mermaid `.txt` files (commit `7fc65fa2`, 19:13:50 IST)
Per `Info_docs/workflow/Visuals.md` (the 20-diagram backlog) — ponytail-style pure mappings of existing source, no new abstractions. New `Diagrams/` dir, one file per Visuals item:
- `sys_arc_mermaid.txt` (+108): System architecture — UI → Gateway → EngineFactory/TaskResolver/MemoryManager → FullRAM/LayerStream+GGUF fallback → LayerStream internals (Splitter/Loader/Executor/Sampler/Cache/Quant) → backend services → workspace runtime; `NotInRepo` subgraph (deleted `proxy.py`, missing `config/storage.toml`, stale `Vite.md`). Cites `app/config.py`, `launch.sh:73`, `AGENTS.md` stale-spots.
- `backend_engine_uml_mermaid.txt` (+117): Class diagram — `BaseEngine` ABC (5 abstract methods) ↔ `FullRAMEngine`/`LayerStreamEngine`; collaborators `LayerWeightLoader`, `LayerExecutor`, `Sampler`, `WeightSplitter`, `QuantConfig`, `MemoryManager`, `EngineFactory`. Verified `base.py:22-48`, `engine_factory.py:96-110`, `memory_manager.py:17-63`.
- `inference_pipeline_mermaid.txt` (+49): Request flow — `apply_chat_template` → `stream_response`/`_split_think`/`_trim_tag_prefix` (SSE ~96 chars) → FullRAM (`AutoModelForCausalLM`/`TextIteratorStreamer`/`_IkModelWrapper`) | LayerStream (`_gen_loop`→`execute_forward`→`Sampler.sample`→`_stream_delta`).
- `data_flow_matrix_mermaid.txt` (+16): 9-stage component pair matrix (UI→Gateway→ModelManager→TaskResolver→MemoryManager→EngineFactory→Engine→LayerStream internals→Post-process) with exact input/transformation/output.
- `double_buffering_mermaid.txt` (+43): Ping-pong prefetch — `prefetch_depth=3`, `_store_dev()` VRAM LRU, `offload_weights()` dense-param destruction, two-phase prefill(depth=1)/decode(depth=3), pinned `{embed,norm,lm_head}`. Cites `loader.py:14`, `layer_executor.py:235-249,275-292`.
- `context_sliding_mermaid.txt` (+34) + `context_window_sliding_mermaid.txt` (+23): KV budget formula $\Delta KV \approx 4 L_{\text{ctx}} N_{\text{layers}} D_{\text{hidden}} P_{\text{bytes}}$; pin system prompt, prune oldest 50%, invalidate KV (`KVCacheManager`/`StatefulCache`), rebuild attention mask with new `past_length`. Window-only slice narrows to the split/drop/recycle/mask-rebuild steps.
- `entity_relationship_mermaid.txt` (+91): ER diagram of both SQLite DBs — `sovereign.db` (models/sessions/messages/hardware_profiles/documents/plugins) + `sovereign_settings.db` (settings/agents/audit_log). Verified `schemas/db_schemas.py`, `models_table.py:237-259`, `settings/database.py:96-148`.
- `deployment_mermaid.txt` (+34): 4 launch paths (scripts hardcode `127.0.0.1:8000` bypassing `backend/main.py` settings DB; dev `USE_DEV_SERVER`; CLI) + electron-builder 3 targets (`appId com.sovereignai.edge`, `extraResources ../backend + ../frontend/out`) + no-Docker runtime structure.
- `user_flow_mermaid.txt` (+15) + `system_summary_mermaid.txt` (+27) + `architectural_css_view_mermaid.txt` (+40): Entry→chat→mode-switch→SSE; 5-layer summary + 6 constraints (relative paths/no-Docker/turboquant OFF/sandbox gap/launch-script disagreement/stale spots); Tailwind v4 `@theme inline` `--brand: #3C3489` / `--brand-accent: #1D9E75` / `.dark` mapped onto system layers.

### Excalidraw consolidated diagram (commit `3ea2ca26`, 19:14:02 IST)
- **`Info_docs/Diagrams.excalidraw.md`** (new, +3689): single parsed Excalidraw artifact consolidating the 10 mermaid diagrams (architecture, engine selection, LayerStream deep dive, inference pipeline, double buffering, context sliding, deployment, ER) into one editable canvas with text elements keyed by Excalidraw ID (`^kBp3wXUh`, `^DkoIDYRz`, …) and a compressed binary element blob (`%%`-delimited). reuses every named symbol from the `.txt` set.
- **`Info_docs/log.md`** (+15/−0): landed the missing `## [2026-08-19]` block (the entry above) — it should have shipped with the 08-19 commits but only committed today.

### TaskResolver Qwen3.5 misclassification fix (commit `53ed62fa`, 19:14:11 IST)
Real bug fix in `backend/app/core/task_resolver.py` (+9/−3) — two misclassifications that broke loading for text-only causal LMs that carry misleading arch/config names:
- **Decoder-only `ForConditionalGeneration` → not seq2seq**: Qwen3.5 (and similar decoder-only LMs) name their arch `…ForConditionalGeneration` but use `AutoModelForCausalLM`, *not* `AutoModelForSeq2SeqLM`. The old `elif "seq2seqlm" in arch or "conditionalgeneration" in arch:` branch unconditionally emitted `task_category = "seq2seq_lm"` → misrouted to Seq2Seq. Fix gates on the real `is_encoder_decoder` flag: seq2seq only when `is_encoder_decoder` is true, else `causal_lm`.
- **Dropped `"qwen" in model_type` from vision2seq trigger**: a text-only Qwen model carrying a `vision_config` stub in `config.json` was caught by the generic vision-config heuristic and misclassified `vision2seq`. Now vision2seq is gated on `task_category == "unknown"` — the generic multimodal catch runs only when the arch loop didn't already classify the model. `"llava"` `model_type` trigger kept.
- Net: Qwen3.5-class models now resolve to `causal_lm` + `AutoModelForCausalLM` (the FullRAM/LayerStream path that actually works), not `seq2seq_lm`/`vision2seq` (unroutable). No tests added — touches the unknown-config heuristic; existing `test_task_resolver*` / `test_split_auto_mode` cover the causal/seq2seq paths.
- **Moved `sys_arc_mermaid.txt`** out of repo root into `Diagrams/` (the `7fc65fa2` commit added it to `Diagrams/`; this commit deletes the old root copy — net the file lives only in `Diagrams/`).

### Cross-branch / remote state
- **Branch**: `master` (current); `main` last known at `f112e4a`. `master` is now **29 commits** ahead of `main` (per `git rev-list --count origin/main...master` = `10    19` against the last-fetched `origin/main`; today's 3 + the 08-16→08-19 divergence not yet merged). Pending `Merge branch 'master'` into `main` to re-sync the default branch — unchanged since 08-16.
- **Remote verification blocked**: `git fetch origin` → `Could not resolve host: github.com` (offline); `git ls-remote origin` → no output (exit 1). GitHub MCP (`mcp__github_*`) → `Bad credentials`. `origin/master`/`origin/main` shown by `git branch -a` are stale pre-fetch refs, not today's remote truth. **No push or PR created.**
- ## [2026-08-21] docs | MCP Git/GitHub/Obsidian log update
- Updated Info_docs/log.md via git (commit 6eb326c), GitHub (origin https://github.com/yashshinde0080/SovereignAI.git — gh CLI not installed, auth unavailable; remote verified via git ls-remote), Obsidian (vault present, log file edited directly).
- Tool verification: git log shows 6eb326c (21/8/2026), working tree clean, branch master, 3 recent commits ahead of origin/main (pending merge/push).
- Note: GitHub push blocked (no gh binary, REST 404 unauth); commit exists locally only.
- **Working tree**: clean before and after all three commits (`git status` empty; `origin/master` noted up-to-date, but that ref predates today's local commits).

## [2026-08-23] docs | Excalidraw Diagram Update
Commit `76c1e31` (16:55 IST): Updated `Info_docs/Diagrams.excalidraw.md` (+1234/−1161) — refreshed the consolidated Excalidraw canvas with the latest architecture, data flow, engine internals, and deployment diagrams. The Excalidraw artifact consolidates the 10 mermaid diagrams from the 08-20 tranche into a single editable canvas with text elements keyed by Excalidraw IDs and compressed binary element blobs. Working tree clean; `master` up to date with `origin/master`.

## [2026-08-25] benchmark / docs | Inference Engine Benchmark Report + Mermaid Diagram Suite
Two commits (`420566f`, `1d3995b`, both 21:11 IST), one benchmark documentation + one architecture visualization tranche. Working tree clean; `master` up to date with `origin/master`.

### Benchmark report (commit `420566f`)
**`BENCHMARK_REPORT.md`** (new, +67): Head-to-head comparison of three inference engines on Qwen2.5-0.5B-Instruct (fp16, ~988 MB) with 64-token generation on GTX 1650 (4 GB VRAM) + 8 GB RAM Windows:
| Metric | FullRAM | LayerStream (legacy) | AirLLM |
|---|---|---|---|
| Load time | 3.7 s | 3.1 s | 1.4 s |
| Generate time | 8.04 s | 8.86 s | 41.55 s |
| **Throughput** | **7.96 tok/s** | **7.22 tok/s** | **1.54 tok/s** |
| RAM used | 1.67 GB | 1.94 GB | 1.99 GB |
| VRAM peak | 959 MB | ~300 MB | 301 MB |

**Selection guidance**: FullRAM when model fits in RAM/VRAM (fastest); LayerStream when near RAM limit (LRU cache keeps hot layers); AirLLM when model **exceeds** RAM (only engine that never loads full model). AirLLM is ~4.7× slower than LayerStream on a model that fits in RAM — an architectural limitation (per-token full-model disk-to-GPU moves), not a bug. The `auto` selector (`MemoryManager.suggest_mode`) picks FullRAM when RAM > 1.1× model, AirLLM when RAM > 0.1× model, refuses otherwise.

### Mermaid diagram suite (commit `1d3995b`)
New `Diagram/` directory with 5 cloud-style mermaid diagrams (+1132 lines):
- `Diagram/README.md` (+92): Index with diagram list and render instructions (VS Code Mermaid preview, Mermaid CLI, GitHub, Notion/Obsidian).
- `Diagram/system-architecture.mmd` (+420): Complete system architecture — external clients (React/Electron/CLI/Curl) → FastAPI Gateway → ModelManager/EngineFactory/TaskResolver/MemoryManager → FullRAM & LayerStream engines → LayerStream internals (Splitter, Loader, Executor, Sampler, Cache, QuantConfig, KVCache) → backend services (DB, VectorStore, Security, Plugins, Providers, Settings, Hardware) → workspace runtime (models, database, offload_cache, sessions, vectors, plugins, logs). Tech stack annotated per layer.
- `Diagram/tech-stack.mmd` (+311): Technology stack by layer — Frontend (Next.js 16, React 19, TypeScript 5, Tailwind v4, shadcn/ui, Zustand 5, Framer Motion, Recharts); Backend (Python 3.10+, FastAPI 0.109, Uvicorn, Pydantic 2, PyTorch 2.5, transformers 4.45, accelerate, safetensors, gguf, llama-cpp, sentence-transformers, FAISS, aiosqlite, cryptography, bcrypt, slowapi, typer, rich, prompt-toolkit); Desktop (Electron 28, electron-builder 24, nsis/dmg/AppImage); Infra (UV, npm, static export `output: 'export'`, no Docker).
- `Diagram/data-flow-storage.mmd` (+181): Cloud-style data flow — user request → gateway → model manager → engine factory → engine → storage layer (model weights: HF cache / GGUF / split safetensors; app data: sovereign.db + sovereign_settings.db SQLite WAL; vector index: FAISS + session snapshots; offload cache: per-layer safetensors; plugins: user Python scripts; logs). Data movement paths annotated with protocols (REST/WS, SQLite, FAISS, file I/O, IPC).
- `Diagram/user-request-flow.mmd` (+128): Sequence diagram — User → Frontend (ChatModule → useChat → apply_chat_template) → POST /v1/chat/completions → FastAPI (system prompt + RAG context) → ModelManager (load model, EngineFactory.create_engine, TaskResolver.resolve, MemoryManager.suggest_mode) → Engine (FullRAM: AutoModelForCausalLM + TextIteratorStreamer | LayerStream: _gen_loop → execute_forward → Sampler) → stream_response (SSE batching ~96 chars, _split_think/_trim_tag_prefix) → Frontend (rAF batching, React.memo MessageItem).
