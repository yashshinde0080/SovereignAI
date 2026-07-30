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
- Remove dead speculative task router entries (44 YAGNI entries)
- Replace custom DatabaseManager with SQLAlchemy or sqlite-utils
- Patent LayerStream approach?
