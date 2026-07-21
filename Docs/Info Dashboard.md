# SovereignAI Edge — Info Dashboard

This vault documents the ==SovereignAI Edge== platform: a ==portable==, ==100% offline== AI system running LLMs on consumer hardware via ==dual-engine== architecture.

## Core Documents

| Doc     | What it covers                                      |
| ------- | --------------------------------------------------- |
| [[PRD]] | Product vision, target users, feature list          |
| [[TRD]] | Tech stack, system requirements, portability layout |

## Architecture & Engines

| Doc | What it covers |
|-----|---------------|
| [[Technical Architecture]] | System layers, component interactions, deployment |
| [[Engines Overview]] | Deep-dive: ==FullRAM== vs ==LayerStream==, trade-offs |
| [[Engine Algorithms]] | Pseudocode for both engines, math formulas |
| [[Algorithms]] | Core adaptive memory + LayerStream algorithms |
| [[Implemented Algorithms]] | 25 algorithms across NLP, RAG, memory, frontend |

## Execution Flow

| Doc | What it covers |
|-----|---------------|
| [[Working]] | State machine: UNINITIALIZED → READY_IDLE → INFERENCING |
| [[Working Flow]] | Boot sequence → session → shutdown, sequence diagrams |
| [[Flowcharts]] | Model init, request handling, error flowcharts |
| [[Pipelines]] | End-to-end inference pipeline: ingestion → streaming |
| [[Schedulers]] | Job queue, worker pool, background tasks |

## Visuals & Maps

| Doc | What it covers |
|-----|---------------|
| [[Visuals]] | ASCII architecture, engine selection, double-buffering |
| [[Mindmap]] | Hierarchical component mindmap |
| [[Gaps]] | 15 research gaps in memory-constrained LLM inference |

## Cross-Reference Map

```text
PRD ──→ TRD ──→ Technical Architecture
                      │
          ┌───────────┼───────────┐
          v           v           v
  Engines Overview  Pipelines  Schedulers
          │           │
          v           v
  Engine Algorithms  Algorithms
          │           │
          └──→ Implemented Algorithms
```

## ==Key Concepts==

- **==FullRAM==** — Load entire model into VRAM/RAM. Max speed. Needs 16GB+.
- **==LayerStream==** — Load one layer at a time from disk. Runs 70B models on 8GB RAM.
- **==Dual-Engine==** — Hardware profiler auto-selects FullRAM or LayerStream at runtime.
- **==Portable==** — Runs from USB. All paths relative. No registry/install needed.
- **==Offline==** — 100% local. No telemetry. Zero bytes leave the machine.
- **==Plugin System==** — Python `importlib`-based hooks for RAG, pre/post processing.

## Technology Stack Nodes

| Technology | Role in Stack |
|------------|---------------|
| [[FastAPI]] | Backend API gateway and router |
| [[React]] | Frontend user interface framework |
| [[Electron]] | Desktop application shell |
| [[SQLite]] | Local database for persistence |
| [[Pydantic]] | Data validation and schemas |
| [[Zustand]] | Frontend state management |
| [[Tailwind CSS]] | Utility-first styling framework |
| [[Vite]] | Frontend build tool and dev server |
| [[Hugging Face]] | ML transformers and tokenizers |
| [[GGUF]] | Model weight file format |
| [[KV Cache]] | Memory optimization for inference |
| [[LayerStream]] | Low-memory inference engine |