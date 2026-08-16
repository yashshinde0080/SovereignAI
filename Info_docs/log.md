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
  | config | ppl | deg | needle |
  |---|---|---|---|
  | baseline | **8.34** | — | ✅ PINEAPPLE123. The |
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
Committed (13d26c9, 158ac51, 483b0ec). Three threads: a real-engine round-trip test that caught a latent LayerStream bug, a GPU-kernel availability check that closed out the 08-14 benchmark, and the security settings UI that finished the P1 auth story's frontend half.

- **LayerStream round-trip test** (`backend/tests/test_layerstream_roundtrip.py`, new): `@slow` full executor round-trip on a freshly-split tiny Llama — copies the tokenizer, runs `generate_stream`, and unloads. Closed the "zero coverage on high-risk LayerStream executor" gap from the 08-12 Phase 3 eng review. A `slow` pytest marker registered in `backend/pyproject.toml` so these real-engine tests run with `-m slow` and skip by default.

- **Bug the round-trip exposed** (`backend/app/engines/layerstream/layer_executor.py`, +11): `execute_forward` crashed on `rotary_emb.to(device)` for **any non-hybrid Llama/Qwen2 model** — the `inv_freq` buffer arrives as a meta tensor (`init_empty_weights`) and `.to()` on a meta tensor raises *"Cannot copy out of meta tensor"*. Fix materializes `inv_freq` from `rope_theta` first (same formula as `assign_weights`' meta-buffer branch) before relocating. This would have failed the first `generate` on every standard Llama/Qwen2 split — masked until now because the 08-14 benchmark used the hybrid Qwen3.5 (path without this branch).

- **GPU benchmark follow-up** (`backend/benchmark_layerstream.py` +10, `reviews/benchmark-2026-08-14.md` +26): re-ran on the box's GTX 1650 (torch 2.5.1+cu124 + `triton-windows` + `flash-linear-attention 0.2.2`, all venv-local). **0.38 tok/s ≈ CPU (0.40)** — zero delta, because transformers' Qwen3_5 fast path needs **both** fla and `causal-conv1d`; `causal-conv1d` has no Windows wheels (PyPI or GitHub) and the box has no `nvcc`/MSVC. Kernel availability now printed by the runner (`cuda=… fla=… causal_conv1d=…`). Fast-attention delta is **parked, not abandoned** — needs a Linux CUDA box or a global CUDA Toolkit install.

- **Settings UI auth** (`frontend/components/settings/SecuritySettings.tsx` +43, `frontend/lib/api.ts` +13): API Token field + LAN-exposure warning (shown when `bind_localhost_only=false`); the API client now sends `Authorization: Bearer` from localStorage — the frontend half of the P1 auth+path-safety item, completing the middleware added 08-14.

- **Closeout report** (`reviews/completed-2026-08-12-to-2026-08-15.md`, new): the full 22-item done/deferred ledger for the 08-12 review application — 112 tests passing, lists the three left-open decisions (gguf IQ2_BN patch, TurboQuant parked, tags/releases pending, fast-attention delta needs Linux CUDA).

## [2026-08-16] implement | Engine Benchmark Suite + LayerStream Performance Decision + Honest Pitch Correction
Committed (2463d94, d9fc444, dfc2a3b, be00932, 9733608, cc4c6be, 324d7e1, bf3f39d, 9a80f2f). Major benchmarking tranche across all three engines + the design decision that re-positions the product pitch around measured numbers.

### Engine Benchmark Master Report (`reviews/benchmark-engines-2026-08-16.md`)
Consolidated cross-engine comparison on the 8 GB dev box:
| Engine | Model | tok/s | Peak RAM delta | RAM/file |
|---|---|---|---|---|
| LayerStream (CPU) | 0.8B FP16 split | 0.40 | 2.30 GB | — |
| FullRAM CPU (fp32) | 0.5B Q4 | **3.84** | +1.93 GB | **4.1x** |
| FullRAM CUDA (fp16) | 0.5B Q4 | **7.03** | +2.25 GB | **4.8x** |
| llama.cpp CPU | 0.5B Q4 | **24.05** | +0.48 GB | **1.0x** |
| llama.cpp --gpu-layers | 0.5B Q4 | 28.95 | +0.48 GB | 1.0x |
| llama.cpp CPU | **3B Q4** | **5.44** | **+2.27 GB** | **1.2x** |

**Key findings:**
- LayerStream compute = 98% of wall time; I/O is 9% (already overlapped). No I/O fix produces 4x.
- FullRAM/transformers dequantizes Q4 to fp32/fp16 at ~4x file size → 3B Q4 needs ~9.7 GB (OOM on this box).
- llama.cpp keeps weights quantized in RAM (1.0-1.2x file) → **3B Q4 runs at 5.44 tok/s on 8 GB**, the only engine that can.
- Speedup: llama.cpp 60x LayerStream, 6.3x FullRAM CPU on 0.5B Q4.
- Corrected pitch: **"0.5-1B Q4 in RAM via FullRAM; 3-8B Q4 via llama.cpp at ~5 tok/s on 8 GB."**

### LayerStream Performance Decision (`reviews/design-layerstream-perf-2026-08-16.md`)
Office-hours outcome:
- **Diagnosis**: Compute 98%, I/O 9% (prefetch already overlaps). Torch layer-by-layer cannot beat llama.cpp fused kernels.
- **Approach A (shipping)**: FullRAM Q4 0.5-1B is the product wedge. LayerStream off-by-default, experimental badge in UI.
- **Approach B (next, 1-2 weeks)**: llama.cpp mmap offload for beyond-RAM GGUF. Beyond-RAM becomes usable (10-50x faster than LayerStream).
- **Approach C (parked)**: torch.compile/CUDA graphs/fused kernels — reopens only if spike shows within ~3x of llama.cpp.
- **Parked I/O list** (revisit triggers in `reviews/parked-io-fixes-2026-08-16.md`): Q4/Q8 weight quantization, deeper prefetch, GDS/O_DIRECT, LLM-in-a-Flash, causal-conv1d Linux setup.

### FullRAM Q4 Benchmark Detail (`reviews/benchmark-fullram-2026-08-16.md`)
Measured `qwen2.5-0.5b-instruct-q4_k_m.gguf` (469 MB):
- CPU fp32: 3.84 tok/s, 63.4 s load, +1.93 GB RAM (4.1x file)
- CUDA fp16: 7.03 tok/s, 66.8 s load, +2.25 GB RAM (4.8x file)
- Projection: 3B Q4 ~8-10 GB (no), 8B Q4 ~20 GB (no). FullRAM ceiling = ~1B Q4.
- Load time = UX killer (minutes for 3B+). llama.cpp mmap = seconds.

### llama.cpp Offload Spike (`reviews/spike-llamacpp-offload-2026-08-16.md`)
Validated Approach B mechanism:
- 3B Q4 on 1.17 GB free RAM: 5.44 tok/s, 2.31 GB RSS (1.2x file), 5.6 s load.
- FullRAM/transformers cannot run this model at all (~9.7 GB fp32).
- Integration note: existing llama_cpp fallback only triggers on transformers "not supported yet" — needs explicit beyond-RAM router decision.

### Implementation landed (dfc2a3b, be00932)
- `MemoryManager.suggest_mode` now uses honest 4x GGUF residency so "auto" picks FullRAM only for models that fit; LayerStream flagged experimental (engine attr, API fields, UI badges).
- Fixed suggest_mode crash (`a and b or c` precedence: None metadata raised AttributeError).
- New runners: `backend/benchmark_fullram.py`, `backend/benchmark_llamacpp.py` (mirror LayerStream runner).
- New test: `backend/tests/test_suggest_mode.py` (7 tests).
- 112 backend tests pass; frontend typecheck clean.

### Frontend/UI (cc4c6be, 324d7e1)
- ModeSwitcher: experimental badge for LayerStream, improved FullRAM/LayerStream labels.
- ModelTable: engine badge column.
- GeneralSettings: engine select shows experimental warning.
- Types: `types/index.ts` added `experimental` flag to engine info.

### Repo hygiene (2463d94)
- Deleted `Info_docs/Excalidraw/SovereignAI.excalidraw.md` (314 lines) and `Info_docs/Kanban_board.md` (34 lines) — stale design artifacts.

### Documentation created
- `reviews/benchmark-engines-2026-08-16.md` — master cross-engine report (224 lines)
- `reviews/benchmark-fullram-2026-08-16.md` — FullRAM detail (136 lines)
- `reviews/design-layerstream-perf-2026-08-16.md` — design decision (121 lines, updated +51)
- `reviews/spike-llamacpp-offload-2026-08-16.md` — Approach B spike (70 lines)
- `reviews/parked-io-fixes-2026-08-16.md` — parked I/O list with revisit triggers (102 lines)

### Status
DONE_WITH_CONCERNS — FullRAM benchmark measured, pitch corrected, engine routing implemented, Approach B validated. Open: Approach B router wiring (beyond-RAM GGUF -> llama.cpp).