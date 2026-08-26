# SovereignAI Edge — Complete Architecture & System Design Deep Dive

> A portable, 100% offline AI platform that runs large language models locally on consumer hardware or USB drives. No cloud dependency. No data leaves the machine.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Client Layer — Three UIs](#3-client-layer--three-uis)
4. [Gateway Layer — FastAPI](#4-gateway-layer--fastapi)
5. [Core Services — The Decision Engine](#5-core-services--the-decision-engine)
6. [Inference Engines](#6-inference-engines)
7. [Data Layer — Storage & Persistence](#7-data-layer--storage--persistence)
8. [RAG — Retrieval-Augmented Generation](#8-rag--retrieval-augmented-generation)
9. [Security & Encryption](#9-security--encryption)
10. [Plugin System](#10-plugin-system)
11. [Settings & Personalization](#11-settings--personalization)
12. [End-to-End Data Flows](#12-end-to-end-data-flows)
13. [Deployment & Runtime](#13-deployment--runtime)
14. [Memory Management Deep Dive](#14-memory-management-deep-dive)
15. [LayerStream — Layer-by-Layer Inference](#15-layerstream--layer-by-layer-inference)
16. [Frontend Architecture](#16-frontend-architecture)
17. [Electron Desktop Shell](#17-electron-desktop-shell)

---

## 1. System Overview

SovereignAI Edge is a self-contained AI inference platform designed to run entirely offline. It bundles a Python backend (FastAPI + PyTorch), a React frontend (Next.js 16 static export), and an optional Electron desktop wrapper into a single portable directory that can live on a USB drive.

**Core design principles:**

- **Portability:** All paths are relative. No absolute paths exist anywhere in the codebase. The entire runtime lives inside `./workspace/` relative to the installation root.
- **Offline-first:** No cloud API calls required. Models are downloaded once (or imported from USB), then run purely locally.
- **Two inference engines:** A fast path (FullRAM) that loads the entire model into RAM/VRAM, and a memory-bounded path (LayerStream) that swaps layer weights from disk per forward pass, enabling 3–8B Q4 models on ~8GB RAM.
- **OpenAI-compatible API:** The backend exposes `/v1/chat/completions` with streaming SSE, making it a drop-in local replacement for the OpenAI API.
- **No Docker, no containers:** Pure Python + Node.js. Runs directly on the host OS or from a USB stick.

---

## 2. High-Level Architecture

The system is organized into five distinct layers:

```
┌─────────────────────────────────────────────────────┐
│  CLIENT LAYER                                        │
│  React Web (Next.js 16) │ Electron 28 │ Python CLI  │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / WebSocket (127.0.0.1:8000)
┌──────────────────────▼──────────────────────────────┐
│  GATEWAY LAYER                                       │
│  FastAPI + 8 subrouters (/v1/*)                     │
│  lifespan() │ CORS │ Rate Limit │ Auth Middleware    │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  CORE SERVICES                                       │
│  ModelManager │ EngineFactory │ TaskResolver         │
│  MemoryManager │ HardwareDetector │ SettingsService  │
└──────┬───────────────┬──────────────────────────────┘
       │               │
┌──────▼──────┐ ┌──────▼──────────────────┐
│  FULLRAM    │ │  LAYERSTREAM             │
│  ENGINE     │ │  ENGINE                  │
│  (transformers│ │  (raw PyTorch)          │
│   + GGUF   │ │  layer-by-layer          │
│   fallback)│ │  + prefetch + LRU cache  │
└─────────────┘ └─────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  DATA LAYER                                          │
│  2 SQLite DBs (WAL) │ FAISS Vector Store             │
│  workspace/ (models, cache, sessions, logs)          │
└─────────────────────────────────────────────────────┘
```

---

## 3. Client Layer — Three UIs

### 3.1 React Web (Next.js 16 + React 19)

The primary UI. Built with Next.js 16 App Router, React 19, and shadcn/ui components (new-york style, Tailwind v4 with `@theme inline` CSS variables). Static export mode (`output: 'export'` in `next.config.ts`) produces flat HTML/JS/CSS in `frontend/out/` — no Node.js server needed at runtime.

**State management:** Zustand v5 store holds `systemStatus`, `messages`, `hardware`, and `settings`.

**API communication:** A single `ApiClient` class (`frontend/lib/api.ts`) wraps all fetch calls to `http://127.0.0.1:8000`. Every request carries a `Bearer` token from `localStorage` when configured (for LAN access). The client retries on connection failure and the WebSocket metrics channel auto-reconnects.

**Key pages:**
- `/` — Home: if a model is loaded, shows `ChatModule` directly; otherwise shows hardware dashboard + model recommendations
- `/models` — Model browser, pull/download, load/unload
- `/console` — Chat interface with streaming SSE
- `/settings` — General, Personalization, Security, Parental Controls, Agents
- `/rag` — Document upload, query, chunk inspection
- `/plugins` — Plugin enable/disable

### 3.2 Electron 28 Desktop Wrapper

A thin native shell (`electron/main.js`) that:

1. Registers a custom `app://` protocol to serve the static `frontend/out/` directory
2. Spawns the Python backend as a child process (`uvicorn app.main:app --host 127.0.0.1 --port 8000`)
3. Creates a `BrowserWindow` loading either `localhost:3000` (dev mode with `USE_DEV_SERVER=true`) or `app://-/` (production)
4. Provides native features via IPC: file dialogs, notifications, app version, backend restart
5. System tray integration with minimize-to-tray behavior

**Startup sequence:** `app.whenReady()` → `createWindow()` (shows UI immediately) → `startBackend()` (boots Python in parallel). The frontend retries `/status` and the metrics WebSocket reconnects, so a briefly-unreachable backend self-heals.

**Packaging:** `electron-builder` bundles `../backend` and `../frontend/out` as `extraResources`. Builds for Windows (NSIS), macOS (DMG), and Linux (AppImage + deb).

### 3.3 Python CLI (typer + rich)

A terminal interface (`backend/app/cli/main.py`) providing:

- `sovereign serve` — Start the FastAPI server
- `sovereign chat` — Interactive REPL chat session
- `sovereign run <prompt>` — One-shot generation
- `sovereign pull <model>` — Download a model from HuggingFace
- `sovereign import <file>` — Import a GGUF file
- `sovereign list` — List installed models
- `sovereign benchmark` — Run performance benchmarks
- `sovereign system` — Show hardware info

Uses `prompt_toolkit` for the interactive chat REPL and `rich` for formatted output.

---

## 4. Gateway Layer — FastAPI

### 4.1 Application Bootstrap (`backend/app/main.py:lifespan()`)

The `lifespan()` async context manager handles the entire startup sequence:

1. **Configure logging** — `SOVEREIGN_LOG_LEVEL` env var, structured format
2. **Patch GGUF** — Adds IQ2_BN (BitNet) quantization type if the installed `gguf` package lacks it
3. **Initialize DatabaseManager** — Opens `workspace/database/sovereign.db` (WAL mode, thread-local connections)
4. **Initialize VectorStoreManager** — FAISS index + metadata DB for RAG
5. **Detect hardware** — `HardwareDetector` probes CPU, RAM, GPU (CUDA), disk speed via `llmfit`
6. **Initialize ModelManager** — Sets up HuggingFace provider, custom catalog loader, background model scanner
7. **Initialize SettingsService** — Reads `workspace/database/sovereign_settings.db`
8. **Load startup model** — If `general.startup_model` is configured in settings, auto-loads it with `general.default_mode`
9. **Initialize PluginManager** — Loads builtin + user plugins via `importlib`

All services are attached to `app.state.*` for dependency injection throughout the request lifecycle.

### 4.2 Route Structure (`backend/app/api/router.py`)

Eight subrouters mounted under `/v1`:

| Prefix | Module | Purpose |
|--------|--------|---------|
| `/v1/chat` | `chat.py` | Chat completions, task execution, mode switching |
| `/v1/models` | `models.py` | Model listing, loading, unloading, pulling, deleting |
| `/v1/system` | `system.py` | System status, hardware info, recommendations |
| `/v1/benchmark` | `benchmark.py` | Performance benchmarks, mode comparison |
| `/v1/rag` | `rag.py` | Document upload, query, chunk inspection |
| `/v1/plugins` | `plugins.py` | Plugin listing, enable/disable, execution |
| `/v1/workspace` | `workspace.py` | Workspace snapshots (save/load/delete) |
| `/v1/settings` | `settings/router.py` | Settings CRUD, password/PIN, agent management |

Plus:
- `/ws/metrics` — WebSocket for real-time system metrics (1s broadcast)
- `/` — Health check
- `/health` — Detailed health with model status

### 4.3 Middleware Stack

1. **CORS** — Allows `localhost:3000`, `127.0.0.1:3000`, `app://-` (Electron)
2. **Rate Limiter** — `slowapi` at 60 requests/minute per IP
3. **Auth Middleware** — Opt-in Bearer token enforcement. Only active when `bind_localhost_only=false` AND `api_token` is configured in settings. Localhost stays auth-free for Electron/CLI loopback.
4. **Error Handler** — Transforms all HTTP errors into OpenAI-compatible `{error: {message, type, param, code}}` format

### 4.4 OpenAI-Compatible Chat (`/v1/chat/completions`)

The chat endpoint is the heart of the system. Here's the complete request lifecycle:

**Step 1: Validate & Extract**
- Parse `ChatRequest` (messages, model, stream, max_tokens, temperature, top_p, enable_thinking, use_rag)
- Verify an engine is loaded; return 400 if not

**Step 2: Inject System Prompt**
- `SettingsService.get_system_prompt()` builds a prompt from personalization settings (style, characteristics, response length, user context, custom instructions) and any active agent's system instruction
- Prepended to messages if not already present

**Step 3: RAG Integration (optional)**
- If `use_rag=true` and vector store is initialized:
  - Find the last user message
  - Condense query with last 3 messages for context
  - `vector_store.build_context(query, top_k=5, max_tokens=2048)` — FAISS cosine search
  - Inject retrieved context tagged as `[RETRIEVED CONTEXT — machine-generated, verify before trusting]`
  - Extract citation metadata (document_id, filename, score)

**Step 4: Apply Chat Template**
- If the engine's tokenizer has `apply_chat_template`, use it (handles thinking mode toggle via `enable_thinking`)
- Fallback: simple `System: / User: / Assistant:` concatenation

**Step 5: Stream or Generate**
- **Streaming:** `stream_response()` async generator returns `StreamingResponse` with `media_type="text/event-stream"`
- **Non-streaming:** `engine.generate()` returns a single JSON response

**Step 6: Post-Processing**
- `_split_think()` separates `<think>...</think>` reasoning from content
- `_trim_tag_prefix()` drops trailing partial tags at frame boundaries
- SSE batching (~96 chars/frame) reduces frame count ~10x

### 4.5 SSE Streaming Protocol

The `stream_response()` generator:

1. Accumulates raw text in `full_text`
2. On each engine token, calls `_split_think(full_text)` to separate content from reasoning
3. `_trim_tag_prefix()` prevents half-emitted `<think>` or `</think>` tags from leaking
4. Computes deltas (new content since last emission, new reasoning since last emission)
5. Batches deltas into frames of ~96 characters before emitting
6. Checks `http_request.is_disconnected()` on every token to abort abandoned streams
7. Appends RAG metadata as a special chunk before `[DONE]`

Output format (SSE):
```
data: {"id":"chatcmpl-...","choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-...","choices":[{"delta":{"reasoning":"Let me think..."},"finish_reason":null}]}

data: {"id":"chatcmpl-...","choices":[{"delta":{"rag_metadata":[...]},"finish_reason":null}]}

data: {"id":"chatcmpl-...","choices":[{"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

### 4.6 Mode Switching (`/v1/chat/mode/switch`)

POST endpoint that reloads the current model in a different execution mode. Delegates to `ModelManager.load_model()` which handles the full unload → create → load cycle.

---

## 5. Core Services — The Decision Engine

### 5.1 ModelManager (`backend/app/services/model_manager.py`)

The central coordinator for model lifecycle. Key responsibilities:

**Model Discovery:**
- Background scan of `workspace/models/installed/` on startup (non-blocking)
- Scans for HuggingFace directories (config.json), standalone GGUF files, and pre-split models in `workspace/offload_cache/`
- Syncs discovered models with the SQLite registry
- Cleans up stale registry entries for deleted files

**Fuzzy Matching:**
- `_fuzzy_match_model()` resolves display names (e.g. "Qwen3.5-0.8B") to registry IDs
- Normalizes slashes/colons, prefers exact matches, then containment matches
- Split variants (`split:...`) never win fuzzy matches — they're derived views of base models

**Model Loading (`load_model()` → `_load_model_locked()`):**

1. **Wait for background scan** — Ensures registry is complete before loading
2. **Resolve model** — Direct lookup → fuzzy match → raise if not found
3. **Acquire load lock** — `asyncio.Lock` serializes concurrent loads (two simultaneous loads would fight over `app.state`)
4. **Mode correction:**
   - Split models in auto mode → forced to `layerstream`
   - FullRAM + split model → redirect to base model path
5. **Disk full preflight** — LayerStream needs ~model-size free disk for swap cache
6. **Create engine** — `EngineFactory.create_engine()` with task metadata for llmfit scoring
7. **Load engine** — `engine.load()` with error rollback (restores previous engine on failure)
8. **Unload previous** — Clean up old engine after new one is confirmed loaded
9. **Update app state** — `app.state.active_engine`, `active_model`, `active_mode`

**Model Download:**
- Fetches from HuggingFace via `HuggingFaceProvider`
- Supports quantized GGUF (Q4_K_M, Q5_K_M, Q8_0) and full repo downloads
- Progress callbacks update `download_status` dict
- Writes `metadata.json` alongside downloaded files
- Maps quant strings to `quant_method` (gguf variants → "gguf", full repos → "none")

**Model Deletion:**
- Path-root guard: refuses to delete outside `models/` directory even if registry metadata is tampered
- Removes from disk and registry

### 5.2 TaskResolver (`backend/app/core/task_resolver.py`)

Static introspection engine that determines model capabilities from HuggingFace `AutoConfig`:

**Resolution process:**
1. `AutoConfig.from_pretrained()` — tries local first, then remote
2. If config loading fails (raw GGUF / unconfigured): returns safe default `{causal_lm, generative: True}`
3. Reads `architectures`, `model_type`, `is_encoder_decoder` from config
4. Maps architecture suffixes to task categories:
   - `ForCausalLM` → `causal_lm` (generative)
   - `ForSeq2SeqLM` / `ForConditionalGeneration` → `seq2seq_lm` or `causal_lm` (checks `is_encoder_decoder`)
   - `ForMaskedLM` → `masked_lm`
   - `ForSequenceClassification` → `sequence_classification`
   - `ForQuestionAnswering` → `question_answering`
   - `ForImageClassification` → `image_classification` (input_modality: image)
   - Vision2Seq / LLaVA → `vision2seq` (input_modality: multimodal, generative)
   - Whisper → `speech_seq2seq` (input_modality: audio, generative)
   - And many more (20+ task types supported)
5. Heuristic guard: `vision_config` attribute only triggers `vision2seq` if no task was matched above (prevents Qwen3.5 misclassification)

**Output:** `{model_path, architectures, model_type, task_type, input_modality, is_generative}`

### 5.3 MemoryManager (`backend/app/core/memory_manager.py`)

Determines the optimal execution mode based on available resources.

**Two-tier decision:**

**Tier 1 — llmfit scoring (when metadata available):**
- Calls `llmfit.score_model_fit(model_name, hw)` for a fit score
- `fit_score > 0.85` AND `ram_required < 70% of total RAM` → `fullram`
- `fit_score > 0.6` → `layerstream`
- Otherwise → `insufficient`

**Tier 2 — Legacy threshold fallback:**
- CUDA VRAM: `model_size * 1.1 < free_vram` → `fullram`
- System RAM: `model_size * 1.1 < available_ram` → `fullram`
- `model_size * 0.1 < available_ram` → `layerstream`
- Otherwise → `insufficient`

### 5.4 EngineFactory (`backend/app/core/engine_factory.py`)

Creates the appropriate engine instance based on mode and model characteristics.

**Process:**
1. Compute model size from disk (sum of all files for directories, single file size for GGUF)
2. Resolve task via `TaskResolver.resolve()`
3. If mode is `auto`, use `MemoryManager.suggest_mode()` — non-generative + layerstream suggestion → forced fullram
4. Read `quant_method` from `metadata.json` (maps GGUF quant strings to "gguf")
5. Instantiate `FullRAMEngine` or `LayerStreamEngine` with hardware profile and memory manager

---

## 6. Inference Engines

### 6.1 BaseEngine ABC (`backend/app/engines/base.py`)

All engines implement five abstract methods:

```python
class BaseEngine(ABC):
    async def load(self): ...
    async def unload(self): ...
    async def generate(input_data, **kwargs) -> Dict: ...
    async def generate_stream(input_data, **kwargs) -> AsyncGenerator[Dict, None]: ...
    def get_memory_usage(self) -> Dict: ...
```

Plus a concrete `get_stats()` method.

### 6.2 FullRAM Engine (`backend/app/engines/fullram/executor.py`)

The fast path: loads the entire model into RAM/VRAM using `transformers.AutoModelForCausalLM`.

**Load sequence:**
1. Resolve task via `TaskResolver` → get task_type, input_modality, is_generative
2. Get model class via `TaskRouter.get_model_class(task_type)`
3. Configure device (CUDA with float16, or CPU with float32)
4. Handle GGUF files: pass `gguf_file=` kwarg to `from_pretrained()`
5. Handle `.bin` checkpoints: convert to safetensors first (CVE-2025-32434 mitigation)
6. Load tokenizer (`AutoTokenizer`) and processor (`AutoProcessor` / `AutoImageProcessor`) based on modality
7. **GGUF fallback chain:** If transformers fails:
   - Try `ik_llama_cpp.IkLlama` (handles BitNet / IQ2_BN models)
   - Fall back to `llama_cpp.Llama` (standard GGUF)
   - If both fail, raise descriptive error

**Generate:** Processes inputs based on modality (text, image, audio, multimodal), routes through `TaskRouter.execute()`, decodes output tokens, reports finish_reason (stop vs length).

**Stream:** Uses `TextIteratorStreamer` in a separate thread. For llama.cpp backends, streams directly from the C++ library (ik_llama doesn't support streaming — yields full output at once).

**Memory:** Reports RSS, peak WSET, VRAM allocated/peak.

### 6.3 LayerStream Engine (`backend/app/engines/layerstream/executor.py`)

The memory-bounded path: swaps layer weights from disk per forward pass via raw PyTorch + safetensors. Enables running larger models on limited RAM at the cost of slower inference.

**Load sequence:**
1. Create offload cache directory: `workspace/offload_cache/<model_name>/`
2. If not already split: run `WeightSplitter.split_and_save()` to split model into per-layer `.safetensors` files
3. Load tokenizer from split directory (with fallback to source)
4. Load `AutoConfig` from split directory, force `eager` attention
5. Create empty model skeleton via `init_empty_weights()` + `AutoModelForCausalLM.from_config()`
6. Detect model components via `ModelIntrospector`
7. Detect hybrid architecture (e.g. Qwen3.5's mix of linear_attention and full_attention layers)
8. Initialize `LayerExecutor` with prefetch depth, cache budget, turboquant config

**Generate (two-phase computation):**

*Phase 1 — Prefill:*
- Feed entire input sequence through all layers in one pass
- Cache KV states per layer
- Sample first token from logits

*Phase 2 — Decode:*
- Single-token step, reusing cached KV from previous steps
- Loop until EOS or max_tokens
- Run in `asyncio.to_thread()` to avoid blocking the event loop

**Stream:**
- Same two-phase approach but yields tokens incrementally
- Uses `_stream_delta()` with rolling-window overlap matching (robust to BPE subword merge instability)
- Reports `finish_reason: "length"` when max_tokens is exhausted (not "stop")

---

## 7. Data Layer — Storage & Persistence

### 7.1 Workspace Structure

All runtime data lives inside `./workspace/` with no absolute paths:

```
workspace/
├── models/
│   ├── installed/          # Downloaded models (HF repos, GGUF files)
│   │   ├── Qwen2-0.5B/    # HuggingFace directory with config.json
│   │   └── model.gguf      # Standalone GGUF file
│   └── hf_cache/           # HuggingFace tokenizer/config cache
├── database/
│   ├── sovereign.db        # Models, sessions, documents, hardware profiles
│   └── sovereign_settings.db  # Settings, agents, audit log
├── offload_cache/          # LayerStream per-layer .safetensors splits
│   └── Qwen2-0.5B/
│       ├── embed.safetensors
│       ├── layer_0.safetensors
│       ├── layer_N.safetensors
│       ├── norm.safetensors
│       ├── lm_head.safetensors
│       └── quant_config.json
├── sessions/               # Chat session snapshots
├── vectors/                # FAISS index files
├── vector_index/           # Vector metadata
├── plugins/                # User Python plugin scripts
├── data/                   # General data storage
└── logs/                   # server_cli.log
```

### 7.2 SQLite Databases

**`sovereign.db` (DatabaseManager):**
- WAL mode, thread-local connections, `synchronous=NORMAL`, `mmap_size=256MB`
- Tables: `models`, `sessions`, `documents`, `messages`, `hardware_profiles`, `plugins`, `benchmark_results`, `audit_log`, `schema_version`
- Async access via `aiosqlite` + `ModelRegistry`

**`sovereign_settings.db` (SettingsDatabase):**
- Same WAL configuration
- Tables: `settings` (JSON blob per section), `agents`, `audit_log`
- Sections: general, personalization, data_controls, security, parental_controls, project

### 7.3 Configuration (`backend/app/config.py`)

Uses `pydantic-settings` `BaseSettings` with env prefix `SOVEREIGN_`:

- All paths are relative via `Path(__file__).parent...` (USB portable)
- `HF_HOME` forced to `workspace/hf_cache`
- `turboquant_enabled` defaults to `False` (eval gate fails)
- `trust_remote_code` defaults to `False` (security gate)

---

## 8. RAG — Retrieval-Augmented Generation

### 8.1 Architecture

The RAG system uses FAISS for vector search with a local sentence-transformers embedding model.

**Components:**
- `VectorStoreManager` — Central orchestrator
- `DocumentChunker` — Splits documents into overlapping chunks
- `EmbeddingPipeline` — Generates embeddings via sentence-transformers
- `FAISSIndexBuilder` — Manages the FAISS index (Flat or IVF)
- `VectorMetadataStore` — SQLite-backed chunk/embedding metadata
- `Retriever` — Search + context building

### 8.2 Ingestion Pipeline

1. **Chunk** — `DocumentChunker.chunk_text(text, doc_id)` with configurable chunk_size, overlap, max_chunks
2. **Store chunks** — Insert into metadata DB
3. **Embed** — `EmbeddingPipeline.embed_texts(texts, batch_size=32)` using sentence-transformers
4. **Index** — Add vectors to FAISS index (auto-creates or trains IVF if enough vectors)
5. **Save** — Persist index to disk

### 8.3 Query Pipeline

1. **Embed query** — Same embedding model
2. **FAISS search** — Cosine similarity, top_k results
3. **Build context** — Concatenate relevant chunks up to max_tokens
4. **Inject into prompt** — Tagged as machine-generated, with citation metadata

### 8.4 Chat Integration

When `use_rag=true` in a chat request:
- Query condensation: combines last 3 messages for context
- `build_context()` returns `RAGContext` with context_text and results
- Context injected into system message with trust disclaimer
- Citations returned as `rag_metadata` in the final SSE chunk

---

## 9. Security & Encryption

### 9.1 Model Encryption (`backend/app/security/encryption.py`)

Fernet symmetric encryption with PBKDF2HMAC key derivation (480,000 iterations):

**Encryption:**
- Generates random 32-byte salt per file
- Derives key from password + machine salt (hostname + MAC address)
- Chunked format: `SOVEREIGN_ENC_v1` header → salt → reserved → [length-prefixed encrypted chunks]
- 64MB chunk size for memory efficiency

**Decryption:**
- Reads salt from file header
- Derives key from password (or machine key if no password)
- Decrypts chunks sequentially

**Machine key:** Derived from `platform.node()` + `uuid.getnode()` — models encrypted with machine key can only be decrypted on the same machine.

### 9.2 Auth Middleware (`backend/app/security/middleware.py`)

Opt-in Bearer token enforcement:

- Only active when `bind_localhost_only=false` (server accessible from LAN)
- AND `api_token` is configured in settings
- Uses `secrets.compare_digest` for timing-safe comparison
- Localhost stays auth-free (Electron/CLI loopback)

### 9.3 Plugin Sandboxing (`backend/app/plugins/sandbox.py`)

Timeout-only sandbox (30 seconds). No filesystem, network, or memory isolation on Windows (documented gap).

---

## 10. Plugin System

### 10.1 Plugin Interface (`backend/app/plugins/interface.py`)

All plugins implement:
```python
class PluginInterface(ABC):
    async def initialize(self): ...
    async def cleanup(self): ...
    def get_actions(self) -> List[str]: ...
    async def execute(self, action: str, params: Dict) -> Any: ...
```

### 10.2 Plugin Manager (`backend/app/plugins/manager.py`)

- Loads from two directories: `backend/app/plugins/builtin/` and `workspace/plugins/`
- Uses `importlib.util` for dynamic import
- Finds plugin classes by scanning for `PluginInterface` subclasses
- Calls `initialize()` on load, `cleanup()` on unload
- Executes actions through `PluginSandbox` (timeout-only)

---

## 11. Settings & Personalization

### 11.1 SettingsService (`backend/app/settings/service.py`)

Per-section CRUD backed by `SettingsDatabase`:

- **General:** startup_model, default_mode
- **Personalization:** base_style_tone, characteristics, headers_lists_mode, response_length, preferred_name, profession, user_context, custom_instructions
- **Security:** bind_localhost_only, api_token, require_password, password_hash
- **Parental Controls:** require_pin_for_settings, pin_hash
- **Data Controls:** Data governance settings
- **Project:** Project-specific settings

### 11.2 System Prompt Builder

`get_system_prompt()` constructs a prompt from:
1. Base style tone (professional, casual, etc.)
2. Characteristics (helpful, creative, etc.)
3. Headers/lists mode (always, never, minimal)
4. Response length (short, default, long, detailed)
5. User context (name, profession, background)
6. Custom instructions
7. Active agent's system instruction (if any)

---

## 12. End-to-End Data Flows

### 12.1 Chat Request Flow

```
User types message in React UI
  → POST /v1/chat/completions {messages, stream: true}
    → CORS check → Rate limit check → Auth check (if LAN)
      → chat_completions()
        → Verify engine loaded
        → Inject system prompt (SettingsService)
        → Optional RAG (FAISS search → inject context)
        → Apply chat template (tokenizer)
        → Return StreamingResponse(stream_response())
          → engine.generate_stream()
            → [FullRAM: TextIteratorStreamer thread]
            → [LayerStream: prefill → decode loop in asyncio.to_thread]
          → Per token: _split_think → _trim_tag_prefix → batch deltas
          → SSE frame (~96 chars): data: {delta: {content: "..."}}
          → Check client disconnected → abort if so
          → Final: [DONE]
```

### 12.2 Model Loading Flow

```
User clicks "Load" in UI
  → POST /v1/models/load {model: "Qwen2-0.5B", mode: "auto"}
    → ModelManager.load_model()
      → Wait for background scan
      → Resolve model (direct → fuzzy match)
      → Acquire _load_lock
        → Mode correction (split: → layerstream)
        → Disk full preflight (LayerStream only)
        → EngineFactory.create_engine()
          → TaskResolver.resolve() (AutoConfig introspection)
          → MemoryManager.suggest_mode() (llmfit or threshold)
          → Instantiate FullRAMEngine or LayerStreamEngine
        → engine.load()
          → [FullRAM: AutoModelForCausalLM.from_pretrained() → CUDA/CPU]
          → [LayerStream: WeightSplitter → LayerExecutor init]
        → Unload previous engine
        → Update app.state
      → Return {status: "loaded", model, mode}
```

### 12.3 LayerStream Inference Flow

```
Input prompt → tokenize → input_ids
  │
  ▼ Phase 1: PREFILL
  ┌─────────────────────────────────┐
  │ For each layer i:               │
  │   get_weights(i) → CPU safetensors
  │   dequantize_on_device() → GPU tensor
  │   execute_forward(input_ids)    │
  │   cache KV per layer            │
  │   prefetch_async(i+1..i+3)     │
  └─────────────────────────────────┘
  │
  ▼ Sample first token from logits
  │
  ▼ Phase 2: DECODE (loop max_tokens times)
  ┌─────────────────────────────────┐
  │ For each layer i:               │
  │   get_weights(i) → from LRU or disk
  │   dequantize → device           │
  │   execute_forward(single_token) │
  │   KV reused from prefill        │
  │   prefetch next layers          │
  └─────────────────────────────────┘
  │
  ▼ Sample next token
  ▼ If EOS or max_tokens → stop
  ▼ Yield token via _stream_delta()
```

### 12.4 RAG Ingestion Flow

```
User uploads document via UI
  → POST /v1/rag/upload (multipart form)
    → Read file content
    → VectorStoreManager.ingest_text(text, filename)
      → DocumentChunker.chunk_text()
      → Store chunks in metadata DB
      → EmbeddingPipeline.embed_texts()
      → FAISSIndexBuilder.add_vectors()
      → Save index to disk
    → Return {document_id, chunks_count}
```

---

## 13. Deployment & Runtime

### 13.1 Launch Paths (4 entry points)

1. **`launch.bat` / `launch.sh`** — Hardcodes `--host 127.0.0.1 --port 8000`, bypasses settings DB
2. **`python main.py` (from backend/)** — Reads `sovereign_settings.db` for host/port/bind settings
3. **`npm start` (from electron/)** — Spawns backend as child process, loads frontend via custom protocol
4. **`sovereign` CLI** — typer-based, multiple subcommands

### 13.2 USB Deployment

```
Clone repo → .venv install → ./launch.sh → workspace/ created on first run
```

All paths relative. No absolute paths. `HF_HOME` forced to `workspace/hf_cache`. The entire directory can be copied to a USB drive and run from any machine.

### 13.3 Electron Packaging

`electron-builder` configuration:
- `extraResources`: `../backend` → `backend/`, `../frontend/out` → `frontend/`
- Windows: NSIS installer (oneClick=false, allowChangeDir=true)
- macOS: DMG
- Linux: AppImage + deb
- App ID: `com.sovereignai.edge`

---

## 14. Memory Management Deep Dive

### 14.1 FullRAM Memory

- **VRAM (CUDA):** Entire model loaded via `device_map="auto"` (transformers handles placement)
- **RAM (CPU):** Model loaded with `low_cpu_mem_usage=True`
- **KV Cache:** Grows linearly with context length: `4 × L_ctx × N_layers × D_hidden × precision_bytes`
- **7B model example:** 32 layers × 4096 hidden × FP16 → ~2GB KV at 2048 tokens

### 14.2 LayerStream Memory

- **VRAM peak:** Size of 1 layer + KV cache + buffers
- **System RAM:** LRU byte-budget cache + KV cache RAM + prefetch futures
- **Pinned paths:** `embed`, `layer_N/norm`, `lm_head` — never evicted from cache
- **LRU eviction:** `_enforce_budget()` pops least-recently-used non-pinned entries until bytes are below budget
- **Cache budget:** Auto-scaled from largest per-layer file × 4.5 (window + headroom), floor 256MB

### 14.3 Context Window Sliding

When token count exceeds budget:
1. Pin system prompt (never pruned)
2. Drop oldest 50% of history tokens
3. Invalidate corresponding KV cache entries
4. Rebuild attention mask with shorter past
5. Continue with shorter context — no OOM

---

## 15. LayerStream — Layer-by-Layer Inference

### 15.1 Weight Splitting (`backend/app/engines/layerstream/splitter.py`)

Offline phase that splits a consolidated model into per-layer files:

- Input: HuggingFace model directory (`.bin` or `.safetensors`)
- Output: `workspace/offload_cache/<model>/embed.safetensors`, `layer_0.safetensors`, ..., `layer_N.safetensors`, `norm.safetensors`, `lm_head.safetensors`
- Also writes `quant_config.json` with quantization method (none/int8/int4/gguf)

### 15.2 Layer Weight Loader (`backend/app/engines/layerstream/loader.py`)

Manages loading weights from disk with prefetching:

- `ThreadPoolExecutor(prefetch_depth=3)` — Loads future layers while current layer computes
- LRU byte-budget cache — Keeps recently-used layers in RAM
- Pinned paths (embed/norm/lm_head) exempt from eviction
- `_load_file()` — Uses `safetensors.torch.safe_open()` for memory-mapped loading
- `dequantize_on_device()` — Handles int8 (scale + reshape) and int4 (packed 2-values/byte + unpack + scale)

### 15.3 Layer Executor (`backend/app/engines/layerstream/layer_executor.py`)

Orchestrates the layer-by-layer forward pass:

- `execute_forward(input_ids, mode="prefill"|"decode")`
- Manages attention mask caching and RoPE pre-computation
- Handles hybrid architectures (Qwen3.5's mixed attention types)
- Two cache paths:
  - `StatefulCache` — For hybrid models (rolling window)
  - `KVCacheManager` + `HFProxyCache` — For standard models

### 15.4 Sampler (`backend/app/engines/layerstream/sampler.py`)

Non-destructive sampling:
- Top-K filtering
- Top-P (nucleus) filtering
- Multinomial sampling
- Temperature scaling

### 15.5 Streaming Delta (`_stream_delta()`)

Robust text delta computation for BPE tokenizers:
- Decodes a rolling window of the last 8 tokens
- Longest-overlap matching against already-emitted text
- Prevents dropped/duplicated deltas from BPE merge instability
- Falls back to single-token decode when no stable overlap exists

---

## 16. Frontend Architecture

### 16.1 Tech Stack

- **Framework:** Next.js 16 (App Router, React 19, TypeScript 5)
- **UI Library:** shadcn/ui (new-york style) + Radix UI primitives
- **Styling:** Tailwind v4 via `@tailwindcss/postcss`, `@theme inline` CSS variables in `app/globals.css`
- **State:** Zustand v5
- **Icons:** Lucide React
- **Charts:** Recharts 3
- **Animation:** Framer Motion 12
- **Build:** Static export (`output: 'export'`) → `frontend/out/`

### 16.2 Component Structure

```
frontend/
├── app/                    # Next.js App Router pages
│   ├── page.tsx            # Home (chat-first when model loaded)
│   ├── models/             # Model browser
│   ├── console/            # Chat interface
│   ├── settings/           # Settings pages
│   ├── rag/                # RAG document management
│   └── plugins/            # Plugin management
├── components/
│   ├── ui/                 # shadcn/ui primitives (button, card, etc.)
│   ├── models/             # ModelControlPanel, ModelCard
│   ├── task/               # ChatModule (core chat component)
│   ├── settings/           # SecuritySettings, etc.
│   └── plugins/            # PluginList
├── lib/
│   ├── api.ts              # ApiClient (all backend calls)
│   ├── utils.ts            # cn() helper
│   └── maskedLm.test.ts    # Unit test
├── store/                  # Zustand store
├── hooks/                  # Custom React hooks
└── types/                  # TypeScript type definitions
```

### 16.3 Chat Flow (Frontend)

1. User types message → React state updates
2. `POST /v1/chat/completions` with `stream: true`
3. Read SSE response via `fetch` + `ReadableStream`
4. Parse each `data: {...}` frame
5. Accumulate `delta.content` and `delta.reasoning` separately
6. Render content tokens in real-time
7. Show reasoning in a collapsible `<think>` block
8. On `[DONE]`, finalize message
9. `rag_metadata` chunk triggers citation display

---

## 17. Electron Desktop Shell

### 17.1 Main Process (`electron/main.js`)

**Startup:**
1. `app.whenReady()` → register `app://` protocol for static file serving
2. `createWindow()` — 1400×900 BrowserWindow, hidden until ready
3. `createMenu()` — Custom application menu
4. `createTray()` — System tray with minimize-to-tray
5. `startBackend()` — Spawns `python -m uvicorn app.main:app` as child process
   - Uses venv Python if available, falls back to system Python
   - Waits for "Uvicorn running" in stdout, or 10s timeout
   - Resolves even on error (app opens regardless)

**Custom Protocol:**
- `app://-/` serves `frontend/out/index.html`
- Handles directory indexing (looks for `index.html` in subdirectories)
- Falls back to root `index.html` for SPA routing

**IPC Handlers:**
- `get-app-path`, `get-version`, `show-notification`
- `show-open-dialog`, `show-save-dialog`
- `restart-backend` — Kills and restarts the Python process

**Shutdown:**
- `before-quit` → `stopBackend()` (taskkill on Windows, SIGTERM on Unix)
- `window-all-closed` → quit (except macOS)

---

## Key Design Decisions

1. **Two engines, not one:** FullRAM for speed when memory allows, LayerStream for accessibility on constrained hardware. The auto mode uses llmfit scoring to pick the best option.

2. **Relative paths everywhere:** Enables USB portability. `HF_HOME` is forced to `workspace/hf_cache`. No absolute paths in config, database, or code.

3. **No Docker:** 100% local/offline. The platform runs directly on the host OS or from a USB stick. This is a deliberate constraint for the target use case.

4. **OpenAI-compatible API:** Makes SovereignAI Edge a drop-in replacement for any tool that speaks the OpenAI protocol.

5. **Streaming-first:** The chat endpoint defaults to streaming. SSE batching (~96 chars/frame) balances latency and throughput.

6. **Opt-in security:** Auth is only enforced when explicitly configured and the server is bound beyond localhost. This keeps the local development experience frictionless.

7. **Engine selection in ModelManager, not engines:** Engines never decide their own mode. The factory and memory manager make the decision, keeping engines pure.

8. **LayerStream as the differentiator:** The layer-by-layer approach with prefetching, LRU caching, and double-buffering enables running models that wouldn't fit in RAM otherwise. The tradeoff is speed (0.48–8 tok/s depending on model size).

---

*Document generated from source code analysis of SovereignAI Edge codebase.*
*Last updated: August 26, 2026.*
