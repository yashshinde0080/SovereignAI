---
tags: [prd, product, requirements, vision]
source: "[[Docs/prd.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# PRD

SovereignAI Edge is a fully portable, 100% offline AI platform that runs large language models on consumer-grade hardware or directly from external drives (USB/SSD). It eliminates cloud dependency entirely, guaranteeing data privacy, security, and accessibility in air-gapped environments. The platform targets privacy-conscious individuals, enterprise and defense organizations operating in air-gapped environments, researchers needing localized AI without API costs, and digital nomads in low-connectivity areas.

The product delivers zero-internet operations through fully local execution across frontend UI, backend API, and inference engine -- all running over localhost with all dependencies pre-packaged. Its defining feature is a dual execution engine system: the FullRAM engine loads entire model checkpoints into active memory for maximum tokens-per-second speed when sufficient RAM/VRAM is available, while the LayerStream engine provides a fallback for low-memory systems by iteratively loading and unloading individual neural network layers from NVMe/SSD, enabling 70B+ parameter models on systems with as little as 8GB RAM.

The platform offers three interfaces -- an Electron desktop application, a React web UI accessible via browser on the local network, and a CLI for power users and scripting. Extensibility comes through a plugin system supporting custom Python scripts (for local RAG, custom prompts, local archive search) and model agnosticism via the GGUF format, accepting Llama, Mistral, Gemma, and other model variants. Chat histories and configurations are saved locally via SQLite, and the system enforces strict no-telemetry policies.

## Key Points

- Fully portable: runs from USB/SSD without leaving registry keys or configuration files on the host OS
- Dual execution engines: FullRAM (high-memory) and LayerStream (low-memory) with automatic selection
- Three interfaces: Electron desktop, React web UI, and CLI
- Extensible via Python plugin system and GGUF model format
- Cross-platform: Windows, macOS (M-series and Intel), and Linux
- No telemetry, no internet required, zero bytes leave the machine

## Related
- [[TRD]] — Technical requirements and stack details
- [[Technical Architecture]] — System layers and component interactions
- [[Engines Overview]] — Deep-dive into FullRAM and LayerStream engines
- [[Gaps]] — Research gaps addressed by this platform
