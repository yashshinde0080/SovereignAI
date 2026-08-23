# Architecture Overview

SovereignAI Edge is a portable, 100% offline AI platform that runs LLMs locally on consumer hardware or USB drives. Two inference engines back a unified FastAPI gateway.

## High-Level Data Flow

```
Client (React / Electron / CLI)
  → REST / WebSocket (127.0.0.1:8000)
  → FastAPI Gateway (/v1/*)
      → Chat: system prompt + RAG context → apply_chat_template
            → engine.generate() or stream_response() SSE
      → Model load: ModelManager.load_model()
            → EngineFactory.create_engine()
                → TaskResolver.resolve() (AutoConfig introspection)
                → MemoryManager.suggest_mode() (llmfit scoring > threshold)
            → FullRAMEngine or LayerStreamEngine
  → PyTorch + transformers (FullRAM)
    / raw PyTorch layer-by-layer (LayerStream)
      llama-cpp-python only as GGUF fallback
  → File I/O: ./workspace/{models,database,offload_cache,...}
```

## Server Startup Sequence

1. `backend/main.py` → `get_server_config()` reads `sovereign_settings.db` for host/port → `uvicorn.run()`
2. `backend/app/main.py:lifespan()` startup:
   - `_configure_logging()` — level via `SOVEREIGN_LOG_LEVEL`
   - `_patch_gguf_quant_types()` — adds IQ2_BN (135) enum for newer BitNet models
   - `DatabaseManager()` → `initialize()` → runs migrations, checks integrity
   - `VectorStoreManager()` → `initialize()` — loads existing FAISS index or creates new
   - `detect_hardware()` — CPU, RAM, GPU, disk benchmark → `app.state.hardware_profile`
   - `ModelManager()` → `initialize(app)` → loads custom catalogs, starts background `scan_installed()` task
   - `SettingsService()` — per-section CRUD from `sovereign_settings.db`
   - Load startup model from `general.startup_model` + `general.default_mode`
   - `PluginManager()` → `load_plugins()` — imports from `workspace/plugins/`
   - Sets `app.state.active_engine = None` (filled by model load)
3. Shutdown: unload engine, cleanup provider, close DB + vector store.

## Key Directories

| Path | Purpose |
|---|---|
| `backend/app/main.py` | FastAPI app + `lifespan()` |
| `backend/main.py` | Server entry — reads host/port from settings DB |
| `backend/app/api/` | REST endpoints under `/v1/*` |
| `backend/app/engines/` | Inference engines (FullRAM + LayerStream) |
| `backend/app/core/` | Engine factory, memory manager, task resolver |
| `backend/app/services/` | Model manager, model registry |
| `backend/app/database/` | `DatabaseManager`, `ConnectionPool` (WAL) |
| `backend/app/settings/` | Settings service, settings DB, schemas |
| `backend/app/vectorstore/` | FAISS RAG: chunker, embedder, retriever |
| `backend/app/security/` | Bearer auth middleware, Fernet encryption |
| `backend/app/websocket/` | `/ws/metrics` — 1s metrics broadcast |
| `backend/app/plugins/` | PluginInterface ABC, importlib loader |
| `backend/app/providers/` | HuggingFace, Local, EnterpriseRepo providers |
| `frontend/` | Next.js 16 + React 19 (static export) |
| `electron/` | Electron 28 desktop wrapper |
| `workspace/` | Runtime data root (models, DBs, cache, etc.) |

## Two SQLite Databases

| Database | Path | Managed by | Purpose |
|---|---|---|---|
| `sovereign.db` | `workspace/database/sovereign.db` | `DatabaseManager` | Models, sessions, documents, hardware_profiles, plugins, benchmark_results, audit_log |
| `sovereign_settings.db` | `workspace/database/sovereign_settings.db` | `SettingsDatabase` | Settings (JSON per section), agents, audit_log |

See [[01-database-system]] for details.

## Config System

`backend/app/config.py` — `Settings(BaseSettings)` with env prefix `SOVEREIGN_`. All paths relative via `Path(__file__).parent...` for USB portability. `HF_HOME` forced to `workspace/hf_cache`.

## Dependency Injection Pattern

FastAPI `app.state.*` — `lifespan()` initializes all services and attaches them. Every API endpoint reads from `request.app.state`.

```python
app.state.db                  # DatabaseManager
app.state.vector_store        # VectorStoreManager
app.state.hardware_profile    # dict from HardwareDetector
app.state.model_manager       # ModelManager
app.state.settings_service    # SettingsService
app.state.plugin_manager      # PluginManager
app.state.active_engine       # FullRAMEngine | LayerStreamEngine | None
app.state.active_model        # str | None (model_id)
app.state.active_mode         # "fullram" | "layerstream" | None
```

## Related

- [[02-chat-api-flow]] — Chat request handling and streaming
- [[03-model-loading]] — How models are loaded into engines
- [[04-engine-system]] — FullRAM and LayerStream engine internals
- [[05-layer-by-layer]] — LayerStream's layer-by-layer execution
- [[12-task-resolution]] — How models are classified by task type
- [[11-hardware-memory]] — Memory management and mode selection
