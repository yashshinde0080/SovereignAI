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
    → llama.cpp Python bindings (via transformers)
    → File I/O: ./models/*.gguf, ./database/*.db
```

### Key files:

- **Entry point:** `backend/main.py` — reads settings from SQLite, calls `uvicorn.run()`
- **FastAPI app:** `backend/app/main.py` — lifespan setup: DB, vector store, hardware detect, model manager, plugin manager
- **API routes:** `backend/app/api/router.py` — mounts chat, models, system, benchmark, RAG, plugins, settings routers under `/v1/*`
- **Engine ABC:** `backend/app/engines/base.py` — `BaseEngine` with `load()`, `unload()`, `generate()`, `generate_stream()`, `get_memory_usage()`
- **LayerStream engine:** `backend/app/engines/layerstream/` — 15 files, includes 3 nearly-duplicate engine implementations (major gotcha, see below)
- **FullRAM engine:** `backend/app/engines/fullram/` — executor, kv_cache, loader
- **CLI:** `backend/app/cli/main.py`

### Data flow:

1. `app/main.py:lifespan()` runs at startup — inits DB, vector store, hardware profiler, model manager, settings, plugin manager
2. On model load: `ModelManager.load_model()` → engine router selects FullRAM or LayerStream based on `HardwareDetector` output vs model size
3. Chat requests hit `/v1/chat/*` → `app/api/chat.py` → active engine's `generate()` or `generate_stream()`
4. Settings are stored in SQLite DB (`database/sovereign_settings.db`), read via `SettingsService.get_general()` including `startup_model` and `default_mode`

---

## Non-Obvious Gotchas (Critical)

### 1. LayerStream has 3 duplicate engines — only 1 is active

- `executor.py` (309 lines) — the main `LayerStreamEngine`
- `eviction.py` (267 lines) — SECOND engine, apparently unused/tested
- `layer_by_layer_inference.py` (245-428) — THIRD partial engine, `LayerByLayerEngine`

The ponytail review (in `issue.md`) flags this as a major over-engineering problem. If you're fixing bugs in LayerStream, confirm which engine is actually registered/routed to. The others may have drifted out of sync.

### 2. `backend/tests/test_dummy.py` is the only test file — empty test suite

`test_dummy.py` contains `def test_dummy(): pass`. There is no real test coverage. If you're asked to run tests, `pytest` passes instantly because it tests nothing. Do not assume tests exercise real code.

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

### 6. The engine stack bypasses llama.cpp for Python

The TRD specifies "llama.cpp Python bindings" as the underlying tensor engine, but the LayerStream engine works with raw PyTorch + safetensors (layer-by-layer loading). `backend/app/engines/fullram/loader.py` has a hand-rolled GGUF parser (`GGUFLoader`, flagged as replacing with `transformers.AutoModel`). If you're adding GGUF support to LayerStream, check whether `llama.cpp` is actually wired or just specified.

### 7. Frontend uses Tailwind v4 with shadcn/ui

`frontend/package.json` uses `tailwindcss` v4 and `@tailwindcss/postcss` v4. The shadcn components config is in `frontend/components.json`. Theme setup likely follows the `@theme inline` pattern from Tailwind v4.

### 8. Old debug/test scripts litter the repo root and `backend/`

Files like `debug_*.py`, `test_*.py`, `verify_*.py`, `reproduce_*.py`, `dl_err.txt`, `log.txt` are historical artifacts. They test specific model loading, layer execution, and API calls against real models. Some may be useful for reproduction, but many are stale.

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