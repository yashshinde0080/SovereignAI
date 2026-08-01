---

kanban-plugin: board

---

## backlog



## To Do



## In Progress



## In review



## Done

- [x] Workspace Snapshots + Mode Comparison + RAG Hardening + Plugin Marketplace (July 30)
	  - Backend: Workspace API (CRUD for workspace snapshots)
	  - Backend: Benchmark compare (compare_modes)
	  - Backend: RAG hardening (upload cap, validation)
	  - Frontend: Workspace Snapshots UI
	  - Frontend: Home page hardware suggestions banner
	  - Frontend: Documents page drag-and-drop upload
	  - Frontend: Benchmark page mode comparison UI
	  - Frontend: Plugins page with placeholder plugins
	  - Frontend: Sidebar updates
	  - Frontend: Hooks type safety and notifications
	  - Frontend: API client typed methods
	  - Electron: Notification support via IPC
	  - Root: install.sh script
	  - Root: TODOS.md update
	  - Root: pyproject.toml asyncio_mode
	  - Root: .gitignore update
- [x] TypeScript Type Safety + UI Polish Sweep (July 31)
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
- [x] Masked LM Support + Stream Delta Fix + Safetensors Compatibility + TypeScript Polish (Aug 1)
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
- [x] Initial Wiki Build (July 21)
	  - Added wiki schema to CLAUDE.md (page format, operations, index/log conventions)
	  - Created index.md — catalog of all 31 wiki pages by category
- [x] TurboQuant KV Cache Compression (July 23)
	  - Created `backend/app/engines/shared/turboquant/` package (config, polarquant, qjl, codebook, kv_cache, hf_proxy)
	  - Added settings: `turboquant_enabled`, `turboquant_bits`, `turboquant_qjl_enabled`, `turboquant_rotation`
	  - Wired into LayerStream engine via optional `turboquant_config` param on `LayerExecutor`
	  - Added `KVCacheManager.create(mode="turboquant")` factory to layerstream/kv_cache.py
	  - Added `use_turboquant` flag to FullRAM `KVCache`
	  - Added `sovereign benchmark-turboquant` CLI command
	  - Self-check verifies PolarQuant + QJL reconstruction MSE < 0.02 on unit vectors
	  - Skipped bit-packing (ponytail) — add when real memory pressure is measured
- [x] Ponytail Review (July 24)
	  - Ran `/ponytail-review` across full codebase
	  - Found ~3800 lines of unnecessary complexity (dead providers, duplicate task resolvers, 1003-line inference handler with 18 unused task handlers, USB bundle protocol over-engineering, zombie memory manager, etc.)
	  - Created [[workflow/Ponytail Review|Ponytail Review]] page, updated index
	  - Created log.md — timeline tracking
	  - Batch-ingested 31 Docs/ sources into wiki pages with frontmatter, synthesis, and [[wikilinks]]
	  - Cross-linked related pages: PRD↔TRD, FullRAM↔LayerStream, tech-stack↔Technical Architecture, etc.
- [x] Ponytail Audit (full project) (July 24)
	  - Scanned all backend (21,813 lines) + frontend (8,303 lines) + root
	  - Found ~5000 lines removable across USB bundle provider, enterprise repo, ManualStream, inference.py handlers, settings over-engineering, root clutter, singleton pattern, layerstream executor duplication
	  - Created [[workflow/Ponytail Audit|Ponytail Audit]] page, updated index, appended to log
- [x] Literature Review (July 24)
	  - Created [[project/Literature Review|Literature Review]] — 6 high-impact papers on edge AI, quantization, attention, speculative decoding, RAG
	  - Cross-linked to FullRAM, LayerStream, Engine Algorithms
	  - Updated index, appended to log




%% kanban:settings
```
{"kanban-plugin":"board"}
```
%%