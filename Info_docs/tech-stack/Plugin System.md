---
tags: [plugins, extensibility, middleware]
source: "[[Docs/Plugin System.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Plugin System

The Plugin System enables dynamic extension of SovereignAI Edge without modifying core code. Plugins are Python scripts placed in the `./plugins/` directory that register callbacks via decorators such as `@hook('pre_prompt')` and `@hook('post_generation')`. The backend scans the plugins directory on startup and hot-reloads modified scripts periodically (via the background scheduler) without restarting the application.

Use cases include local RAG (injecting retrieved document context into prompts), custom input/output formatting for specific models, safety filters for content moderation, and custom metrics logging. Plugins execute in a sandboxed environment via Python's `importlib`, with hardware bounds and OS sandboxing preventing runaway resource consumption. The plugin interface is defined in `backend/app/plugins/` with built-in plugins for PDF ingestion and code analysis.

## Key Points

- Decorator-based hook registration: `@hook('pre_prompt')`, `@hook('post_generation')`
- Directory scanning and hot-reload without application restart
- Sandboxed execution via Python importlib with hardware resource bounds
- Use cases: RAG injection, custom formatting, safety filters, metrics logging
- Built-in plugins: PDF ingestion, code analysis
- Integrates into the inference pipeline via FastAPI middleware hooks

## Related
- [[FastAPI]]
- [[Technical Architecture]]
- [[Pipelines]]
