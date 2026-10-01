## [2026-09-22] refactor+chore | Code cleanup + dependency pruning
- Cloud engine: fixed doc references `TODOS.md` → `TODO.md` in `engine.py` and `providers.py`
- Plugin sandbox: simplified to timeout-only execution — removed `max_memory_mb` knob (unenforceable on Windows), `ThreadPoolExecutor`, `resource` import; `PluginSandbox` now only enforces `asyncio.wait_for` timeout (docstring updated)
- Backend deps: removed `tensorflow`, `torchaudio`, `torchvision` from `pyproject.toml` (unused, pulled by old transformers dev build)
- Frontend: added `@plugin "@tailwindcss/typography"` to `globals.css` for prose classes used by `MessageList.tsx`; migrated slider from `@radix-ui/react-slider` to `radix-ui` (single package), removed `@radix-ui/react-slider` from `package.json`/`package-lock.json`
- Commits: 67fbf6a, 7cda500, 09767eb, bc843e0

## [2026-09-21] refactor+chore | Code cleanup + dependency stabilization
- Backend database: simplified `DatabaseManager` connection handling in `manager.py` (removed redundant logic, -35 net lines); removed `toml` dependency and optional `config/storage.toml` coupling
- VectorStore: removed unused config surface in `vectorstore/config.py` (-29 lines, deleted `load_vector_config`); tightened `manager.py` import chain to use defaults from Settings
- Dependencies: pinned stable releases in `uv.lock` + `requirements.txt` — transformers 4.45.2 (from 5.3.0.dev0), tokenizers 0.20.3 (from 0.22.2), typer 0.9.0 (from 0.24.1); removed `shellingham`, `typing-inspection`, `toml` transient deps; `pyproject.toml` synced
- Commits: 727bc80, 5bcc2b6

## [2026-09-20] fix+test | Cloud API key stability + graceful decryption + test regressions
- Cloud encryption: replaced machine-derived key (hostname + MAC) with persisted random key in workspace/database/.secret_key — prevents InvalidToken 500 storm when active NIC changes; key now travels with USB workspace
- Registry: `_decrypt()` catches InvalidToken, logs warning, returns empty string (caller masks as ****) — no 500 on /v1/cloud/* endpoints; user re-saves key to fix
- Registry: `update_provider()` now returns masked shape (api_key_masked) matching CloudProviderOut serialization — avoids "Field required" 500 on provider edit
- Requirements: pinned httpx<0.28 (0.28 removed `app` kwarg used by starlette TestClient)
- Tests: added test_undecryptable_key_degrades_gracefully (regression for old key orphaning); test_persisted_key_is_stable_across_instances (verifies shared secret); test for masked return shape on update_provider
- Commits: 077eb5e, 8317124, 7935a99, b494b21, 3fd4446

## [2026-09-19] feat+chore | README refresh + UI preview assets
- Docs: readme.md updated (+58/-44) — refreshed project overview and layout
- Assets: added electron-preview.png (51 KB) and web-ui-preview.png (293 KB) to Info_docs/assets/ for landing/docs
- Commits: 2b87848, 5792033

## [2026-09-18] patch+doc | RAG prompt fix + line-based architecture in readme
- Backend RAG: patched prompt in RAG to fix retrieval behavior — updated prompt template for better context injection
- Docs: updated readme.md with line-based architecture diagram for clearer system overview
- Commits: a557067, 7eb3844

## [2026-09-16] test+ci+chore | Fast HTTP chat e2e, GitHub Actions CI, start-script rework
- Backend: added `tests/test_chat_api_http.py` (156 lines, 5 tests) driving `POST /v1/chat/completions` through the real HTTP stack — routing, SSE framing, error paths — with a fake engine on `app.state` (no model, fast loop); complements the `@slow` real-model e2e
- CI: added `.github/workflows/backend.yml` — ruff + fast pytest (`-m "not slow"`) on push/PR touching `backend/**`, path-filtered; un-ignored `.github/` in `.gitignore` (previously ignored, so CI never existed); TODO.md fast-suite count 139 → 144
- Chore: deleted `start-desktop.bat` and `start-web.bat` (absolute-path uvicorn launchers); added new per-app one-click launchers `start_backend.bat`, `start_electron.bat`, `start_web.bat`; `.gitignore` +`graphify-out/`
- Commits: 1d7e3fd, 1439822, ef2f36f, fa063e3

## [2026-09-15] refactor+test | Print→logger, ruff lint, USB signing, test fixes, cleanup
- Backend: replaced `print()` with `logger` across API, engines, providers, core; WS metrics now `discard()` + close dead sockets, bare except fixed in model_manager
- Backend: added `ruff` config to `backend/pyproject.toml` + `TODO.md` audit summary (WS metrics, bare except, USB signing, print removal, linter)
- Backend: USB bundle signing implemented via ed25519 (`app/providers/usb_bundle.py`) with verification on parse; added `tests/usb_bundle_signing_check.py` self-check
- Backend: added `tests/test_app_smoke.py` proving TestClient works without lifespan; fixed `_FakeEmbedder` in `test_vectorstore_sync.py` to use `zlib.crc32` + punctuation stripping for deterministic hashing; updated `test_layerstream_loader.py` assertion
- Backend: import cleanup + dead-code removal across benchmarks, engines, CLI, vectorstore, plugins; removed `ARCHITECTURE_DEEP_DIVE.md` and `TODOS.md`
- Config: `.gitignore` updated to ignore `opencode.json`
- Commits: e5142b0, 594b92c, 03f9bf0, 07d4494, 4e6f3cd, 1cddf17

## [2026-09-14] doc | Update workspace paths in AGENTS.md, readme, and Diagrams
- AGENTS.md: workspace/vector_index/ → workspace/data/vector_index/ path correction; workspace/vectors/ marked as obsolete
- readme.md: workspace/vectors/ → workspace/data/vector_index/ in file-system layout
- Diagrams.excalidraw.md: vector index path updated to workspace/data/vector_index/
- Info_docs/working/10-rag-vector-store.md: path updated

## [2026-09-13] fix+perf | Hybrid LayerStream crash fix + CPU device cache + repo hygiene
## [2026-09-13] fix | RAG FAISS/metadata desync self-heal + frontend lint/escaping cleanup
- Backend RAG fix: `delete_document()` now rebuilds the index instead of only logging a warning — stale FAISS vectors used to collide with fresh ingests (every search returned zero sources, "can't access sources"). `rebuild_index()` assigns `vector_index` cumulatively (was `len(all_embeddings)` which produced off-by-N duplicates). `ingest_text()` skips duplicate re-uploads (deterministic ID + INSERT OR REPLACE previously kept metadata flat while FAISS appended). Startup self-heals an existing desync (metadata is source of truth; rebuild or reset).
- Backend RAG: new `/v1/rag/stats` health endpoint (FAISS vs metadata counts, `in_sync` flag); upload now distinguishes 503 (PDF plugin/vector store unavailable) from 400 (unhandled type); `query_documents` uses `input_data` kwarg + `output`/`text` fallback for the engine call. Deleted dead `fullram/kv_cache.py`.
- Backend tests: new `test_vectorstore_sync.py` (167 lines) covering ingest/delete/re-ingest sync, cumulative rebuild, startup self-heal, and delete-all-then-ingest with a fake bag-of-words embedder (no model download).
- Frontend: React hook dep-array lint fixes (`useCallback`, `useEffect` deps in documents/page.tsx, page.tsx); HTML-entity escaping of quotes/apostrophes (`&apos;s`, `"`); `DocumentViewerModal` collapsed loading/error/chunks into one derived state; removed unused `taskType` props (`ChatModule`, `ClassificationModule`) and an unused `ScrollArea` import; `useMetrics` unused `SystemStatus` import dropped.
- Docs: added `backend/backend.md` + `frontend/frontend.md` READMEs;
  `components/task/README.md` documents the six parked task modules
  (intentionally unrouted, not dead code). Commits 6605264, 8474652, b83eeaf, 55c4f3d.

## [2026-09-07] feat | Crown spinner theme + CLI polish
- Backend: added crown spinner (`RICH_SPINNERS["crown"]`) to `backend/app/cli/main.py`; `_tui_header()` with crown logo · title · version pill; `_status_bar()` replacing `[dim]` banner; `_bubble()` for cleared messages; SpinnerColumn("crown") in `pull()` and `_run_chat()`; table title updated to `👑 SovereignAI Edge`
- Net: +187 lines, -23 lines in `backend/app/cli/main.py`

## [2026-09-06] feat | Crown spinner theme + CLI polish
- Backend: added crown spinner (`RICH_SPINNERS["crown"]`) to `backend/app/cli/main.py`; `_tui_header()` with crown logo · title · version pill; `_status_bar()` replacing `[dim]` banner; `_bubble()` for cleared messages; SpinnerColumn("crown") in `pull()` and `_run_chat()`; table title updated to `👑 SovereignAI Edge`
- Net: +187 lines, -23 lines in `backend/app/cli/main.py`

## [2026-09-04]
- No git commits; working tree modifications to `backend/tests/test_cloud.py`, `frontend/app/console/page.tsx`, `frontend/components/chat/DocumentViewerModal.tsx`, `frontend/components/task/ChatModule.tsx`

## [2026-09-03] feat | Cloud model UI + Models frontend refactor
- Frontend: added CloudModelList.tsx (142 lines), ModelControlPanel.tsx (53 lines modified), OnlineServices.tsx (239 lines), CloudProvidersSettings.tsx (303 lines), SettingsDialog.tsx (7 lines modified), ChatModule.tsx (10 lines modified), tabs.tsx (66 lines added)
- Frontend: updated useModels.ts, api.ts, store/index.ts, types/index.ts for models integration
- Frontend: added todo_front.md (174 lines) with task tracking

## [2026-09-01] doc | Added technical report
- Docs: added `TECHNICAL_REPORT.md` (+759 lines) (c16147c)

## [2026-08-31] feat | Desktop/Web starter scripts
- Backend: created `start-desktop.bat` and `start-web.bat` (14 lines each) for one-click server launch; these scripts hardcode `--host 127.0.0.1 --port 8000` when invoking `uvicorn app.main:app`

## [2026-08-30] refactor | Plugin system removal + readme rework
- Backend: deleted plugins REST API (`api/plugins.py`, 67 lines) and schemas (`schemas/plugins.py`, 19 lines); unmounted route from `api/router.py`
- Frontend: deleted plugins page (`app/plugins/page.tsx`), `PluginCard`/`PluginList` components, `usePlugins` hook, plugins API client + types; Sidebar entry removed
- Net: 406 lines deleted across 11 files; plugin backend internals (`app/plugins/` manager/sandbox/interface) untouched
- Docs: readme.md reworked (+265/-104)
- Commits: 0301f16, 213afa5, 6f1f25b, 0ffe786, f5c6116

## [2026-08-29] refactor | Thinking-mode rollback + DB connection reuse + hardware cache + font rebrand
- Backend: reverted reasoning feature end-to-end — removed `_split_think`, `_trim_tag_prefix`, incremental tag tracker and `enable_thinking` template flag from `chat.py`/`schemas/chat.py`; deleted `test_think_strip.py`; stream now emits plain content with 96-char batching only
- Frontend: removed Thinking toggle, ThinkingBlock, `Message.reasoning` and reasoning-delta handling in useChat (back to fixed `max_tokens: 512`); per-message model badge kept
- Backend perf: `ModelRegistry` + `SettingsDatabase` reuse one persistent SQLite connection (new `close()`) instead of connect-per-operation; `HardwareDetector` caches profile after first call, single nvidia-smi call for name+VRAM, cached disk benchmark; tidy-ups across engine_factory, model_manager, providers, audit, websocket metrics, vectorstore
- Style: swapped Inter for Oxanium (sans) + Source Code Pro (mono) in layout.tsx, reworked globals.css theme tokens to match (db38768)
- Docs: mermaid data-flow diagram added at repo root (`data-flow.md`); `Info_docs/Diagrams.excalidraw.md` refreshed with architecture image

## [2026-08-28] feat | Chat UX polish + per-message model badge
- Backend: stream_response() now accepts model_name and emits it in the first SSE chunk's delta (backend/app/api/chat.py)
- Frontend: useChat captures model_name from stream delta + non-stream response, stores on Message.model (types/index.ts); ChatWindow/MessageList thread modelName prop and render small model label under assistant avatar
- ChatModule: listens for 'chat:send' CustomEvent so empty-state suggestion cards one-click send; moves Stop button inline next to Thinking toggle; compacts RAG doc chips and footer text
- MessageList: new empty state with 3 quick-start suggestion cards (Explain code / Brainstorm / Summarize); tighter message spacing; code blocks get smaller header with inline Copy/Copied label; loading dots switch bounce→pulse

## [2026-08-26] docs | Documentation updates + research references
- Documentation updates: added research references to algorithms-and-formulas.md and research-results.md; updated log.md with new entry; verified 112 tests passing



