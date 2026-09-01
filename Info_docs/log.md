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