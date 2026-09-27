---
tags:
  - trd
  - technical
  - requirements
  - stack
source: "[[Docs/trd.md]]"
created: 2026-07-21
updated: 2026-09-27
---

# TRD

The SovereignAI Edge platform is architected as a zero-configuration, dependency-free execution environment with dynamic hardware detection, efficient memory management, and cross-platform consistency. The backend uses Python 3.10+ bundled as a standalone executable (via PyInstaller) to avoid host OS dependencies, with FastAPI serving REST and WebSocket APIs, Llama.cpp Python bindings for GGML/GGUF tensor operations, Pydantic for strictly typed configurations, and SQLite for local persistence. The frontend uses Next.js 16 with React 19, TypeScript, Zustand for state management, Tailwind CSS v4 for responsive styling, and static export for Electron bundling. The Electron shell wraps the entire application, managing the lifecycle of the embedded Python backend binary.

Minimum system requirements for LayerStream mode include a 4-core CPU, 8GB DDR4 RAM, an NVMe SSD (highly recommended), and integrated graphics -- allowing 3-8B Q4 parameter models with 10GB free space. Recommended specifications for FullRAM mode are an 8-core+ CPU, 16-32GB DDR5 RAM, NVMe SSD, and a dedicated GPU with at least 8GB VRAM (NVIDIA RTX series or Apple Silicon Unified Memory).

Portability is fundamental to the design: since the application runs off external drives, absolute paths cannot be used. All operations rely on relative paths resolved dynamically at runtime, with a standard layout of `./workspace/models/` for GGUF weight files, `./workspace/database/` for SQLite data and user configs, `./workspace/plugins/` for user-added Python scripts, and `./backend/` and `./frontend/out/` for application binaries.

## Key Points

- Python 3.10+ backend bundled as standalone executable (no host Python required)
- FastAPI gateway with Uvicorn server and Pydantic model validation
- Next.js 16 + React 19 + Tailwind CSS v4 frontend with Zustand state management (static export)
- Electron 28 wrapper manages Python backend lifecycle (start/stop), bundles `backend/` and `frontend/out/`
- Llama.cpp bindings for low-level GGML/GGUF tensor operations (fallback only; primary is transformers)
- All paths are relative for USB portability; no absolute paths used
- Minimum 8GB RAM (LayerStream), recommended 16-32GB RAM (FullRAM)
- Three inference engines: FullRAM, LayerStream, CloudAPI (online mode)
- Dual SQLite DBs: `sovereign.db` + `sovereign_settings.db` (WAL mode)
- Encrypted API key storage (Fernet + PBKDF2HMAC) for cloud providers

## Related
- [[PRD]] — Product vision and feature list
- [[Technical Architecture]] — System layers and deployment
- [[Engines Overview]] — FullRAM vs LayerStream deep-dive
- [[Gaps]] — Research gaps in memory-constrained inference