# TODOS — Deferred & Future Work

> Created per CEO review report recommendation. All scope decisions logged.

## Phase 1 — Core Engine Validation (Next)
- [ ] Ship a working CLI that loads a model via LayerStream and generates text
- [ ] Test with a real developer who hit Ollama RAM limits; watch them use it

## Phase 2 — Polished Web UI
- [ ] One-line install script: `curl -fsSL sovereign.ai | bash`
- [ ] Hardware-optimized model suggestions on first run
- [ ] Workspace snapshots (save/restore sessions)

## Phase 3 — Desktop + USB
- [ ] Ship Electron wrapper with notifications
- [ ] Test USB-portable execution on Windows, Mac, Linux
- [ ] Hardware-optimized model suggestions

## Phase 4 — Ecosystem
- [ ] Plugin marketplace UI with install-from-URL
- [ ] Drag-and-drop RAG (files)
- [ ] Model comparison mode (FullRAM vs LayerStream)
- [ ] Desktop notifications for model events

## Phase 5 — Hardening
- [ ] Structured logging (replace print statements)
- [ ] Update error handling for all shadow paths (OOM, disk full, WebSocket disconnect)
- [ ] Write tests for API routes
- [ ] MemoryError → 507, suggest LayerStream mode
- [ ] Disk full check before LayerStream swap

## Deferred (no immediate plan)
- Test suite: add backend API tests
- Remove dead speculative task router entries (44 YAGNI entries)  *(note: eviction.py + layer_by_layer_inference.py already deleted; task map now 32 entries)*
- Replace custom DatabaseManager with SQLAlchemy or sqlite-utils
- Patent LayerStream approach?  *(autoplan review: drop — re-skin of llama.cpp mmap/swap)*

## /autoplan Review — Priority Items (2026-08-05, approved as-is)

### P1 (blockers)
- [ ] Run the 8GB validation spike: benchmark llama.cpp mmap / MoE / Q4 on real 8GB hardware; decide LayerStream's fate with numbers (premise P1)
- [ ] Fix the 98 frontend TypeScript errors (`models/page.tsx` props, `DownloadModal.tsx` duplicate imports) — `pnpm build` must pass
- [ ] Decide engine strategy post-spike: wrap llama.cpp vs keep custom PyTorch engine (premise P2)
- [ ] Add auth token + path-traversal validation before any binding beyond localhost

### P2 (high)
- [ ] Delete `manualstream/` (live trap) + orphaned layerstream helpers (`scheduler.py`, `prefetch.py`, `mmap_loader.py`, `introspection.py`, `splitter.py`)
- [ ] Shrink `task_router.py` to `{causal_lm, seq2seq_lm}` + AutoModel fallback; drop 30+ AutoModel imports
- [ ] Reconcile stale docs: AGENTS.md (test suite claim), CLAUDE.md (SQLAlchemy claim), PRD/TRD (Vite/React18/llama.cpp claims)
- [ ] Error paths: MemoryError→507 + LayerStream suggestion, client-disconnect cancellation, disk-full preflight, concurrent-load lock
- [ ] Real engine tests: LayerStream executor, `suggest_mode` boundaries, chat e2e with tiny Q4 model (see test plan in TRD.md appendix)
- [ ] `sovereign import <path.gguf>` offline model-acquisition flow
- [ ] OpenAI-compat contract test + docs for `/v1/chat/completions`
- [ ] 5-state chat lifecycle UI (no model / loading / ready / generating / error) + stop button + backend-offline state
- [ ] Disable/remove speculative `frontend/components/task/` UI modules

### P3 (polish)
- [ ] Structured logging to replace 147 `print()` calls
- [ ] Quickstart doc + error reference (code → cause → fix), verified copy-paste in CI
- [ ] Release tagging; pin install.sh to latest tag; migration notes
- [ ] Config knobs (port, bind, model dir) as env vars / `sovereign config`
- [ ] Design identity pass (taste: distinctive tokens, hero chat moment)
- [ ] Decision: commit to dark-only theme or build light toggle (taste)
