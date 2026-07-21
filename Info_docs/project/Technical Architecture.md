---
tags: [architecture, technical, system, components]
source: "[[Docs/technical_architecture.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Technical Architecture

The SovereignAI Edge architecture is designed as a monolithic local service composed of decoupled micro-layers, using a client-server model entirely contained within the host machine (127.0.0.1). The Electron or React interface acts as the client, and the bundled Python server acts as the backend API. This design ensures all inference, storage, and API traffic stays on the local machine.

The boot sequence begins with a launcher script (`launch.bat` / `launch.sh`) that validates the environment, maps relative paths from the current execution directory (critical for USB portability), and forks processes for both the FastAPI backend server and the frontend Electron process simultaneously. The FastAPI gateway exposes endpoints for model management, chat completions, streaming, and document operations, with a middleware layer that handles plugin hooks for pre-processing prompts and post-generation tasks.

At the heart of the system is the Inference Core with its engine selectors. The Hardware Profiler examines system resources via psutil and OS-level APIs. If model size times 1.2 is less than available RAM, the model is mapped directly into memory via mmap for FullRAM execution. If memory is insufficient, the system splits the GGUF file into layers and streams them one at a time from disk to RAM, processing the forward pass and evicting each layer before loading the next. The plugin architecture uses dynamic Python importlib, scanning the `./plugins/` directory on startup for hook-registering decorators.

## Key Points

- Monolithic local service with decoupled micro-layers; entirely on 127.0.0.1
- Launch script forks backend (FastAPI) and frontend (Electron) simultaneously
- Hardware Profiler determines FullRAM or LayerStream mode at runtime
- FullRAM uses mmap for direct memory mapping when RAM is sufficient
- LayerStream loads one neural network layer at a time from disk
- Plugin system uses dynamic importlib with hook decorators (pre_prompt, post_generation)

## Related
- [[PRD]] — Product vision and target users
- [[TRD]] — Technical stack and system requirements
- [[Engines Overview]] — FullRAM and LayerStream engine architecture
- [[Working Flow]] — Boot sequence and session lifecycle
- [[Schedulers]] — Task queue and resource allocation
- [[Hardware Profiler]] — Resource analysis and engine selection component
