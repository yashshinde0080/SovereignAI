# TODOS — Issue Tracker

Source: `reviews/issues-21-8-2026.md` (57 issues found 21 Aug 2026)

## Completed

- [x] **P0 ISSUE-01** — Unload-before-load loses active model on failure (`model_manager.py`)
- [x] **P1 ISSUE-02** — Silent stream failure mid-SSE (`chat.py`)
- [x] **P1 ISSUE-03** — Auth middleware queries SQLite on every request (`middleware.py` + `service.py`)
- [x] **P1 ISSUE-04** — `trust_remote_code=True` hardcoded in 6 places (`executor.py`, `task_resolver.py`, `splitter.py`)
- [x] **P2 ISSUE-05** — ~~LayerStream prompt in output~~ FALSE POSITIVE (not a bug)
- [x] **P2 ISSUE-06** — `suggest_mode()` precedence bug (`memory_manager.py`)
- [x] **P2 ISSUE-08** — Tokenizer failure swallowed silently — improved error comment (`fullram/executor.py`)
- [x] **P2 ISSUE-11** — `ConnectionPool.close_all()` incomplete — now tracks all connections (`database/connection.py`)
- [x] **P2 ISSUE-12** — 4 dead code files — deleted (`scheduler.py`, `prefetch.py`, `memory.py`, `mmap_loader.py`)
- [x] **P2 ISSUE-13** — 7 bare `except:` clauses — replaced with `except Exception:` (7 files)
- [x] **P2 ISSUE-15** — FullRAM no VRAM reporting — added `torch.cuda.memory_allocated()` (`fullram/executor.py`)
- [x] **P2 ISSUE-17** — ThreadPoolExecutor never shut down — added `executor.shutdown()` (`loader.py`)
- [x] **P2 ISSUE-18** — `scan_installed()` blocks startup (`model_manager.py`)
- [x] **P2 ISSUE-21** — Fake disk speed default — returns `0.0` on failure (`hardware_detector.py`)
- [x] **P2 ISSUE-22** — AVX2 always True on Windows — returns `False` on Windows (`hardware_detector.py`)
- [x] **P2 ISSUE-24** — PluginSandbox no real isolation — documented limitation (`sandbox.py`)
- [x] **P2 ISSUE-47** — ~~llama_cpp non-chat includes prompt~~ FALSE POSITIVE (LayerStream builds output from scratch)
- [x] **P1 ISSUE-48** — Splitter OOM on large models — added memory preflight check (`splitter.py`)
- [x] **P3 ISSUE-25** — Dir creation at import time — wrapped in try/except for read-only USBs (`config.py`)
- [x] **P3 ISSUE-28** — `config/storage.toml` doesn't exist — removed dead reference (`main.py`)
- [x] **P3 ISSUE-36** — Plugin cleanup silent — logs exceptions (`plugins/manager.py`)
- [x] **P3 ISSUE-38** — Frontend no retry — uses `Promise.allSettled()` (`page.tsx`)
- [x] **P3 ISSUE-40** — Approximate chunk count — returns actual count (`rag.py`)
- [x] **P3 ISSUE-45** — aiohttp session not cleaned — added `provider.cleanup()` to shutdown (`main.py`)
- [x] **P3 ISSUE-46** — `fnmatch` import in loop — moved to top of function (`huggingface.py`)
- [x] **P3 ISSUE-57** — `main.py` connection leak — added `finally: conn.close()` (`backend/main.py`)

## Open — P1

- [ ] **P1 ISSUE-52** — RAG ingest blocks event loop — wrap `embed_texts()` in `asyncio.to_thread` in `vectorstore/manager.py`

## Open — P2

- [ ] **P2 ISSUE-07** — Fuzzy match non-deterministic — improve `_fuzzy_match_model()` ranking in `model_manager.py`
- [ ] **P2 ISSUE-09** — nvidia-smi per-client per-second — cache GPU metrics in `websocket/metrics.py`
- [ ] **P2 ISSUE-10** — SettingsDB new connection per call — add connection pooling in `settings/database.py`
- [ ] **P2 ISSUE-14** — 57 `print()` statements in backend — replace with `logger` (14 files)
- [ ] **P2 ISSUE-16** — StatefulCache GPU-only — add `max_gpu_bytes` threshold with CPU eviction in `kv_cache.py`
- [ ] **P2 ISSUE-23** — RAG context exceeds context window — check `max_position_embeddings` in `chat.py`
- [ ] **P2 ISSUE-29** — 3 duplicate DB systems — unify on one connection strategy
- [ ] **P2 ISSUE-30** — ModelRegistry new connection per query — hold persistent aiosqlite connection in `registry.py`
- [ ] **P2 ISSUE-33** — KV cache unbounded growth — enforce `max_position_embeddings` in `kv_cache.py`
- [ ] **P2 ISSUE-39** — No error boundary on ChatModule — add React error boundary in `frontend/app/page.tsx`
- [ ] **P2 ISSUE-53** — Predictable encryption salt — use random key in `security/encryption.py`

## Open — P3

- [ ] **P3 ISSUE-19** — No session cleanup — call `cleanup_old()` on startup in `main.py`
- [ ] **P3 ISSUE-20** — No periodic WAL checkpoint — add checkpoint every 1000 writes
- [ ] **P3 ISSUE-26** — HF_HOME override breaks USB portability — force workspace path in `config.py`
- [ ] **P3 ISSUE-27** — Launch scripts bypass `main.py` — update `launch.sh`/`launch.bat`
- [ ] **P3 ISSUE-31** — BenchmarkTracker eager updates — lazy evaluation in `benchmark.py`
- [ ] **P3 ISSUE-32** — Mask cache full clear — LRU eviction in `layer_executor.py`
- [ ] **P3 ISSUE-34** — Download uses print not callback — use `progress_callback` in `huggingface.py`
- [ ] **P3 ISSUE-35** — `engine/` directory dead code — delete or archive
- [ ] **P3 ISSUE-37** — `workspace.py` uses `os.path` — refactor to `pathlib.Path`
- [ ] **P3 ISSUE-41** — `compare_modes` misleading — rename endpoint or document limitation
- [ ] **P3 ISSUE-42** — RAG threshold 0.0 — use configurable threshold in `chat.py`
- [ ] **P3 ISSUE-43** — Window controls unimplemented — add handlers or remove from `preload.js`
- [ ] **P3 ISSUE-44** — Electron hardcodes port — read from settings in `electron/main.js`
- [ ] **P3 ISSUE-49** — `inspect.signature` per layer per call — cache signatures in `layer_executor.py`
- [ ] **P3 ISSUE-50** — Attention mask per-token allocation — pre-allocate in `layer_executor.py`
- [ ] **P3 ISSUE-51** — Delete doesn't rebuild FAISS — auto-rebuild or document in `vectorstore/manager.py`
- [ ] **P3 ISSUE-54** — Encryption non-atomic — write to temp first in `encryption.py`
- [ ] **P3 ISSUE-55** — `ensure_safetensors` no permission check — check writable in `safetensors.py`
- [ ] **P3 ISSUE-56** — LayerStream no modality check — validate at load in `executor.py`

## Summary

| Status | Count |
|--------|-------|
| Completed | 28 |
| Open P1 | 1 |
| Open P2 | 11 |
| Open P3 | 17 |
| **Total** | **57** |
