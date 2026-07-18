# SovereignAI Edge — Documentation Index

> Master navigation for all technical docs in this vault. Docs themselves are unmodified — this file only organizes links.

---

## 🏗 Architecture & Design

| Doc | Purpose |
|-----|---------|
| [technical_architecture.md](technical_architecture.md) | System-wide architecture, data flow, component diagram |
| [engines_overview.md](engines_overview.md) | FullRAM vs LayerStream comparison, selection logic |
| [flowcharts.md](flowcharts.md) | Mermaid diagrams for request flow, engine routing, model load |
| [mindmap.md](mindmap.md) | Visual concept map of all subsystems |
| [prd.md](prd.md) | Product requirements document |
| [trd.md](trd.md) | Technical requirements document |
| [Gaps.md](Gaps.md) | Known gaps, TODOs, technical debt |

---

## ⚙️ Inference Engines

| Doc | Engine | Focus |
|-----|--------|-------|
| [FullRAM.md](FullRAM.md) | FullRAM | Fast path, high-RAM, all weights in memory |
| [LayerStream.md](LayerStream.md) | LayerStream | Low-RAM, layer-by-layer disk swap |
| [engine_algorithms.md](engine_algorithms.md) | Both | Core algorithms: KV cache, attention, sampling |
| [implemented_algorithms.md](implemented_algorithms.md) | Both | What's actually coded vs spec |
| [algorithms.md](algorithms.md) | Both | Algorithm references, formulas |
| [schedulers.md](schedulers.md) | LayerStream | Layer eviction / prefetch scheduling |
| [pipelines.md](pipelines.md) | Both | Inference pipeline stages |
| [KV Cache.md](KV Cache.md) | Both | KV cache management, quantization |
| [GGUF.md](GGUF.md) | Both | GGUF format parsing, metadata |
| [working.md](working.md) | Both | Working notes, debug logs |
| [working_flow.md](working_flow.md) | Both | Step-by-step execution traces |

---

## 🧩 Core Subsystems

| Doc | Subsystem |
|-----|-----------|
| [Hardware Profiler.md](Hardware Profiler.md) | GPU/CPU/RAM detection, auto engine selection |
| [Plugin System.md](Plugin System.md) | Python plugin sandbox, interface, manager |
| [Info Dashboard.md](Info Dashboard.md) | WebSocket metrics, real-time system stats |

---

## 🛠 Tech Stack References

| Doc | Technology |
|-----|------------|
| [FastAPI.md](FastAPI.md) | Backend API framework patterns |
| [Pydantic.md](Pydantic.md) | Settings, schemas, validation |
| [SQLite.md](SQLite.md) | Database schema, aiosqlite patterns |
| [React.md](React.md) | Frontend component patterns (Next.js 16, React 19) |
| [Zustand.md](Zustand.md) | State management stores |
| [Tailwind CSS.md](Tailwind CSS.md) | v4 + shadcn/ui theming |
| [Vite.md](Vite.md) | Build tool config |
| [Electron.md](Electron.md) | Desktop wrapper, IPC, bundling |
| [Hugging Face.md](Hugging Face.md) | Model hub, transformers, safetensors |

---

## 📁 Assets

| File | Use |
|------|-----|
| `assets/dual_engine.png` | Architecture diagram (FullRAM + LayerStream) |
| `assets/hero.png` | Landing page hero image |
| `assets/privacy.png` | Privacy/local-first badge |

---

## 🔍 Quick Links by Task

| Task | Start Here |
|------|------------|
| Understand overall system | [technical_architecture.md](technical_architecture.md) |
| Choose engine for hardware | [engines_overview.md](engines_overview.md) → [Hardware Profiler.md](Hardware Profiler.md) |
| Debug LayerStream layer loading | [LayerStream.md](LayerStream.md) → [schedulers.md](schedulers.md) |
| Add a plugin | [Plugin System.md](Plugin System.md) |
| Extend API | [FastAPI.md](FastAPI.md) → [Pydantic.md](Pydantic.md) |
| Modify UI theme | [Tailwind CSS.md](Tailwind CSS.md) → [React.md](React.md) |
| Package for Electron | [Electron.md](Electron.md) |
| Load GGUF model | [GGUF.md](GGUF.md) → [engine_algorithms.md](engine_algorithms.md) |

---

## 📌 Vault Meta

- **Format**: Obsidian-flavored Markdown (wikilinks supported)
- **Graph**: Enabled — see `.obsidian/graph.json`
- **No edits to source docs** — this index only adds navigation