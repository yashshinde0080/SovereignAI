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