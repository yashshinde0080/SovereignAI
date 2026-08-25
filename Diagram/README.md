# SovereignAI Edge - Architecture Diagrams

This folder contains Mermaid diagrams documenting the complete system architecture of SovereignAI Edge.

## Diagrams

### 1. `system-architecture.mmd` - Complete System Architecture
**Cloud-style architecture diagram** showing all components, layers, and connections in a single comprehensive view.

**Layers depicted:**
- **External Access Layer** - Users and three client applications (Web, Electron, CLI)
- **Network & Security Edge** - Localhost default + LAN opt-in with Bearer auth + Fernet encryption
- **API Gateway** - FastAPI with 7 sub-routers, middleware stack, WebSocket metrics
- **Core Services** - Lifespan initialization + runtime services (ModelManager, Settings, Hardware, VectorStore, Plugins, Databases)
- **Engine Factory & Selection** - Mode selection pipeline (TaskResolver → MemoryManager/llmfit → Threshold Fallback)
- **Inference Engines** - BaseEngine ABC with FullRAM (transformers primary + GGUF fallback) and LayerStream (layer-by-layer streaming)
- **ML Stack** - Transformers/PyTorch primary, GGUF fallback, RAG stack
- **Data & Storage** - All `./workspace/` subdirectories (two SQLite DBs, model files, vector index, runtime files)
- **Model Providers** - HuggingFace, Local, Enterprise, USB Bundle
- **Build & Bundle** - Frontend static export, Electron extraResources, launch scripts discrepancy
- **Landing Page** - Separate Next.js 14 app

### 2. `user-request-flow.mmd` - User Request Flow (Sequence Diagram)
**Sequence diagram** showing the complete chat request lifecycle with three flows:

1. **Chat Request Flow** - From user input through middleware, prompt building (system + RAG), engine selection/loading, generation (streaming vs non-streaming), SSE response
2. **Mode Switch Flow** - POST `/v1/chat/mode/switch` triggering engine unload/reload with re-evaluation
3. **Benchmark Flow** - POST `/v1/system/benchmark` running prompts through engine, measuring metrics, storing results

### 3. `data-flow-storage.mmd` - Data Flow & Storage Architecture
**Data flow diagram** showing ingestion → processing → storage → output with all storage components:

- **Input Sources** - User input, model downloads, document uploads, plugin installs
- **Processing Pipelines** - Chat (prompt→tokenize→inference→detokenize→SSE), Model (fetch→split→quant→cache), RAG (chunk→embed→index→store), Plugin (validate→sandbox→register)
- **Storage Layer** - Two SQLite DBs (WAL mode), model files (installed/, GGUF, offload_cache/), vector index (vectors/, vector_index/), runtime files (sessions/, plugins/, logs/, hf_cache/)
- **Outputs** - Streaming tokens, full responses, benchmarks, system status, RAG results, plugin outputs

### 4. `tech-stack.mmd` - Technical Stack Architecture
**Technology stack diagram** organized by layer with dependency flows:

- **Frontend Layer** - Next.js 16, React 19, TypeScript 5, Tailwind v4 (@theme inline), shadcn/ui, Zustand, Framer Motion, Recharts
- **Electron Desktop** - Electron 28, electron-builder 24, custom protocol, dev server mode
- **Landing Page** - Separate Next.js 14 + React 18 + Tailwind v3
- **Backend Layer** - FastAPI 0.109, Uvicorn 0.27, Pydantic 2.5, pydantic-settings, asyncio/ThreadPoolExecutor
- **ML/Inference Layer** - Transformers 4.45 + PyTorch 2.5.1 (primary), ik-llama-cpp-python/llama-cpp-python (GGUF fallback), custom LayerStream components
- **Quantization** - Int8/Int4 via WeightSplitter, TurboQuant (default OFF, eval gate fails)
- **RAG Stack** - sentence-transformers, faiss-cpu, recursive chunker
- **Data Layer** - SQLite (WAL, mmap), aiosqlite, Fernet+PBKDF2HMAC encryption, Bearer auth (opt-in), bcrypt, slowapi rate limiting
- **Infrastructure** - uv (canonical), pip/venv (launcher), npm, pytest (asyncio_mode=auto, @slow marker), benchmarks (non-pytest), dev tools
- **Hardware Targets** - CPU, CUDA, MPS, RAM, NVMe, USB portable deployment

## Viewing Diagrams

### VS Code / Cursor
Install "Markdown Preview Mermaid Support" extension, then open `.mmd` files.

### GitHub / GitLab
Mermaid renders natively in markdown files. Rename to `.md` or embed in markdown:

```markdown
```mermaid
%% paste diagram content here
```
```

### Mermaid Live Editor
Copy diagram content to [mermaid.live](https://mermaid.live/)

### CLI Rendering
```bash
# Install mermaid-cli
npm install -g @mermaid-js/mermaid-cli

# Render to SVG
mmdc -i system-architecture.mmd -o system-architecture.svg

# Render to PNG
mmdc -i system-architecture.mmd -o system-architecture.png
```

## Key Architectural Decisions Documented

1. **Engine Selection in ModelManager, not engines** - Factory pattern with TaskResolver + MemoryManager/llmfit
2. **FullRAM primary, GGUF fallback only** - Transformers AutoModelForCausalLM is the main path
3. **LayerStream single engine** - All legacy duplicates deleted, only `executor.py:LayerStreamEngine` remains
4. **All paths relative** - `./workspace/` for USB portability, no absolute paths
5. **Launch scripts bypass settings DB** - `launch.bat/sh` hardcode 127.0.0.1:8000; `backend/main.py` reads settings
6. **TurboQuant default OFF** - Eval gate fails on Qwen2-0.5B and Pythia-70m
7. **Two SQLite databases** - `sovereign.db` (app data) + `sovereign_settings.db` (config)
8. **Opt-in LAN auth only** - Localhost stays auth-free for Electron/CLI loopback
9. **Plugin sandbox = timeout only** - No FS/network/memory isolation on Windows (documented gap)
10. **No conftest.py** - All test fixtures inline per file