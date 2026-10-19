# SovereignAI Edge - Capabilities Report

## What This Project Can Do

### 1. **Run Local LLMs** ✅
- Three inference engines backed by a unified FastAPI gateway
- **FullRAM**: Load entire model into RAM/VRAM via `transformers.AutoModelForCausalLM`
- **LayerStream**: Low-RAM path, swaps layer weights from disk per forward pass
  - Enables 3–8B Q4 models on ~8GB RAM
  - Qwen2-0.5B int4: ~8.0 tok/s
  - Qwen3.5-0.8B hybrid: ~0.48–1.30 tok/s (with cache)
- **CloudAPI**: Proxies to external providers (OpenAI, Anthropic, Google, Mistral, custom/self-hosted)

### 2. **Three User Interfaces** ✅
- **React Web**: Next.js 16 + React 19 (App Router, RSC, static export)
- **Electron 28**: Desktop wrapper (Windows/macOS/Linux builds)
- **Python CLI**: typer-based console interface (`sovereign` command)

### 3. **REST API** ✅
- `POST /v1/chat/completions` — OpenAI-compatible chat completions
- `POST /v1/chat/execute` — Task-based input delegation
- `POST /v1/chat/mode/switch?mode=cloud` — Switch to cloud provider
- `GET /v1/cloud/*` — Provider CRUD, model list refresh, connectivity test
- SSE streaming with batching (~96 chars/frame), think-strip separation

### 4. **Model Management** ✅
- `ModelManager` with fuzzy model name matching
- `EngineFactory.create_engine()` — auto-detects task type, resolves mode
- `MemoryManager.suggest_mode()` — llmfit scoring + threshold fallback
- Auto-loads `startup_model` from settings DB on startup
- Split+fullram mode resolution redirects to base path

### 5. **Settings & Configuration** ✅
- `pydantic-settings` `BaseSettings` with env prefix `SOVEREIGN_`
- Reads `.env` if present (git-ignored, placeholder at `.env.example`)
- Two SQLite DBs in WAL mode:
  - `sovereign.db` — models, sessions, documents, hardware_profiles, plugins
  - `sovereign_settings.db` — settings (JSON-blob), agents, audit_log
- All paths relative via `Path(__file__).parent...` for USB portability
- `HF_HOME` forced to `workspace/hf_cache`

### 6. **Security** ✅
- Fernet + PBKDF2HMAC (480k iters) for API key encryption
- Machine-salt from `platform.node()` + `uuid.getnode()`
- `lan_auth_middleware` — opt-in Bearer token via `secrets.compare_digest`
- Localhost stays auth-free for Electron/CLI loopback
- Cloud API keys masked in GET responses, never returned in full

### 7. **RAG (Retrieval-Augmented Generation)** ✅
- FAISS RAG vector store
- `sentence-transformers ≥2.2.0` for embeddings
- Chunkers, retrievers, metadata storage in `workspace/data/vector_index/`
- Migrated from `workspace/vector_index/` (old location, deleted 2026-09-14)

### 8. **Plugin System** ✅
- `PluginInterface` ABC — `initialize()`, `cleanup()`, `get_actions()`, `execute(action, params)`
- Dynamic import via `importlib.util`
- `PluginSandbox` = timeout-only (30s) — no FS/network/memory isolation on Windows
- User scripts in `workspace/plugins/`

### 9. **CLI Tools** ✅
- `sovereign` console script (typer)
- Commands: `run`, `chat`, `serve`, `pull`, `import`, `benchmark`, `list`, `system`, `cloud`
- Cloud commands: `cloud add`, `cloud list`, `cloud remove`, `cloud test`, `cloud models`

### 10. **Testing** ✅
- **215 fast tests** + **5 slow tests** all passing (AGENTS.md count)
- pytest >=8.0 + pytest-asyncio >=0.23.0
- Markers: `slow`
- No `conftest.py` — all fixtures inline per-file
- Test coverage: CLI, SSE, stream batching, think-strip, fuzzy model match, split-auto mode, layerstream loader, turboquant, OpenAI compat, plugin sandbox, cloud engine, FullRAM executor, engine-factory/auth, settings, hardware detector, RAG chunks/citations/dedup/retrieval/hardening, system API, suggest mode, stream delta/batch, vectorstore sync

### 11. **Benchmarks** ✅ (not pytest, not collected)
- `benchmarks/accuracy_eval.py` — eval gate
- `benchmark_layerstream.py` — real t/s + peak RAM
- `benchmark_layerstream_phase_a.py` — LRU/prefetch
- `benchmarks/qjl_ablation.py` — QJL ablation study
- `benchmarks/kv_structure_probe.py` — KV structure analysis
- `benchmarks/reference_polar_probe.py` — reference polar probe

### 12. **Electron Integration** ✅
- Bundles `../backend` → `backend/` and `../frontend/out` → `frontend/`
- AppId: `com.sovereignai.edge`
- loads `localhost:3000` in dev (`USE_DEV_SERVER=true`), else `app://` protocol
- Electron-builder: nsis (Win), dmg (mac), AppImage+deb (Linux)

### 13. **Landing Page** ✅
- Separate Next.js 14 + React 18 + Tailwind v3 site
- Independent `package.json` and `page-lock.json`

## Key Conventions Followed
- **Snake_case** for backend modules/classes
- **camelCase** for frontend functions, **PascalCase** for components
- **kebab-case** for CLI commands (typer)
- **All paths relative** — no absolute paths anywhere, runs from USB
- **Async patterns**: Coroutines for IO-bound engine methods, async generators for SSE, `asyncio.to_thread` for blocking PyTorch, `ThreadPoolExecutor` for disk prefetch
- **Engine interface**: All engines implement `BaseEngine` ABC (5 abstract methods)
- **Cloud mode**: Bypasses `TaskResolver` and `MemoryManager` entirely
- **No Docker/compose** — 100% local/offline
- **TurboQuant**: Experimental, default-OFF, eval gate fails on Qwen2-0.5B and Pythia-70m

## What's NOT Included (or Limited)
- ⚠️ TurboQuant: experimental, default-OFF, eval gate fails on test models
- ⚠️ Chat e2e: TestClient broken by starlette/httpx incompatibility
- ⚠️ Plugin sandbox: timeout-only, no FS/network/memory isolation on Windows
- RAG, hardware_detector, and settings test coverage confirmed by added tests

## Quick Start
```bash
# From backend directory
python main.py       # Dev server (hot-reload via SOVEREIGN_RELOAD=1)

# Or production
cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Run tests
cd backend && python -m pytest -m "not slow"   # Fast loop (~30-60s)
cd backend && python -m pytest               # All tests including slow

# CLI
sovereign chat     # Start chatting
sovereign serve    # Start server
```