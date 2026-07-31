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

## [2026-07-24] ingest | Literature Review
- Created [[project/Literature Review|Literature Review]] — 6 high-impact papers on edge AI, quantization, attention, speculative decoding, RAG
- Cross-linked to FullRAM, LayerStream, Engine Algorithms
- Updated index, appended to log

## [2026-07-24] review | Ponytail Audit (full project)
- Scanned all backend (21,813 lines) + frontend (8,303 lines) + root
- Found ~5000 lines removable across USB bundle provider, enterprise repo, ManualStream, inference.py handlers, settings over-engineering, root clutter, singleton pattern, layerstream executor duplication
- Created [[workflow/Ponytail Audit|Ponytail Audit]] page, updated index, appended to log

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
- **Root — Commit analysis**: 5 commits touching 39 files across frontend (678 insertions, 490 deletions)
- **Types** (`frontend/types/index.ts`): Defined 8 new interfaces replacing `any` usage: `Agent`, `CurrentModel`, `DownloadStatus`, `HistoryPoint`, `Model`, `Recommendation`, `TaskResult`, `WorkspaceSnapshot`. Replaced 3 `Record<string, any>` with `Record<string, unknown>` across `SystemStatus`, `Metrics`, `SearchResult`
- **API client** (`frontend/lib/api.ts`): Added typed imports for all 14 response types. Added explicit return types to 12 API methods. Downgraded `any`-based `listModels`/`getRecommendations` calls. Removed all `as any` casts from API responses
- **Store** (`frontend/store/index.ts`): Collapsed boilerplate — replaced 79-line dual interface+store with compact 71-line direct `create` with inline type argument. Removed `setHistory` function-argument overloading pattern. All `any` metrics/history setter types downgraded to inferred from interface
- **Hooks** (`frontend/hooks/`): Hook-level type safety — `useModels` now imports and casts `SystemStatus`, `CurrentModel`, `DownloadStatus` from `@/types`. `useMetrics`, `useChat`, `usePlugins` similarly typed. All catch blocks use `errMsg()` utility instead of `error.message`/`String(error)`. `useModels.notify()` drops `(window as any)` cast in favor of declared `electronAPI` interface
- **Utilities** (`frontend/lib/utils.ts`): Exported shared `errMsg()` helper for safe error message extraction across all hooks and pages
- **Components — Build repair**: Fixed 4 pages dropping `Block`/`Element` implicit type dependencies: benchmark (removed `GitCompare` dependency), console (removed `as any` on `api.getCurrentModel`), documents (native `SearchResult`/`QueryResult`), models (`DownloadStatus`)
- **Sidebar** (`frontend/components/layout/Sidebar.tsx`): Complete rewrite — ordered nav items list, added cn/link hover styles, keyboard accessible settings button, versioned footer. Removed `TopBar` component
- **Settings** (`frontend/components/settings/`): 7-file TypeScript diet — `SettingsMap` + `Agent` typed imports, `EMPTY` constant replaces empty-object inline literals, `Record<string, any>` → `Record<string, unknown>` in section-update signatures
- **Blanket pattern removal**: `as any` on all state setter calls (`setSystemStatus`, `setHardware`, `setExecutionMode`), `catch (err: any)` → `catch (err)`, `useEffect(..., [])` → `useEffect(..., [dep])` for exhaustive deps
- **Design tokens** (`frontend/app/globals.css`): 4 new CSS custom properties — `brand`, `brand-accent`, `success` — in both light and dark themes. `animate-pulse` spinner reworked with `border-t-transparent` for accessible loading states
- **Workspace page** (`frontend/app/workspace/page.tsx`): `useCallback` wrapping for `loadSnapshots`, delete confirmation via native `window.confirm()`, loading skeleton state, `errMsg()` integration. Inline types migrated to imported `WorkspaceSnapshot`
- **Documents page** (`frontend/app/documents/page.tsx`): `useToast` added for all operations (upload success/fail, load fail, delete). Upload error state via `toast` not just console. `QueryResult` type from `@/types` replaces inline `any`
- **Home page** (`frontend/app/page.tsx`): `Recommendation` type import replaces inline `any[]`. Unused `MemoryStick` and `Zap` icon imports removed
- **Plugins page** (`frontend/app/plugins/page.tsx`): `Puzzle` placeholder icon for empty marketplace state. `useEffect` dep array `[refresh]` instead of `[]`. Badge sizes: `text-[10px]` → `text-xs`
- **Benchmark page** (`frontend/app/benchmark/page.tsx`): Mode comparison card added with new foreign-key lite compareBinderUnion wrapping. `errMsg()` in all catch blocks. Loading spinners use `aria-hidden="true"` for accessibility. Mode result interface extracted to module scope
- **Overall**: 100+ TypeScript strict-type breadcrumbs, full `any`→typed migration for all 21 primary data shapes, zero `as any` casts in production paths