---
tags: [architecture, overview, mindmap]
source: "[[Docs/mindmap.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Mindmap

The hierarchical mindmap provides a bird's-eye view of the SovereignAI Edge modular monolith, mapping components from the presentation layer down to OS-level tensor execution. Six top-level branches organize the system: UI Interfaces (React web app, Electron desktop wrapper, Python CLI), Backend API (FastAPI app, WebSocket manager, background tasks), Core Logic (llama.cpp bindings, LayerStream core, plugin registry, state manager), Storage (models directory, SQLite database, plugin directory), and Security (hardware bounds, OS sandboxing, data privacy).

This structural overview makes clear that SovereignAI Edge is a vertically integrated system where every layer -- from the CLI to the C++ tensor execution -- is owned and packaged together. Security is treated as a first-class concern with hardware bounds enforcement and sandboxing built into the architecture rather than bolted on.

## Key Points

- Six branches: UI, Backend API, Core Logic, Storage, Security
- All layers are vertically integrated and packaged as a single monolith
- Security spans hardware bounds checking, OS sandboxing, and privacy guarantees
- The mindmap reveals the full scope of the plugin system, state management, and storage subsystems

## Related
- [[Technical Architecture]]
- [[Visuals]]
- [[Engines Overview]]
