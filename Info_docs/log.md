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