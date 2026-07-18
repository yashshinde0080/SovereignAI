# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

SovereignAI Edge is a portable offline AI compute platform with dual inference engines (FullRAM/LayerStream), a FastAPI backend, Next.js frontend, and Electron desktop wrapper. It supports GGUF model inference with automatic hardware detection and engine selection.

## Project Structure

```
SovereignAI/
├── backend/           # FastAPI Python backend
│   └── app/
│       ├── api/          # REST API routes
│       ├── core/         # Hardware detection, scheduler
│       ├── database/     # SQLite models and migrations
│       ├── engines/      # FullRAM & LayerStream inference engines
│       ├── plugins/      # Plugin system (interface, manager, sandbox)
│       ├── providers/    # Model providers (local, USB, enterprise)
│       ├── schemas/      # Pydantic models
│       ├── services/     # Model management, download, quantization
│       ├── vectorstore/  # RAG vector store (FAISS)
│       ├── websocket/    # Real-time metrics streaming
│       └── cli/          # CLI commands (Typer + Rich)
├── frontend/          # Next.js 16 + React 19 + Tailwind v4
├── electron/          # Electron desktop wrapper
│   ├── main.js        # Electron main process
│   ├── preload.js     # Security preload script
│   ├── menu.js        # Application menu
│   └── tray.js        # System tray
└── Info_docs/         # Obsidian documentation vault
```

## Key Architecture Patterns

### Dual Inference Engine System

Two engines selected automatically based on hardware:

- **FullRAM** (`backend/app/engines/fullram/`): Loads all model weights into RAM for fast inference. Used when sufficient RAM is available.
- **LayerStream** (`backend/app/engines/layerstream/`): Layer-by-layer inference with disk swapping for low-memory systems. Implements layer eviction/prefetch scheduling, mmap-based loading, and KV cache management.

Engine selection in `HardwareDetector.detect()` based on:
- `ram_total_gb` vs `model_size_gb`
- `gpu_vram_gb` for GPU offloading
- Disk speed (SSD required for LayerStream)
- CPU features (AVX2, AVX512)

### Plugin System

Browser-based sandboxed execution (`backend/app/plugins/sandbox.py`). Plugins implement `PluginInterface`:
- `initialize()` / `cleanup()` lifecycle
- `get_actions()` to expose capabilities
- `execute(action, params)` for runtime execution

Built-in plugins in `backend/app/plugins/builtin/`:
- `pdf_ingestion.py` - PDF text extraction
- `code_analyzer.py` - Code analysis utilities

### RAG / Vector Store

FAISS-based vector search (`backend/app/vectorstore/`):
- `chunker.py` - Text chunking
- `embedding_pipeline.py` - Sentence-transformers embedding
- `store.py` - FAISS index management
- `retriever.py` - Similarity search

### Model Providers

Provider pattern (`backend/app/providers/`):
- `base.py` - Abstract provider interface
- `local.py` - Local filesystem models
- `enterprise_repo.py` - Enterprise model repository
- `usb_bundle.py` - USB bundle provider
- `registry.py` - Provider registry

## Development Commands

### Backend

```bash
cd backend

# Activate virtual environment
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# CLI commands
python -m app.cli.main <command>

# Run tests
pytest

# Install dependencies
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend

# Development
pnpm dev
# or npm run dev

# Build
pnpm build

# Lint
pnpm lint
```

### Electron

```bash
cd electron

# Development
npm start

# Build distribution
npm run build:win  # or build:mac, build:linux
```

### Sovereign CLI Commands

```bash
sovereign system         # Show hardware profile
sovereign list           # List installed models
sovereign pull <model>   # Download model
sovereign run <model>    # Load model and chat
sovereign benchmark      # Run inference benchmark
sovereign remove <model> # Remove model
sovereign serve          # Start API server
```

## API Endpoints (v1 prefix)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/models/pull` | POST | Download model |
| `/v1/models/load` | POST | Load model |
| `/v1/models/` | GET | List models |
| `/v1/models/{name}` | DELETE | Remove model |
| `/v1/chat/completions` | POST | Chat completions |
| `/v1/upload` | POST | Upload document |
| `/v1/query` | POST | Query documents |
| `/v1/documents` | GET | List documents |
| `/v1/system/hardware` | GET | Hardware profile |
| `/v1/system/status` | GET | Runtime status |
| `/v1/benchmark/run` | POST | Run benchmark |
| `/metrics` | WS | Real-time metrics |

## Critical Files

**Entry Points:**
- `backend/app/main.py` - FastAPI app with lifespan management
- `backend/app/cli/main.py` - CLI (Typer)
- `electron/main.js` - Electron main process

**Core:**
- `backend/app/core/hardware_detector.py` - Hardware detection
- `backend/app/core/scheduler.py` - Inference task scheduler
- `backend/app/engines/base.py` - Base engine interface

**Engines:**
- `backend/app/engines/fullram/` - Full RAM inference
- `backend/app/engines/layerstream/` - Layer-by-layer streaming

**Database:**
- `backend/app/database/models.py` - SQLAlchemy models
- `backend/app/config/storage.toml` - Storage configuration

## Tech Stack

**Backend:** FastAPI, Pydantic 2, aiosqlite, Transformers, Torch, FAISS, sentence-transformers, Rich, Typer

**Frontend:** Next.js 16, React 19, Tailwind CSS v4, shadcn/ui, Zustand, framer-motion

**Electron:** Electron 28, electron-builder