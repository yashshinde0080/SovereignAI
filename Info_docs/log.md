## [2026-09-11] fix+perf | Hybrid LayerStream crash fix + CPU device cache + repo hygiene
- Backend fix: `StatefulCache` implemented the transformers-4.x cache protocol; transformers 5.12.1 (installed vs pinned 4.45.2) reads `has_previous_state(layer_idx)` as a METHOD and state via `layers[i].conv_states/recurrent_states` — every hybrid (Qwen3.5) LayerStream request crashed with `TypeError: 'bool' object is not callable`. `StatefulCache` now implements the 5.x protocol (regression tests: `test_stateful_cache_protocol.py`)
- Backend perf: LayerStream device-tensor cache was CUDA-only (`dev_cache_budget=0` on CPU) → 75% of decode wall time spent in `Tensor.to()` re-copying/re-casting all weights per token (cProfile, 08-11). CPU now gets a 50%-of-total-RAM budget that must cover the full per-token working set (a partial budget churns and measured 2× slower). Qwen3.5-0.8B hybrid: 0.48 → **1.30 tok/s** on the 8 GB dev box, peak RAM 2.9 GB; FullRAM fp32 control measured 2.25 tok/s (that's the CPU floor — `fla`/`causal-conv1d` are CUDA-only)
- Backend tests: new `test_engine_factory_and_auth.py` (auto-mode resolution, cloud branch, LAN auth incl. RFC-7235 case-insensitive scheme fix in `security/middleware.py`); suite now 134 tests (129 fast + 5 slow), all passing
- Repo hygiene: launch.bat/launch.sh now resolve host:port from the settings DB via `backend/main.py:get_server_config()` (were hardcoded 127.0.0.1:8000, bypassing `bind_localhost_only`); deleted root `__pycache__/proxy.cpython-314.pyc` + `backend/__pycache__` artifacts of deleted debug scripts; deleted stale `Info_docs/tech-stack/Vite.md` and cleaned its wikilinks (INDEX.md, React.md, Tailwind CSS.md, Zustand.md, Sovereign.canvas); readme benchmark table + test counts refreshed; AGENTS.md gotchas #2/#11 refreshed
## [2026-09-01] doc | Added technical report
- Docs: added `TECHNICAL_REPORT.md` (+759 lines) (c16147c)
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
## [2026-08-31] feat | Desktop/Web starter scripts
- Backend: created `start-desktop.bat` and `start-web.bat` (14 lines each) for one-click server launch; these scripts hardcode `--host 127.0.0.1 --port 8000` when invoking `uvicorn app.main:app`
## [2026-09-03] feat | Cloud model UI + Models frontend refactor
- Frontend: added CloudModelList.tsx (142 lines), ModelControlPanel.tsx (53 lines modified), OnlineServices.tsx (239 lines), CloudProvidersSettings.tsx (303 lines), SettingsDialog.tsx (7 lines modified), ChatModule.tsx (10 lines modified), tabs.tsx (66 lines added)
- Frontend: updated useModels.ts, api.ts, store/index.ts, types/index.ts for models integration
- Frontend: added todo_front.md (174 lines) with task tracking
## [2026-09-04]
- No git commits; working tree modifications to `backend/tests/test_cloud.py`, `frontend/app/console/page.tsx`, `frontend/components/chat/DocumentViewerModal.tsx`, `frontend/components/task/ChatModule.tsx`


## [2026-09-06] feat | Crown spinner theme + CLI polish
- Backend: added crown spinner (`RICH_SPINNERS["crown"]`) to `backend/app/cli/main.py`; `_tui_header()` with crown logo · title · version pill; `_status_bar()` replacing `[dim]` banner; `_bubble()` for cleared messages; SpinnerColumn("crown") in `pull()` and `_run_chat()`; table title updated to `👑 SovereignAI Edge`
- Net: +187 lines, -23 lines in `backend/app/cli/main.py`


## [2026-09-07] feat | Crown spinner theme + CLI polish
- Backend: added crown spinner (`RICH_SPINNERS["crown"]`) to `backend/app/cli/main.py`; `_tui_header()` with crown logo · title · version pill; `_status_bar()` replacing `[dim]` banner; `_bubble()` for cleared messages; SpinnerColumn("crown") in `pull()` and `_run_chat()`; table title updated to `👑 SovereignAI Edge`
- Net: +187 lines, -23 lines in `backend/app/cli/main.py`

## [2026-09-13] fix | RAG FAISS/metadata desync self-heal + frontend lint/escaping cleanup
- Backend RAG fix: `delete_document()` now rebuilds the index instead of only logging a warning — stale FAISS vectors used to collide with fresh ingests (every search returned zero sources, "can't access sources"). `rebuild_index()` assigns `vector_index` cumulatively (was `len(all_embeddings)` which produced off-by-N duplicates). `ingest_text()` skips duplicate re-uploads (deterministic ID + INSERT OR REPLACE previously kept metadata flat while FAISS appended). Startup self-heals an existing desync (metadata is source of truth; rebuild or reset).
- Backend RAG: new `/v1/rag/stats` health endpoint (FAISS vs metadata counts, `in_sync` flag); upload now distinguishes 503 (PDF plugin/vector store unavailable) from 400 (unhandled type); `query_documents` uses `input_data` kwarg + `output`/`text` fallback for the engine call. Deleted dead `fullram/kv_cache.py`.
- Backend tests: new `test_vectorstore_sync.py` (167 lines) covering ingest/delete/re-ingest sync, cumulative rebuild, startup self-heal, and delete-all-then-ingest with a fake bag-of-words embedder (no model download).
- Frontend: React hook dep-array lint fixes (`useCallback`, `useEffect` deps in documents/page.tsx, page.tsx); HTML-entity escaping of quotes/apostrophes (`&apos;s`, `&quot;`); `DocumentViewerModal` collapsed loading/error/chunks into one derived state; removed unused `taskType` props (`ChatModule`, `ClassificationModule`) and an unused `ScrollArea` import; `useMetrics` unused `SystemStatus` import dropped.
- Docs: added `backend/backend.md` + `frontend/frontend.md` READMEs; `components/task/README.md` documents the six parked task modules (intentionally unrouted, not dead code). Commits 6605264, 8474652, b83eeaf, 55c4f3d.
