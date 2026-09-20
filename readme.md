<div align="center">

# 🛡️ SovereignAI Edge

**The Ultimate Portable AI Platform.**

Run large language models locally on consumer hardware or directly from USB — offline by default, optional cloud mode when you want it.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-yellow.svg)](https://www.python.org/)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.5-ee4c2c.svg)](https://pytorch.org/)
[![Stars](https://img.shields.io/github/stars/SovereignAI/Edge)](https://github.com/SovereignAI/Edge/stargazers)
[![Issues](https://img.shields.io/github/issues/SovereignAI/Edge)](https://github.com/SovereignAI/Edge/issues)

---

**[Quick Start](#-quick-start)** · **[Architecture](#%EF%B8%8F-system-architecture)** · **[Performance](#-performance-the-multi-engine-advantage)** · **[API](#-openai-compatible-api)** · **[Contributing](#-contributing)**

![SovereignAI Edge — Hero](./Info_docs/assets/hero.png)

---

</div>

## ✨ Key Features

<table>
<tr>
<td width="50%">

### 🧠 Three Inference Engines
**FullRAM** loads entire models for blazing speed. **LayerStream** swaps layers from disk — run 3–8B models on 8GB RAM. **CloudAPI** proxies to OpenAI/Anthropic/Google/custom endpoints (keys encrypted at rest).

</td>
<td width="50%">

### 🔒 Offline & Private by Default
Offline mode: zero data leaves your machine. Prompts, documents, and history stay in local SQLite. No telemetry. Cloud mode is opt-in per provider.

</td>
</tr>
<tr>
<td>

### 📦 Portable
Zero-config execution from any USB/SSD. All paths relative — just clone and run.

</td>
<td>

### 🖥️ Three Interfaces
Modern **React Web UI**, **Electron Desktop App**, or powerful **CLI** — pick your workflow.

</td>
</tr>
</table>

---

## 🏗️ System Architecture

```
┌────────────────────────────────────────────────────────┐
│                    Client Layer                        │
│   ┌──────────────┐    ┌────────────────────────┐       │
│   │  React Web   │    │  Electron Desktop App  │       │
│   │  (Next.js)   │    │   (Chromium wrapper)   │       │
│   └──────┬───────┘    └──────────┬─────────────┘       │
│          └──────────┬────────────┘                     │
│                     │ REST / WebSocket                 │
├─────────────────────┼──────────────────────────────────┤
│                  Backend Core                          │
│   ┌─────────────────┴──────────────────────┐           │
│   │        FastAPI Gateway (/v1/*)         │           │
│   │  Chat · Models · RAG · Cloud · Bench   │           │
│   └─────────────────┬──────────────────────┘           │
│                     │                                  │
│   ┌─────────────────┴──────────────────────┐           │
│   │      Engine Selection (mode: auto)     │           │
│   │    Hardware profile → llmfit scoring   │           │
│   └──────┬─────────────────┬───────────────┘           │
│          │                 │                           │
│   ┌──────▼──────┐   ┌──────▼───────┐                   │
│   │   FullRAM   │   │  LayerStream │                   │
│   │ (PyTorch +  │   │ (raw PyTorch │                   │
│   │transformers)│   │ layer-by-    │                   │
│   └─────────────┘   │ layer, 8GB)  │                   │
│                     └──────────────┘                   │
│   ┌────────────────────────────────────────┐           │
│   │ CloudAPI (OpenAI / Anthropic / Google  │           │
│   │      / Mistral / custom endpoints)     │           │
│   └────────────────────────────────────────┘           │
│                                                        │
│   ┌────────────────────────────────────────┐           │
│   │  Storage: workspace/{models,db,...}    │           │
│   └────────────────────────────────────────┘           │
└────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Client** sends chat/message via REST or WebSocket to `127.0.0.1:8000`
2. **FastAPI Gateway** injects system prompt, optional RAG context, and applies chat template
3. **Engine** generates or streams tokens (SSE batching at ~96 chars/frame) — `mode=auto` picks FullRAM/LayerStream via llmfit memory scoring; `mode=cloud` routes to a provider API and skips local memory checks
4. **Response** returned as OpenAI-compatible JSON or Server-Sent Events

---

## ⚡ Performance: The Multi-Engine Advantage

### FullRAM Engine
Loads the entire model into active memory. Best for systems with high VRAM/RAM (NVIDIA RTX, Apple Silicon). Uses `transformers.AutoModelForCausalLM` with GGUF fallback via `llama-cpp-python`.

### LayerStream Engine
Iteratively loads/unloads individual neural network layers from disk to RAM. Enables models larger than free RAM to still run. Sweet spot: **3–8B Q4 models on 8GB RAM**.

> ⚠️ Large models (70B+) run but slowly. See [reviews/benchmark-2026-08-14.md](reviews/benchmark-2026-08-14.md) for honest numbers. Numbers below are local-engine only; cloud latency depends on the provider.
>
> **2026-09-11:** fixed the hybrid (Qwen3.5) LayerStream path — the cache used the transformers-4.x protocol and crashed on transformers 5.x, and the CPU device-cache was disabled (75% of decode spent in re-copying weights). Same model now runs at **1.30 tok/s** vs 0.48 before (2.7×), peak RAM 2.9 GB. The pure-PyTorch GatedDeltaNet fallback is the remaining floor: `fla`/`causal-conv1d` are CUDA-only, so 8 GB CPU boxes without them top out near the FullRAM fp32 control of ~2.2 tok/s.

![Dual Engine Comparison](./Info_docs/assets/dual_engine.png)

### Benchmarks

| Model | Engine | Tokens/sec | Notes |
|:------|:-------|:-----------|:------|
| Qwen2-0.5B (int4) | FullRAM | 0.85 | Fast path |
| Qwen2-0.5B (int4) | LayerStream | 8.0 | Post device-cache fix |
| Qwen3.5-0.8B (int4) | LayerStream | 1.30 | Hybrid; transformers-5.x cache fix + CPU device cache (2026-09-11). Was 0.48. |

### CloudAPI Engine
No local weights loaded — requests proxy to the configured provider (OpenAI, Anthropic, Google, Mistral, or any OpenAI-compatible endpoint: Together, Groq, vLLM, Ollama). API keys are Fernet-encrypted at rest and masked in all API responses.

---

## 📁 File System Layout

```
SovereignAI/
├── backend/          # FastAPI + Inference (Python 3.10+, PyTorch, transformers)
├── frontend/         # Next.js 16 + React 19 (static export)
├── electron/         # Desktop wrapper (Electron 28)
├── workspace/        # Runtime data root
│   ├── models/       # Model checkpoints (.gguf, .safetensors)
│   ├── database/     # SQLite (sovereign.db + sovereign_settings.db)
│   ├── offload_cache/# LayerStream per-layer chunks
│   ├── sessions/     # Chat snapshots
│   ├── data/         # Vector data directory
│   │   └── vector_index/  # FAISS vector index
│   └── plugins/      # User Python plugins
└── Info_docs/        # Obsidian wiki (31 pages)
```

---

## 🖥️ Interface Previews

<table>
<tr>
<td align="center" width="33%">

**React Web UI**

<!-- Replace with: screenshot of the web chat console at localhost:3000 -->
![Web UI](./Info_docs/assets/web-ui-preview.png)

*Chat · Models · Settings*

</td>
<td align="center" width="33%">

**Electron Desktop**

<!-- Replace with: screenshot of the Electron app window -->
![Electron](./Info_docs/assets/electron-preview.png)

*Native desktop experience*

</td>
<td align="center" width="33%">

**CLI**

```bash
$ sovereign chat
> Hello, how are you?
╭ assistant
│ I'm doing well, thanks for asking!...
╰─
```

*Terminal-native workflow*

</td>
</tr>
</table>

---

## 🏁 Quick Start

### Prerequisites

- **Python** 3.10+
- **Node.js** 18+
- **RAM** 8GB+ recommended

### Option A: One-Click Launch

```bash
# Windows
launch.bat

# Linux / macOS
./launch.sh
```

### Option B: Manual Setup

```bash
# 1. Clone the repo
git clone https://github.com/SovereignAI/Edge.git
cd Edge

# 2. Backend
cd backend
pip install -r requirements.txt
python main.py

# 3. Frontend (new terminal)
cd frontend
npm ci
npm run dev

# 4. Electron Desktop (optional, new terminal)
cd electron
npm ci
npm start
```

### Option C: CLI

```bash
cd backend/app
python -m cli.main --help

# Chat with a loaded model
python -m cli.main chat

# Pull a model from HuggingFace
python -m cli.main pull Qwen/Qwen2-0.5B
```

---

## 🔌 OpenAI-Compatible API

SovereignAI Edge exposes a drop-in OpenAI `/chat/completions` endpoint:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

**Supported params:** `messages`, `model`, `max_tokens`, `temperature`, `top_p`, `stream`, `use_rag`, `enable_thinking`

**Thinking mode:** Models that support it stream `<think>` reasoning in `choices[0].delta.reasoning` alongside `content`. Standard OpenAI clients ignore the extra key — shapes pinned by `backend/tests/test_openai_compat.py`.

Point any OpenAI SDK at `base_url=http://127.0.0.1:8000` — no API key needed on localhost.

**Cloud mode:** add a provider once, then switch:

```bash
sovereign cloud add --name "OpenAI" --type openai --key "sk-..."
curl -X POST "http://127.0.0.1:8000/v1/chat/mode/switch?mode=cloud"
```

Provider CRUD + connectivity test also via REST under `/v1/cloud/*`.

---

## ⚠️ Known Limitations

| Area | Status |
|:-----|:-------|
| **LayerStream speed** | Sub-1.5 tok/s on CPU for larger/hybrid models. `fla`/`causal-conv1d` fast kernels are CUDA-only — CPU uses the pure-PyTorch GatedDeltaNet fallback. |
| **TurboQuant** | Parked. Default-off. 4/4 eval gates failed. See `reviews/eval_gate_*.json`. |
| **FullRAM on low RAM** | Requires enough RAM for the entire model. Use `mode=auto` for automatic engine selection. |
| **Model formats** | Primary: safetensors (transformers). GGUF fallback via llama-cpp-python. BitNet IQ2_BN via ik-llama-cpp-python. |

---

## 🧪 Testing

```bash
# Fast tests (~25-50s)
cd backend && python -m pytest -m "not slow"

# Full tests (includes real-engine round-trip)
cd backend && python -m pytest

# Frontend
cd frontend && node --test lib/maskedLm.test.ts
```

**134 tests** across 17 files (129 fast + 5 slow) covering CLI, SSE streaming, think-strip, fuzzy model match, plugin sandbox, cloud engine, FullRAM executor, engine-factory mode resolution, auth middleware, and OpenAI compat.

---

## 🛡️ Privacy First

![Privacy — Zero data leaves your machine](./Info_docs/assets/privacy.png)

In offline mode (the default), **zero bytes** leave your local machine. All prompts, documents, and chat histories are stored in your local SQLite instance. Cloud mode sends requests only to the provider you configure.

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feat/amazing-feature`)
3. Run tests (`python -m pytest -m "not slow"`)
4. Submit a PR

See [AGENTS.md](AGENTS.md) for architecture details and code conventions.

---

## 📄 License

[MIT](LICENSE) — Built with ❤️ for the Open Source AI Community.

<div align="center">

**[⬆ Back to top](#-sovereignai-edge)**

</div>
