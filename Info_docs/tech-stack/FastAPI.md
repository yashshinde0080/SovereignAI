---
tags: [backend, api, framework]
source: "[[Docs/FastAPI.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# FastAPI

FastAPI serves as the backend API gateway for SovereignAI Edge, handling all REST and WebSocket communication between the frontend interfaces and the inference core. Built on Python's `asyncio`, it provides non-blocking I/O that is essential for streaming tokens during generation without blocking other API calls. The framework auto-generates Swagger documentation at `/docs` for debugging, uses dependency injection for clean service-layer separation, and integrates tightly with Pydantic for request/response validation.

Key endpoints include `GET /models` for listing available models, `POST /chat` for chat completions, `GET /status` for hardware readiness, and WebSocket `/api/stream` for real-time token delivery. FastAPI also serves as the middleware integration point for the plugin system, allowing pre- and post-processing hooks to execute during the request lifecycle.

## Key Points

- Async-native framework enabling concurrent request handling during streaming inference
- Auto-generated OpenAPI/Swagger docs at `/docs` route
- Dependency injection system for clean separation of service logic
- Pydantic integration provides zero-cost request/response validation
- All backend API routes live under `/v1/*` prefix

## Related
- [[Pydantic]]
- [[Technical Architecture]]
- [[React]]
- [[Electron]]
- [[Plugin System]]
