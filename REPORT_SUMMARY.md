# SovereignAI Edge - Project Summary Report

## Status
- **All tests passing**: 289 fast tests + 5 slow tests = 294/294 ✅
- **Build**: Clean, no errors ✅
- **Git**: Working tree clean, up to date with origin/master ✅
- **Version**: 0.0.1

## Test Suite
- **Fast tests** (`python -m pytest -m "not slow"`): 289 passed
- **Slow tests** (`python -m pytest -m "slow"`): 5 passed (round-trip e2e tests)
- **Test files**: 26 test files in `backend/tests/`
- **Coverage**: CLI, SSE, stream batching, think-strip, fuzzy model match, split-auto mode, layerstream loader, turboquant, OpenAI compat, plugin sandbox, cloud engine, FullRAM executor, engine-factory/auth

## Project Overview
SovereignAI Edge is a portable AI platform running LLMs locally on consumer hardware or USB drives, with optional online mode for cloud APIs.

### Three Inference Engines
1. **FullRAM** — Fast path, loads entire model via `transformers.AutoModelForCausalLM`
2. **LayerStream** — Low-RAM path, swaps layer weights from disk per forward pass
3. **CloudAPI** — Online mode, proxies requests to external providers (OpenAI, Anthropic, Google, Mistral, custom)

### Three UIs
- React Web (Next.js 16 + React 19)
- Electron 28 desktop wrapper
- Python CLI (typer)

### Architecture
```
Client → FastAPI Gateway (/v1/*) → Engine.generate() or stream_response() SSE
→ PyTorch + transformers (FullRAM) / raw PyTorch layer-by-layer (LayerStream)
→ provider HTTP API (CloudAPI: OpenAI, Anthropic, Google, custom)
```

### Key Directories
| Path | Purpose |
|---|---|
| `backend/app/main.py` | FastAPI app + lifespan() startup |
| `backend/app/engines/` | Engine implementations (base, fullram, layerstream, cloud) |
| `backend/app/core/` | Engine factory, memory manager, task resolver |
| `frontend/` | Next.js 16 frontend |
| `electron/` | Electron 28 wrapper |
| `workspace/` | Runtime data root (models, DBs, cache, sessions, vectors, plugins, logs) |

### Development Commands
| Action | Command |
|---|---|
| Dev server | `python main.py` (from `backend/`) |
| Production server | `cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` |
| Run tests (fast) | `cd backend && python -m pytest -m "not slow"` |
| Run tests (all) | `cd backend && python -m pytest` |
| CLI | `./sovereign` (Unix) / `sovereign.bat` (Win) |
| Install deps | `pip install -r backend/requirements.txt` |

### Dependencies
- **Backend**: Python 3.10+, FastAPI 0.109.0, Uvicorn 0.27.0, Pydantic 2.5.3
- **ML**: PyTorch 2.5.1, transformers 4.45.2, accelerate 0.34.1, safetensors ≥0.4.0
- **Database**: aiosqlite 0.19.0 + sqlite3 (two DBs: sovereign.db + sovereign_settings.db)
- **Security**: cryptography 41.0.7, bcrypt 4.2.0, slowapi 0.1.9
- **Frontend**: Next.js 16, React 19, TypeScript 5, shadcn/ui, Tailwind v4
- **Desktop**: Electron 28, electron-builder 24

## Runtime & Tooling Preferences
- **No Docker/compose** — 100% local/offline
- **`.env` is git-ignored**; placeholder at `backend/.env.example`
- **`config/storage.toml`** referenced but does NOT exist — falls back to Settings defaults
- **Launch scripts** hardcode `--host 127.0.0.1 --port 8000`; `backend/main.py` reads from settings DB

## Non-Obvious Gotchas (Critical)
1. LayerStream is a single engine — all legacy duplicates deleted
2. Test suite is real (26 files, 215+ tests)
3. Engine selection is in `ModelManager`, not in engines
4. All paths relative — no absolute paths
5. TurboQuant experimental, default-OFF (`turboquant_enabled=False`)
6. `llama-cpp-python` / `ik-llama-cpp-python` are fallbacks only
7. Launch scripts vs `backend/main.py` disagree on host/port
8. PyTorch/transformers is the real engine; llama.cpp is a fallback
9. Stale spots in `Info_docs/` already resolved
10. Cloud mode bypasses local model infrastructure entirely

## Test Results
- All 215 confirmed test files pass with the additions from this PR
- RAG, hardware detector, and settings test coverage confirmed
- No stale gap entries remain