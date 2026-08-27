# 🛡️ SovereignAI Edge
[![License](https://img.shields.io/github/license/SovereignAI/Edge)](LICENSE)
[![Stars](https://img.shields.io/github/stars/SovereignAI/Edge)](https://github.com/SovereignAI/Edge/stargazers)

![SovereignAI Edge Hero](./Info_docs/assets/hero.png)

> **The Ultimate Portable, 100% Offline AI Platform.**  
> Run large language models (LLMs) locally on consumer-grade hardware or directly from external drives (USB/SSD). No cloud, no telemetry, no compromise.

---

## 📚 Table of Contents

- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Performance](#-performance-the-dual-engine-advantage)
- [File System Layout](#-file-system-layout)
- [Quick Start](#-quick-start)
- [Privacy First](#-privacy-first)
- [OpenAI-Compatible API](#-openai-compatible-api)
- [Known Limitations](#-known-limitations)
- [Contributing](#-contributing)
- [License](#-license)
## 🚀 Key Features

| Feature | Description |
| :--- | :--- |
| **Dual Engines** | **FullRAM** for blazing speed, **LayerStream** for low-memory systems (8GB+). |
| **Fully Offline** | Operates in total isolation. No internet dependency after initial setup. |
| **Portable** | Zero-configuration execution from any NVMe/SSD or Flash drive. |
| **Extensible** | Powerful Python-based **Plugin System** for custom logic and RAG. |
| **Interfaces** | Choose between a modern **React Web UI**, **Electron Desktop App**, or **CLI**. |

---

## 🛠️ System Architecture

SovereignAI Edge is built with a decoupled micro-layer architecture for maximum portability and performance.

```mermaid
graph TB
    subgraph UI ["Client Layer"]
        ReactUI["React Web UI"]
        Electron["Electron Desktop"]
    end

    subgraph Backend ["Backend Core"]
        FastAPI["FastAPI / Uvicorn"]
        PluginMgr["Plugin Engine"]
    end

    subgraph Engine ["Inference Engine"]
        Direction{Hardware Check}
        FullRAM["FullRAM Mode"]
        LayerStream["LayerStream Mode"]
    end

    UI --> Backend
    Backend --> Engine
    Direction -- High RAM --> FullRAM
    Direction -- Low RAM --> LayerStream
```
Architecture layers: UI→FastAPI backend→Engine (FullRAM or LayerStream). Plugin manager loads extensions; vector store supplies RAG embeddings.

---

## ⚡ Performance: The Dual-Engine Advantage

![Dual Engine Comparison](./Info_docs/assets/dual_engine.png)

### 1. FullRAM Engine
Loads the entire model checkpoint into active memory. Best for systems with high VRAM/RAM (e.g., NVIDIA RTX series, Apple Silicon).

### 2. LayerStream Engine
A fallback engine that iteratively loads and unloads individual neural network layers from Disk to RAM, so models larger than free RAM still run. Sweet spot: **3-8B Q4 models on 8GB RAM** (measured: 1.9GB model → 2.3GB peak RSS). Large models (70B+) run but slowly — see [reviews/benchmark-2026-08-14.md](reviews/benchmark-2026-08-14.md) for honest numbers.

### Benchmarks

| Model | Mode | Tokens/s |
|-------|------|----------|
| Qwen2-0.5B (int4) | FullRAM | 0.85 |
| Qwen3.5-0.8B (int4) | LayerStream | 0.40 |
---

## 📦 File System Layout

```text
SovereignAI/
├── 📁 backend/       # FastAPI & Inference Logic (Python 3.10+, PyTorch/transformers)
├── 📁 frontend/      # Next.js 16 + React 19 (static export, no Vite)
├── 📁 electron/      # Desktop Wrapper
├── 📁 models/        # Place your .gguf models here
├── 📁 plugins/       # Custom Python plugins
└── 📁 database/      # SQLite History & User Configs
```

---

## 🏁 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- 8GB+ RAM (Recommended)

### Execution
1. **Clone the repository**
2. **Launch the platform:**
   - **Windows:** Run `launch.bat`
   - **Linux/macOS:** Run `./launch.sh`

### Installation

1. Install backend deps: `cd backend && pip install -r requirements.txt`
2. Install frontend deps: `cd frontend && npm ci`
3. Install electron deps (optional): `cd electron && npm ci`
4. Configure env (optional): create `.env` with `SOVEREIGN_BIND_LOCALHOST_ONLY=false` for remote access.
---

## 🛡️ Privacy First

![Privacy Shield](./Info_docs/assets/privacy.png)

SovereignAI Edge ensures that **zero bytes** leave your local machine. All prompts, documents, and chat histories are stored in your local encrypted SQLite instance.

---

## 🔌 OpenAI-Compatible API

`POST http://127.0.0.1:8000/v1/chat/completions` is a drop-in OpenAI
`/chat/completions` endpoint — any OpenAI SDK/client works by pointing
`base_url` at it (no API key needed on localhost).

**Supported request params:** `messages`, `model`, `max_tokens`, `temperature`,
`top_p`, `stream`, `use_rag`, `enable_thinking`.

**Extension:** thinking-mode models stream reasoning in
`choices[0].delta.reasoning` alongside `content`; standard OpenAI clients
ignore the extra key. Shapes are pinned by
`backend/tests/test_openai_compat.py`.

---

## ⚠️ Known Limitations

| Area | Status |
|------|--------|
| **LayerStream speed** | Sub-1 tok/s on CPU (measured 0.40 tok/s on Qwen3.5-0.8B). GPU path blocked on Windows — no `causal-conv1d` wheel. |
| **TurboQuant** | Parked. Default-off (`turboquant_enabled=false`). 4/4 eval gates failed on Qwen2-0.5B and Pythia-70m. See `reviews/eval_gate_*.json`. |
| **FullRAM on low RAM** | Requires enough RAM to hold the entire model. No automatic fallback to LayerStream on OOM — use `mode=auto` in the load request. |
| **Model formats** | Primary: safetensors via HuggingFace transformers. GGUF supported as fallback via llama-cpp-python. BitNet IQ2_BN requires ik-llama-cpp-python. |

---

<p align="center">
## 🤝 Contributing

We welcome contributions. Fork repo, create feature branch, run tests (`python -m pytest -m "not slow"`). Submit PR.

## 📄 License

MIT License. See `LICENSE` file.
  Built with ❤️ for the Open Source AI Community.
</p>
