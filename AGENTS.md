# SovereignAI Edge — Agent Guide

## Project Overview

SovereignAI Edge is a **portable, 100% offline AI platform** that runs LLMs locally on consumer hardware (or USB drives). Two inference engines — **FullRAM** (fast, high-RAM) and **LayerStream** (low-RAM, layers swapped from disk). Three user interfaces: React Web UI, Electron desktop app, Python CLI.

---

## Essential Commands

### Backend (Python 3.10+, FastAPI + Uvicorn)

| Action | Command |
|---|---|
| Dev server (hot-reload) | `python main.py` (from `backend/`) |
| Production server | `cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` |
| Run all tests | `cd backend && python -m pytest` |
| Install deps | `pip install -r backend/requirements.txt` |
| Package manager | `uv` (lock file `uv.lock` present), but `pyproject.toml` uses hatchling |

**Important:** The top-level `launch.bat` / `launch.sh` scripts handle venv creation, deps, and server startup. They set `host=127.0.0.1` by default (read from SQLite settings DB at `workspace/database/sovereign_settings.db` section `security` key `api_port` / `bind_localhost_only`).

### Frontend (Next.js 16 + React 19)

| Action | Command |
|---|---|
| Dev server | `cd frontend && npm run dev` |
| Build | `cd frontend && npm run build` |
| Lint | `cd frontend && npm run lint` |

### Electron Desktop

| Action | Command |
|---|---|
| Dev | `cd electron && npm start` |
| Build | `cd electron && npm run build` (platform-specific: `build:win`, `build:mac`, `build:linux`) |

Electron bundles the backend (`../backend`) and frontend build output (`../frontend/out`) as extra resources.

### Landing Page (separate Next.js app in `landing_page/`)

Same npm scripts as frontend, different package.json.

---

## Architecture & Control Flow

```
User (React/Electron/CLI)
    → REST/WebSocket (localhost:8000)
    → FastAPI Gateway (/v1/*)
        → Engine Router → Hardware Profiler → Auto-select FullRAM or LayerStream
    → PyTorch + transformers (FullRAM) / PyTorch layer-by-layer (LayerStream);
      llama-cpp-python only as a GGUF fallback for unsupported architectures
    → File I/O: ./workspace/models/*.gguf, ./workspace/database/*.db
```

### Key files:

- **Entry point:** `backend/main.py` — reads settings from SQLite, calls `uvicorn.run()`
- **FastAPI app:** `backend/app/main.py` — lifespan setup: DB, vector store, hardware detect, model manager, plugin manager
- **API routes:** `backend/app/api/router.py` — mounts chat, models, system, benchmark, RAG, plugins, settings routers under `/v1/*`
- **Engine ABC:** `backend/app/engines/base.py` — `BaseEngine` with `load()`, `unload()`, `generate()`, `generate_stream()`, `get_memory_usage()`
- **LayerStream engine:** `backend/app/engines/layerstream/` — single `LayerStreamEngine` (duplicate engines deleted 08-05)
- **FullRAM engine:** `backend/app/engines/fullram/` — executor (hand-rolled GGUF parser removed)
- **CLI:** `backend/app/cli/main.py`

### Data flow:

1. `app/main.py:lifespan()` runs at startup — inits DB, vector store, hardware profiler, model manager, settings, plugin manager
2. On model load: `ModelManager.load_model()` → engine router selects FullRAM or LayerStream based on `HardwareDetector` output vs model size
3. Chat requests hit `/v1/chat/*` → `app/api/chat.py` → active engine's `generate()` or `generate_stream()`
4. Settings are stored in SQLite DB (`database/sovereign_settings.db`), read via `SettingsService.get_general()` including `startup_model` and `default_mode`

---

## Non-Obvious Gotchas (Critical)

### 1. LayerStream is a single engine now

`backend/app/engines/layerstream/` holds one `LayerStreamEngine` (executor + layer_executor + loader + splitter + prefetch). The duplicate engines (`eviction.py`, `layer_by_layer_inference.py`) and `ManualStreamEngine` were deleted. If you're fixing bugs in LayerStream, the routed engine is `executor.py:LayerStreamEngine`.

### 2. Real test suite (106 tests, not empty)

`backend/tests/` has 10 files covering CLI, SSE, stream batching, think-strip, fuzzy model match, split-auto mode, layerstream loader, turboquant. `pytest` takes ~25-50s. Coverage gaps remain: LayerStream executor, FullRAM fallback, plugin sandbox, RAG, chat e2e — see `reviews/autoplan-report-2026-08-12.md`.

### 3. Engine selection is in `ModelManager`, not in the engines themselves

Engine selection happens in `backend/app/services/model_manager.py:load_model()` via `EngineFactory` (`backend/app/core/engine_factory.py`). Hardware profiling is in `backend/app/core/hardware_detector.py`. The engines themselves don't decide which mode to use.

### 4. Portability constraint: all paths are relative

No absolute paths anywhere. The app runs from USB drives. All runtime storage lives strictly inside `./workspace/`:
- `./workspace/models/` — `.gguf` checkpoints + HF cache
- `./workspace/database/` — SQLite DB files (sovereign.db, sovereign_settings.db)
- `./workspace/data/` — vector index, misc data
- `./workspace/offload_cache/` — LayerStream layer caches
- `./workspace/sessions/` — sessions, snapshots
- `./workspace/plugins/` — user Python scripts (+ `workspace/plugins/user/models` catalog)

### 5. proxy.py is a separate NVIDIA proxy server

Top-level `proxy.py` is NOT the app proxy — it's a standalone FastAPI server that translates Anthropic API format to NVIDIA NIM API (`nvapi-...` key hardcoded). It runs independently on its own port, not part of the main app.

### 6. PyTorch/transformers is the real tensor engine; llama.cpp is a fallback

The FullRAM engine loads via `transformers.AutoModelForCausalLM` (GGUF files via the `gguf_file` kwarg); the LayerStream engine is raw PyTorch + safetensors (layer-by-layer). `llama-cpp-python` / `ik-llama-cpp-python` are only used as a fallback for architectures transformers can't load (e.g. BitNet IQ2_BN GGUF files).

### 7. Frontend uses Tailwind v4 with shadcn/ui

`frontend/package.json` uses `tailwindcss` v4 and `@tailwindcss/postcss` v4. The shadcn components config is in `frontend/components.json`. Theme setup likely follows the `@theme inline` pattern from Tailwind v4.

### 8. Old debug/test scripts litter the repo root and `backend/`

Files like `debug_*.py`, `test_*.py`, `verify_*.py`, `reproduce_*.py`, `dl_err.txt`, `log.txt` are historical artifacts. They test specific model loading, layer execution, and API calls against real models. Some may be useful for reproduction, but many are stale.

### 9. LayerStream is experimental; the I/O fix list is parked with triggers

Measured 08-14/08-15: LayerStream is 0.40 tok/s, compute is 98% of wall time,
and disk I/O (~9%) is already overlapped behind compute — so the I/O fix list
(quantize splits, deeper prefetch, GDS/io_uring, LLM-in-a-Flash, etc.) is
parked, not wrong. Each item has an explicit, checkable revisit trigger:
`reviews/parked-io-fixes-2026-08-16.md`. FullRAM is the default for fitting
models (honest ~4x-Q4-file residency check in `MemoryManager.suggest_mode`);
llama.cpp is the validated beyond-RAM path (24 tok/s on the dev box, see
`reviews/spike-llamacpp-offload-2026-08-16.md`). Don't tune the prefetch
window or add I/O machinery until a benchmark shows disk read > 30% of wall.

---

## Code Organization

```
SovereignAI/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app + lifespan
│   │   ├── config.py               # Settings (pydantic-settings)
│   │   ├── api/                    # REST endpoints
│   │   │   ├── router.py           # Route registration
│   │   │   ├── chat.py, models.py, system.py, rag.py, plugins.py, benchmark.py
│   │   ├── engines/                # Inference engines
│   │   │   ├── base.py             # BaseEngine ABC
│   │   │   ├── fullram/            # FullRAM engine
│   │   │   ├── layerstream/        # LayerStream engine (15 files, duplicate issue)
│   │   │   └── shared/             # Shared engine utilities
│   │   ├── core/                   # System-level services
│   │   │   ├── hardware_detector.py
│   │   │   └── task_router.py      # 44-entry task map (mostly speculative)
│   │   ├── database/               # SQLite connection + manager
│   │   ├── vectorstore/            # FAISS-based RAG
│   │   ├── plugins/                # Plugin system (interface, manager, sandbox)
│   │   ├── providers/              # Model providers (HF, local, enterprise repo, USB)
│   │   ├── cli/                    # CLI app (typer-based)
│   │   ├── settings/               # Settings service + router
│   │   ├── services/               # Service layer
│   │   ├── schemas/                # Pydantic models
│   │   ├── security/               # Auth/encryption
│   │   ├── websocket/              # WebSocket metrics endpoint
│   │   └── utils/                  # Helpers
│   ├── main.py                     # Server entry point (reads SQLite config)
│   ├── requirements.txt            # pip deps
│   └── pyproject.toml              # Project metadata (hatchling)
├── frontend/                       # Next.js 16 app (React 19)
│   ├── app/                        # App router pages
│   ├── components/                 # React components (shadcn/ui)
│   ├── hooks/                      # React hooks (probably Zustand stores)
│   ├── lib/                        # Utility functions
│   └── store/                      # Zustand state stores
├── electron/                       # Electron wrapper
│   ├── main.js                     # Main process
│   ├── preload.js                  # Preload script
│   ├── menu.js                     # App menu
│   └── tray.js                     # System tray
├── landing_page/                   # Separate marketing site (also Next.js)
├── database/                       # SQLite DB files
├── plugins/                        # User plugin scripts
├── models/                         # .gguf model files
├── workspace/                      # Runtime data (sessions, documents, logs)
├── launch.bat / launch.sh          # One-click launcher
└── proxy.py                        # NVIDIA NIM proxy (NOT the app)
```

---

## Key Dependencies

| Layer | Tech | Notes |
|---|---|---|
| Backend | Python 3.10+ | FastAPI, Uvicorn, Pydantic |
| ML | PyTorch 2.5.1, Transformers (bleeding edge, git+https), safetensors | transformers pinned to git head |
| ML | accelerate, sentence-transformers, faiss-cpu | For RAG and model loading |
| Database | aiosqlite + sqlite3 | Custom `DatabaseManager` (7 table classes) |
| Vector store | FAISS | Via `VectorStoreManager` |
| Frontend | Next.js 16, React 19, TypeScript 5 | PostCSS, ESLint 9 |
| UI lib | shadcn/ui, Radix UI, Tailwind v4, Framer Motion, Recharts | |
| State | Zustand v5 | |
| Desktop | Electron 28 | electron-builder for packaging |
| CLI | typer, rich, prompt-toolkit | Python terminal UI |

---

## Patterns & Conventions

- **Backend:** FastAPI dependency injection via `app.state.*`. Lifespan handler initializes all services and attaches them to `app.state`.
- **Engine interface:** All engines implement `BaseEngine` ABC (6 methods). Engines are async (coroutines + async generators for streaming).
- **Plugin system:** Python builtins import, sandboxed execution. Plugins implement a defined interface.
- **Database:** Custom ORM-like layer with `DatabaseManager` + typed table classes (`ModelsTable`, `SessionsTable`, etc.). Over-abstracted per `issue.md`.
- **Config:** TOML for storage config (`config/storage.toml`), SQLite for settings, Pydantic settings for app config.
- **Frontend shadcn:** Standard pattern — `components.json` at root, components in `components/ui/`, use `cn()` from `lib/utils.ts`.