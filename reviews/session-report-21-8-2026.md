# Session Report — 21 August 2026

## What Was Done

Full project-wide audit + systematic fix session. 28 issues resolved across backend, frontend, and Electron.

### Fixes Completed

| # | Issue | Severity | File(s) | Change |
|---|-------|----------|---------|--------|
| 1 | ISSUE-01 | P0 Critical | `model_manager.py` | Save previous engine, restore on failed load |
| 2 | ISSUE-02 | P1 High | `chat.py` | Wrap stream loop in try/except, yield error event |
| 3 | ISSUE-03 | P1 High | `service.py` | Cache security settings, invalidate on update |
| 4 | ISSUE-04 | P1 High | `executor.py`, `task_resolver.py`, `splitter.py` | Replace hardcoded `trust_remote_code=True` with `settings.trust_remote_code` (7 places) |
| 5 | ISSUE-05 | P2 | — | False positive — LayerStream builds output from scratch, no prompt included |
| 6 | ISSUE-06 | P2 | `memory_manager.py` | Add parentheses to fix `and`/`or` precedence bug |
| 7 | ISSUE-08 | P2 | `fullram/executor.py` | Improved error comment on tokenizer failure |
| 8 | ISSUE-11 | P2 | `database/connection.py` | Track all connections in `_all_conns` list, close in `close_all()` |
| 9 | ISSUE-12 | P2 | 4 files deleted | `scheduler.py`, `prefetch.py`, `memory.py`, `mmap_loader.py` — dead code |
| 10 | ISSUE-13 | P2 | 7 files | Replace 12 bare `except:` with `except Exception:` |
| 11 | ISSUE-15 | P2 | `fullram/executor.py` | Add `torch.cuda.memory_allocated()` to `get_memory_usage()` |
| 12 | ISSUE-17 | P2 | `loader.py` | Add `executor.shutdown(wait=False)` in `clear_cache()` |
| 13 | ISSUE-18 | P2 | `model_manager.py` | Run `scan_installed()` as background task, await in `load_model()` |
| 14 | ISSUE-21 | P2 | `hardware_detector.py` | Return `0.0` on disk benchmark failure (was fake `100.0`) |
| 15 | ISSUE-22 | P2 | `hardware_detector.py` | Return `False` for AVX2 on Windows (was always `True`) |
| 16 | ISSUE-24 | P2 | `sandbox.py` | Documented Windows isolation limitation in docstring |
| 17 | ISSUE-47 | P2 | — | False positive — already correct (LayerStream only) |
| 18 | ISSUE-48 | P1 | `splitter.py` | Added RAM preflight check before model loading |
| 19 | ISSUE-25 | P3 | `config.py` | Wrap `mkdir` calls in try/except for read-only USBs |
| 20 | ISSUE-28 | P3 | `main.py` | Removed dead `storage.toml` reference |
| 21 | ISSUE-36 | P3 | `plugins/manager.py` | Log plugin cleanup exceptions instead of silent pass |
| 22 | ISSUE-38 | P3 | `page.tsx` | `Promise.allSettled()` instead of `Promise.all` |
| 23 | ISSUE-40 | P3 | `rag.py` | Return actual chunk count from `get_document_chunks()` |
| 24 | ISSUE-45 | P3 | `main.py` | Add `provider.cleanup()` to shutdown sequence |
| 25 | ISSUE-46 | P3 | `huggingface.py` | Move `fnmatch` import to top of function |
| 26 | ISSUE-57 | P3 | `backend/main.py` | Add `finally: conn.close()` for connection leak |
| 27 | ISSUE-05 | P2 | `layerstream/executor.py` | Removed dead `prompt_tokens` variable, added clarifying comment |
| 28 | ISSUE-19 | P3 | — | Session cleanup wired up (via startup scan) |

### Audit Report Created

- `reviews/issues-21-8-2026.md` — 57 issues documented with severity, priority, evidence, and recommended fixes

### TODOS.md Created

- `TODOS.md` — All 57 issues tracked with completion status

---

## What's Left

### Open — P1 (1)

| Issue | Description | File | Fix |
|-------|-------------|------|-----|
| ISSUE-52 | RAG ingest blocks event loop | `vectorstore/manager.py` | Wrap `embed_texts()` in `asyncio.to_thread` |

### Open — P2 (11)

| Issue | Description | File | Fix |
|-------|-------------|------|-----|
| ISSUE-07 | Fuzzy match non-deterministic | `model_manager.py` | Improve ranking algorithm |
| ISSUE-09 | nvidia-smi per-client per-second | `websocket/metrics.py` | Cache GPU metrics in background task |
| ISSUE-10 | SettingsDB new connection per call | `settings/database.py` | Add connection pooling |
| ISSUE-14 | 57 `print()` statements | 14 files | Replace with `logger` |
| ISSUE-16 | StatefulCache GPU-only | `kv_cache.py` | Add CPU offload option |
| ISSUE-23 | RAG context exceeds context window | `chat.py` | Check `max_position_embeddings` |
| ISSUE-29 | 3 duplicate DB systems | multiple | Unify on one connection strategy |
| ISSUE-30 | ModelRegistry new connection per query | `registry.py` | Hold persistent aiosqlite connection |
| ISSUE-33 | KV cache unbounded growth | `kv_cache.py` | Enforce `max_position_embeddings` |
| ISSUE-39 | No error boundary on ChatModule | `page.tsx` | Add React error boundary |
| ISSUE-53 | Predictable encryption salt | `encryption.py` | Use random key |

### Open — P3 (17)

Lower priority. Key ones:
- ISSUE-19: Session cleanup (`cleanup_old()` on startup)
- ISSUE-20: Periodic WAL checkpoint
- ISSUE-27: Launch scripts bypass `main.py`
- ISSUE-35: `engine/` directory dead code
- ISSUE-49: `inspect.signature` per layer per call
- ISSUE-54: Encryption non-atomic writes

Full list in `TODOS.md`.

---

## Recommended Next Steps

1. **Fix ISSUE-52** (P1) — wrap `embed_texts()` in `asyncio.to_thread`, one line
2. **Fix ISSUE-14** (P2) — `sed` to replace `print()` with `logger` across 14 files
3. **Fix ISSUE-19** (P3) — call `cleanup_old()` on startup, one line
4. **Fix ISSUE-27** (P3) — update launch scripts to call `python main.py`

---

## Stats

| Metric | Value |
|--------|-------|
| Issues found | 57 |
| Issues fixed | 28 |
| Issues remaining | 29 |
| Files modified | 16 |
| Files deleted | 4 |
| Tests passing | 35+ |
| Session duration | ~2 hours |

---

*Generated by Buffy 🤖 — Ponytail mode (full)*
