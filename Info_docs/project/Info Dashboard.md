---
tags: [dashboard, index, overview, vault-map]
source: "[[Docs/Info Dashboard.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Info Dashboard

The Info Dashboard serves as the entry point and navigation hub for the SovereignAI Edge Obsidian vault. It documents the full platform: a portable, 100% offline AI system that runs large language models on consumer hardware via a dual-engine architecture. The dashboard organizes vault documents into logical groups covering core product documents, architecture and engine deep-dives, execution flow documentation, and visual concept maps.

Core documents include the [[PRD]] (product vision, target users, feature list) and [[TRD]] (tech stack, system requirements, portability layout). Architecture and engine coverage includes [[Technical Architecture]] (system layers and component interactions), [[Engines Overview]] (FullRAM vs LayerStream deep-dive with trade-offs), [[Engine Algorithms]] (pseudocode and formulas), and [[Implemented Algorithms]] (25 algorithms across NLP, RAG, memory, and frontend). Execution flow documentation covers session state machines, boot sequences, request handling flowcharts, end-to-end inference pipelines, and scheduler designs.

The vault also provides a cross-reference map showing how PRD feeds into TRD which feeds into Technical Architecture, which in turn branches into Engines Overview, Pipelines, and Schedulers. Key concepts highlighted throughout the vault include FullRAM (max speed, 16GB+ needed), LayerStream (one layer at a time, runs 70B models on 8GB), dual-engine auto-selection via the hardware profiler, USB portability with relative paths, 100% offline operation with no telemetry, and a Python importlib-based plugin system.

## Key Points

- Central navigation hub for the entire Obsidian documentation vault
- Cross-reference map shows document relationships: PRD -> TRD -> Technical Architecture -> Engines Overview / Pipelines / Schedulers
- References 12 technology stack nodes with their roles (FastAPI, React, Electron, SQLite, Pydantic, etc.)
- Key concepts: FullRAM, LayerStream, Dual-Engine, Portable, Offline, Plugin System
- Links to all major documentation areas including visuals, mindmap, flowcharts, and gaps

## Related
- [[PRD]] — Product vision and target users
- [[TRD]] — Technical stack and system requirements
- [[Technical Architecture]] — System layers and component interactions
- [[Hardware Profiler]] — Resource analysis and engine selection component
- [[Engines Overview]] — Deep-dive into both inference engines
- [[Gaps]] — Research gaps in memory-constrained inference
