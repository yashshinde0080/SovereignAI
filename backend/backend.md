# SovereignAI Edge - Backend

This directory contains the backend services for SovereignAI Edge, a portable AI platform for running large language models locally on consumer hardware.

## Overview

- **FastAPI Gateway**: Provides OpenAI-compatible REST and WebSocket APIs at `/v1/*`
- **Three Inference Engines**:
  - **FullRAM**: Loads entire model into RAM/VRAM via Hugging Face Transformers (primary path)
  - **LayerStream**: Streams model layers from disk for low-RAM inference
  - **CloudAPI**: Proxies to external providers (OpenAI, Anthropic, Google, etc.) with encrypted API key storage
- **Features**:
  - Retrieval-Augmented Generation (RAG) via FAISS vector store
  - Plugin system for extensibility
  - Settings management with encrypted storage
  - Hardware profiling and automatic engine selection
  - WebSocket metrics streaming
  - CLI and UI integration points

## Key Directories

- `app/main.py`: FastAPI app with lifespan initialization
- `app/api/`: REST endpoint modules (chat, models, system, etc.)
- `app/engines/`: Engine implementations (FullRAM, LayerStream, CloudAPI)
- `app/core/`: Engine factory, memory manager, task resolver, hardware detector
- `app/database/`: SQLite database managers (WAL mode)
- `app/vectorstore/`: FAISS-based RAG implementation
- `app/plugins/`: Plugin interface and manager
- `app/settings/`: Settings service and encryption
- `app/security/`: Auth middleware and encryption utilities
- `cli/`: Typer-based command line interface
- `workspace/`: Runtime data (models, databases, cache, logs, etc.) - relative paths only

## Development

- Python 3.10+
- Dependencies managed via `uv` (see `backend/uv.lock`)
- Run dev server: `python main.py` (from backend/ directory)
- Run tests: `python -m pytest -m "not slow"` (fast suite)
- See `AGENTS.md` for full architecture and conventions.