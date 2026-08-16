# Repository Guidelines

> SovereignAI Edge — portable, 100% offline AI platform running LLMs locally on consumer hardware or USB drives.

## Project Overview

SovereignAI Edge runs large language models fully offline on consumer hardware. Two inference engines back a unified FastAPI gateway:

- **FullRAM** — fast path, loads the entire model into RAM/VRAM via `transformers.AutoModelForCausalLM`. `llama-cpp-python` / `ik-llama-cpp-python` are fallbacks only, for architectures transformers cannot load (e.g. BitNet IQ2_BN GGUF).
- **LayerStream** — low-RAM path, swaps layer weights from disk per forward pass via raw PyTorch + safetensors. Enables 3–8B Q4 models on ~8GB RAM (the "70B on 8GB" claim was retracted in `reviews/benchmark-2026-08-14.md`, honest measured throughput 0.40 tok/s on Qwen2-0.5B).

Three UIs: React Web (Next.js 16 + React 19), Electron 28 desktop wrapper, Python CLI (typer). All paths relative — no absolute paths anywhere, runs from USB.

## Architecture & Data Flow

```
Client (React / Electron / CLI)
  → REST / WebSocket  (127.0.0.1:8000)
  → FastAPI Gateway  (/v1/*)
      Chat: system prompt + RAG context → apply_chat_template
            → engine.generate() or stream_response() SSE
      Model load: ModelManager.load_model()
            → EngineFactory.create_engine()
                → TaskResolver.resolve() (AutoConfig introspection)
                → MemoryManager.suggest_mode() (llmfit scoring > threshold)
            → FullRAMEngine or LayerStreamEngine
  → PyTorch + transformers (FullRAM)
    / raw PyTorch layer-by-layer (LayerStream)
      llama-cpp-python only as GGUF fallback
  → File I/O: ./workspace/{models,database,offload_cache,...}
```

### Data flow (chat request)

1. `backend/app/main.py:lifespan()` startup — inits DB, vector store, hardware profile, model manager, settings service, plugin manager; auto-loads `startup_model` from settings DB (`general.startup_model`, `general.default_mode`).
2. `POST /v1/chat/completions` → `app/api/chat.py:chat_completions()` — injects system prompt (`SettingsService.get_system_prompt()`), optional RAG via `vector_store.build_context(top_k=5)`, `apply_chat_template` with `enable_thinking` toggle.
3. Streaming: `stream_response()` async generator — SSE batching (~96 chars/frame), `_split_think` / `_trim_tag_prefix` for `<think>` reasoning separation, `is_disconnected()` check. Non-streaming: `engine.generate()`.
4. `POST /v1/chat/execute` delegates task-based input to `engine.generate()`. `POST /v1/chat/mode/switch?mode=` reloads model.

### Engine selection (in `ModelManager`, not in engines)

`ModelManager._load_model_locked()` → `EngineFactory.create_engine()`:
1. `TaskResolver.resolve()` — `AutoConfig.from_pretrained` introspection → `is_generative`, `task_type` (causal_lm, seq2seq_lm, masked_lm, classification, vision2seq). GGUF fallback → causal_lm+generative.
2. Mode resolution — `auto` mode: `MemoryManager.suggest_mode()` via `llmfit.score_model_fit` (fit>0.85 + RAM<70% → fullram; >0.6 → layerstream; else insufficient) with threshold fallback (CUDA VRAM 1.1x → fullram; RAM 1.1x → fullram; 0.1x → layerstream). Non-generative + layerstream-suggested → forced fullram.
3. `FullRAMEngine` or `LayerStreamEngine` instantiated → `engine.load()` → `app.state.{active_engine, active_model, active_mode}` updated.

### BaseEngine ABC (`backend/app/engines/base.py`)

5 abstract methods: `async load()`, `async unload()`, `async generate(input_data, **kwargs) -> Dict`, `async generate_stream(input_data, **kwargs) -> AsyncGenerator[Dict, None]`, `get_memory_usage() -> Dict`. Concrete `get_stats()`.

## Key Directories

| Path | Purpose |
|---|---|
| `backend/app/main.py` | FastAPI app + `lifespan()` startup/teardown |
| `backend/main.py` | Server entry — reads host/port from `sovereign_settings.db` (`security.api_port`, `security.bind_localhost_only`), `uvicorn.run('app.main:app')` |
| `backend/app/api/` | REST endpoints: `chat.py`, `models.py`, `system.py`, `benchmark.py`, `rag.py`, `plugins.py`, `workspace.py`, `settings.py`; `router.py` mounts all under `/v1/*` |
| `backend/app/engines/` | `base.py` ABC; `fullram/executor.py`; `layerstream/` (executor, layer_executor, loader, splitter, sampler, kv_cache, introspection, quant_config, benchmark, scheduler, prefetch, memory) |
| `backend/app/engines/shared/` | `safetensors.py` (.bin→.safetensors converter, CVE-2025-32434), `turboquant/` (KV-cache compression, **default OFF**, eval gate fails) |
| `backend/app/core/` | `engine_factory.py`, `memory_manager.py`, `hardware_detector.py`, `hardware_llmfit.py`, `task_resolver.py`, `task_router.py` |
| `backend/app/database/` | `manager.py` (DatabaseManager), `connection.py` (ConnectionPool WAL) |
| `backend/app/vectorstore/` | FAISS RAG: `manager.py`, retriever, embedder, chunker |
| `backend/app/plugins/` | `interface.py` (PluginInterface ABC), `manager.py` (importlib load), `sandbox.py` (timeout-only) |
| `backend/app/providers/` | HuggingFace, Local, EnterpriseRepo, USBBundle providers |
| `backend/app/cli/main.py` | typer CLI — `run`, `chat`, `serve`, `pull`, `import`, `benchmark`, `list`, `system` |
| `backend/app/settings/` | `service.py`, `router.py`, `database.py` (SettingsDatabase), `schemas.py`, `defaults.py` |
| `backend/app/security/` | `middleware.py` (Bearer, opt-in), `encryption.py` (Fernet+PBKDF2HMAC) |
| `backend/app/websocket/metrics.py` | `/ws/metrics` 1s metrics broadcast |
| `frontend/` | Next.js 16 + React 19 app (App Router, RSC, static export) |
| `electron/` | Electron 28 wrapper — `main.js`, `preload.js`, `menu.js`, `tray.js` |
| `landing_page/` | Separate marketing site (Next.js 14 + React 18, Tailwind v3) |
| `workspace/` | Runtime data root (models, DBs, offload_cache, sessions, vectors, plugins, logs) |
| `reviews/` | In-project review/eval artifacts (autoplan reports, benchmarks, eval gates) |
| `Info_docs/` | Obsidian wiki (31 pages across project/engines/workflow/algorithms/tech-stack) |

## Development Commands

### Backend (Python 3.10+)

| Action | Command |
|---|---|
| Dev server (hot-reload via `SOVEREIGN_RELOAD=1`) | `python main.py` (from `backend/`) |
| Production server | `cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` |
| One-click launcher (Win) | `launch.bat` |
| One-click launcher (Unix) | `./launch.sh` |
| Run tests (fast, skip real-engine) | `cd backend && python -m pytest -m "not slow"` |
| Run tests (incl. @slow round-trip) | `cd backend && python -m pytest` |
| Run only real-engine round-trip | `cd backend && python -m pytest -m slow` |
| Install deps | `pip install -r backend/requirements.txt` |
| CLI | `./sovereign` (Unix) / `sovereign.bat` (Win), or `cd backend/app && python -m cli.main` |
| Benchmarks (not pytest) | `cd backend && python -m benchmarks.accuracy_eval --smoke` · `python benchmark_layerstream.py` |

**Package manager:** `uv` canonical for backend (`uv.lock` present). Launch scripts use pip+venv (`.venv`) installing from `requirements.txt` as fallback.

### Frontend (Next.js 16 + React 19)

| Action | Command |
|---|---|
| Dev server | `cd frontend && npm run dev` |
| Build (static export → `frontend/out/`) | `cd frontend && npm run build` |
| Lint | `cd frontend && npm run lint` |
| Test | `cd frontend && node --test lib/maskedLm.test.ts` |

**Package manager:** npm (`package-lock.json` present).

### Electron Desktop

| Action | Command |
|---|---|
| Dev | `cd electron && npm start` (or `USE_DEV_SERVER=true npm run start` for live localhost:3000) |
| Build Windows | `cd electron && npm run build:win` (nsis) |
| Build macOS | `cd electron && npm run build:mac` (dmg) |
| Build Linux | `cd electron && npm run build:linux` (AppImage+deb) |

Electron bundles `../backend` → `backend/` and `../frontend/out` → `frontend/` as `extraResources` via electron-builder (appId `com.sovereignai.edge`).

### Landing Page

Separate Next.js 14 app. Same npm scripts as frontend, different `package.json`.

## Code Conventions & Common Patterns

- **Dependency injection:** FastAPI `app.state.*`. `lifespan()` initializes all services and attaches them: `db`, `vector_store`, `hardware_profile`, `model_manager`, `settings_service`, `plugin_manager`, `active_engine`, `active_model`, `active_mode`.
- **Async patterns:** Coroutines for IO-bound engine methods (`load`, `generate`). Async generators for SSE streaming (`generate_stream`, `stream_response`). `asyncio.to_thread` for blocking PyTorch `model.generate()`. `ThreadPoolExecutor` for disk prefetch in LayerStream loader. `asyncio.Lock` for model load serialization.
- **Engine interface:** All engines implement `BaseEngine` ABC (5 abstract methods). Never bypass — `ModelManager` routes all load/unload/generate through the active engine reference.
- **Model loading:** `ModelManager._load_model_locked()` — `_fuzzy_match_model()` resolves display names to base (not split), `split:` prefix handling, disk-full preflight check, mode mismatch resolution (split+fullram redirects to base path).
- **Config:** `pydantic-settings` `BaseSettings` (env prefix `SOVEREIGN_`, reads `.env` if present). All paths relative via `Path(__file__).parent...` for USB portability. `HF_HOME` forced to `workspace/hf_cache`.
- **Database:** Two SQLite DBs (WAL mode, thread-local connections, `synchronous=NORMAL`, `mmap_size=256MB`):
  - `workspace/database/sovereign.db` — models, sessions, documents, hardware_profiles, plugins, benchmark_results, audit_log, schema_version (via `DatabaseManager` + async `ModelRegistry` / aiosqlite).
  - `workspace/database/sovereign_settings.db` — settings (JSON-blob per section), agents, audit_log (via `SettingsDatabase`).
- **Encryption:** `ModelEncryption` — Fernet + PBKDF2HMAC (480k iters), machine-salt from `platform.node()` + `uuid.getnode()`. Chunked encrypted file format (`SOVEREIGN_ENC_v1` header).
- **Auth:** `lan_auth_middleware` Bearer token via `secrets.compare_digest`. **Opt-in only** — enforced when `security.bind_localhost_only=false` AND `api_token` configured. Localhost stays auth-free for Electron/CLI loopback.
- **Plugins:** `PluginInterface` ABC — `async initialize()`, `async cleanup()`, `get_actions()`, `async execute(action, params)`. Dynamically imported via `importlib.util`. `PluginSandbox` = **timeout-only (30s)** — no FS/network/memory isolation on Windows (documented gap in `test_plugin_sandbox.py` docstring).
- **LayerStream internals:** `WeightSplitter` splits to `embed/layer_N/norm/lm_head.safetensors` with quant (`none`/`int8`/`int4`). `LayerWeightLoader` = `ThreadPoolExecutor(prefetch_depth=3)` + LRU byte-budget cache (pinned paths exempt: embed/norm/lm_head). `LayerExecutor.execute_forward(prefill/decode)` — layer-by-layer, dequantize int8/int4 on device, cached attention mask, pre-computed RoPE. `Sampler.sample` — non-destructive Top-K + Top-P + multinomial. Hybrid models (Qwen3.5) → `StatefulCache`; standard → `KVCacheManager` + `HFProxyCache`.
- **Frontend shadcn:** `components.json` (new-york style, lucide icons, `cssVariables=true`). Components in `components/ui/`, `cn()` from `lib/utils.ts`. Tailwind v4 `@theme inline` CSS-variable pattern in `app/globals.css` (oklch tokens, `--brand #3C3489`, `--brand-accent #1D9E75`).
- **State:** Zustand v5.
- **Naming:** Backend `snake_case` modules/classes. Frontend `camelCase` functions, `PascalCase` components. CLI `kebab-case` commands (typer).

## Important Files

| File | Role |
|---|---|
| `backend/main.py` | Server entry — `get_server_config()` reads SQLite settings, `uvicorn.run()` |
| `backend/app/main.py` | FastAPI app + `lifespan()` — DB, vector store, hardware detect, model manager, settings, plugin init |
| `backend/app/config.py` | `Settings(BaseSettings)` — env `SOVEREIGN_`, relative paths, `HF_HOME`, `turboquant_enabled=False` |
| `backend/app/api/router.py` | Mounts 8 subrouters under `/v1` (chat, models, system, benchmark, rag, plugins, workspace, settings) |
| `backend/app/api/chat.py` | `/v1/chat/completions` (OpenAI-compatible), `/execute`, `/mode/switch` — `stream_response()` SSE, `_split_think` |
| `backend/app/engines/base.py` | `BaseEngine` ABC — 5 abstract methods |
| `backend/app/engines/fullram/executor.py` | `FullRAMEngine` — `AutoModelForCausalLM`, `TextIteratorStreamer` thread, GGUF `gguf_file=` kwarg, `ik_llama_cpp`/`llama_cpp` fallback |
| `backend/app/engines/layerstream/executor.py` | `LayerStreamEngine` — `_gen_loop` thread, prefill→decode, rolling-window `_stream_delta` |
| `backend/app/engines/layerstream/loader.py` | `LayerWeightLoader` — ThreadPoolExecutor prefetch, LRU budget cache, int8/int4 dequant |
| `backend/app/engines/layerstream/splitter.py` | `WeightSplitter` — splits model to safetensors + `quant_config.json` |
| `backend/app/core/engine_factory.py` | `EngineFactory.create_engine()` — size compute, `TaskResolver`, `MemoryManager.suggest_mode()` |
| `backend/app/core/task_resolver.py` | `TaskResolver.resolve()` — `AutoConfig` introspection → task_type/is_generative |
| `backend/app/core/memory_manager.py` | `MemoryManager.suggest_mode()` — llmfit scoring + threshold fallback |
| `backend/app/core/hardware_detector.py` | `HardwareDetector.detect()` — CPU, RAM, GPU, disk benchmark |
| `backend/app/services/model_manager.py` | `ModelManager` — `_load_lock`, fuzzy match, split handling, download |
| `backend/app/settings/service.py` | `SettingsService` — per-section CRUD, bcrypt password, system prompt builder |
| `backend/app/settings/database.py` | `SettingsDatabase` — `sovereign_settings.db` (settings/agents/audit_log) |
| `backend/app/cli/main.py` | typer CLI — `chat`, `run`, `serve`, `pull`, `import`, `benchmark` |
| `backend/app/security/encryption.py` | `ModelEncryption` — Fernet+PBKDF2HMAC machine-key |
| `backend/app/security/middleware.py` | `lan_auth_middleware` — opt-in Bearer |
| `frontend/app/globals.css` | Tailwind v4 `@theme inline` entry — CSS vars, dark mode |
| `frontend/components.json` | shadcn/ui config (new-york, lucide, neutral base) |
| `frontend/next.config.ts` | `output='export'` static HTML for Electron |

## Runtime & Tooling Preferences

- **Backend runtime:** Python 3.10+. No Bun/Node for backend.
- **Frontend runtime:** Node 18+. npm only (no yarn/pnpm).
- **Tailwind:** v4 via `@tailwindcss/postcss` (PostCSS plugin). `frontend/tailwind.config.js` is a **legacy v3 leftover** — `app/globals.css` `@theme inline` is the authoritative v4 path. Do not extend the v3 config for new work.
- **Static export:** `next.config.ts` `output='export'`, `images.unoptimized`, `trailingSlash=true` — produces `frontend/out/` consumed by Electron.
- **Electron:** loads `localhost:3000` in dev (`USE_DEV_SERVER=true`), else `app://` custom protocol serving `frontend/out`. Backend spawned as `uvicorn app.main:app` subprocess (non-blocking, boots after window).
- **No Docker / no compose** — 100% local/offline. No `.env.example` (Settings reads `.env` if present, env prefix `SOVEREIGN_`).
- **`config/storage.toml`:** referenced by `app/main.py` + managers but **does NOT exist** — code falls back to `Settings` defaults. Optional.

## Non-Obvious Gotchas (Critical)

### 1. LayerStream is a single engine

`backend/app/engines/layerstream/` holds one `LayerStreamEngine` (`executor.py`). All legacy duplicates (`eviction.py`, `layer_by_layer_inference.py`, `ManualStreamEngine`) were deleted. The routed engine is `executor.py:LayerStreamEngine`.

### 2. Test suite is real (13 files, ~106+ tests)

`backend/tests/` has 13 files covering CLI, SSE, stream batching, think-strip, fuzzy model match, split-auto mode, layerstream loader, turboquant (~60+ tests), OpenAI compat, plugin sandbox. Fast loop: `python -m pytest -m "not slow"` (~25-50s). The sole `@slow` test (`test_layerstream_roundtrip.py`) runs a real synthesized 2-layer Llama offline. No `conftest.py` anywhere — all fixtures inline per-file.

### 3. Engine selection is in `ModelManager`, not in engines

Engine selection happens in `engine_factory.py:EngineFactory.create_engine()`, called by `ModelManager._load_model_locked()`. Engines themselves never decide which mode to use. `mode=auto` triggers `MemoryManager.suggest_mode()`.

### 4. Portability constraint: all paths relative

No absolute paths. All runtime storage lives inside `./workspace/`:
- `workspace/models/` — `.gguf` checkpoints, HF cache, `installed/` (import destination)
- `workspace/database/` — `sovereign.db` (models/sessions/docs) + `sovereign_settings.db` (settings/agents)
- `workspace/offload_cache/` — LayerStream per-layer `.safetensors` chunks
- `workspace/sessions/` — chat snapshots
- `workspace/vectors/` + `workspace/vector_index/` — FAISS index
- `workspace/plugins/` — user Python scripts
- `workspace/logs/` — `server_cli.log`

### 5. proxy.py does NOT exist

The old AGENTS.md referenced a top-level `proxy.py` as a standalone NVIDIA NIM proxy. **That file was deleted.** Only a stale `__pycache__/proxy.cpython-314.pyc` remains.

### 6. PyTorch/transformers is the real engine; llama.cpp is a fallback

FullRAM loads via `transformers.AutoModelForCausalLM` (GGUF via `gguf_file=` kwarg). LayerStream is raw PyTorch + safetensors (layer-by-layer). `llama-cpp-python` / `ik-llama-cpp-python` are fallbacks only, for architectures transformers cannot load.

### 7. Launch scripts vs `backend/main.py` disagree on host/port

`launch.bat` / `launch.sh` **hardcode** `--host 127.0.0.1 --port 8000` when invoking `uvicorn app.main:app`. But `backend/main.py:get_server_config()` reads `sovereign_settings.db` (`security.api_port`, `security.bind_localhost_only`) and can bind `0.0.0.0` if `bind_localhost_only=false`. The launch scripts bypass `backend/main.py` entirely. To honor settings DB, run `python main.py` from `backend/` instead.

### 8. TurboQuant is experimental and default-OFF

`turboquant_enabled` defaults to `False` (`backend/app/config.py`). The eval gate (`benchmarks/accuracy_eval.py`) **FAILS** on Qwen2-0.5B and Pythia-70m at all bit rates — the shipped codebook uses uniform centroids (not Beta Lloyd-Max per the paper), and QJL decode scaling is near-no-op (~0.98x not 6x compression). Do not re-enable without the gate passing. See `reviews/autoplan-report-2026-08-09.md`, `turboquant.md`.

### 9. Old root debug scripts were already cleaned

The old AGENTS.md claimed `debug_*.py` / `test_*.py` / `verify_*.py` / `reproduce_*.py` litter the repo root. **They were deleted.** Only `__pycache__/proxy.cpython-314.pyc` remains. Active benchmark scripts live in `backend/benchmarks/` (not pytest-collected, run via `python -m benchmarks.<name>`).

### 10. `llama-cpp-tq/` is a vendored separate package

`llama-cpp-tq/` is a vendored TurboQuant reference implementation with its **own** pytest suite (~32 files under `tests/` + `refract/tests/` + `benchmarks/`) and independent `pyproject.toml`. **NOT** run by the backend `python -m pytest` command.

### 11. Stale spots in `Info_docs/`

`Info_docs/tech-stack/Vite.md` is stale — the codebase is Next.js 16 (static export), not Vite. The root `readme.md` file-system-layout block lists some root dirs (`models/`, `database/`) that are actually runtime subdirs under `workspace/`.

## Testing & QA

- **Framework:** pytest >=8.0 + pytest-asyncio >=0.23.0 (declared as **runtime** deps, not dev-only). Config in `backend/pyproject.toml`: `asyncio_mode="auto"` (no per-test `@pytest.mark.asyncio` needed), one marker `slow`.
- **No conftest.py** — all fixtures inline per-file. Each test stubs its own collaborators (`_FakeEngine`, `_FakeFactory`, `_AppState`). To add a test, follow the existing fake-engine pattern.
- **Default `python -m pytest` runs `@slow`** — no `addopts` deselects slow. Use `-m "not slow"` for the fast loop.
- **Coverage gaps** (confirmed in `reviews/autoplan-report-2026-08-12.md` and test docstrings): FullRAM engine (zero tests), LayerStream executor (only the single `@slow` synthetic round-trip), plugin sandbox (timeout-only, no FS/network/memory isolation on Windows), RAG (zero), chat e2e (TestClient broken by starlette/httpx incompatibility), `hardware_detector` / `engine_factory` / `settings` / `security` / `websocket` / `providers` untested.
- **Benchmarks** (not pytest, not collected): `benchmarks/accuracy_eval.py` (eval gate), `benchmark_layerstream.py` (real t/s + peak RAM), `benchmarks/layerstream_phase_a.py` (LRU/prefetch), `benchmarks/qjl_ablation.py`, `benchmarks/kv_structure_probe.py`, `benchmarks/reference_polar_probe.py`.

## Key Dependencies

| Layer | Tech | Notes |
|---|---|---|
| Backend | Python 3.10+ | FastAPI 0.109.0, Uvicorn 0.27.0, Pydantic 2.5.3, pydantic-settings 2.1.0 |
| ML | PyTorch 2.5.1, transformers 4.45.2, accelerate 0.34.1, safetensors ≥0.4.0, gguf ≥0.10.0 | FullRAM primary; llama-cpp-python ≥0.3.34 + ik-llama-cpp-python ≥0.1.0 as GGUF fallback |
| ML | sentence-transformers ≥2.2.0, faiss-cpu ≥1.7.4 | RAG embeddings + FAISS vector store |
| Database | aiosqlite 0.19.0 + sqlite3 | Two DBs: `sovereign.db` (DatabaseManager) + `sovereign_settings.db` (SettingsDatabase) |
| Security | cryptography 41.0.7, bcrypt 4.2.0, slowapi 0.1.9 | Fernet encryption, Bearer auth (opt-in), rate limit 60/min |
| CLI | typer 0.9.0, rich 13.7.0, prompt-toolkit 3.0.43 | `sovereign` console script via typer |
| Frontend | Next.js 16, React 19, TypeScript 5 | Static export for Electron, ESLint 9 |
| UI lib | shadcn/ui (new-york), Radix UI, Tailwind v4, Framer Motion 12, Recharts 3 | `@theme inline` CSS vars, oklch tokens |
| State | Zustand 5 | |
| Desktop | Electron 28, electron-builder 24 | nsis (Win), dmg (mac), AppImage+deb (Linux) |
| Landing | Next.js 14, React 18, Tailwind v3 | Separate older stack, independent `package.json` |

## Package Managers

| Workspace | Manager | Lockfile |
|---|---|---|
| Backend (Python) | `uv` (canonical), pip (launcher fallback) | `backend/uv.lock` |
| Frontend | npm | `frontend/package-lock.json` |
| Electron | npm | `electron/package-lock.json` |
| Landing page | npm | `landing_page/package-lock.json` |
