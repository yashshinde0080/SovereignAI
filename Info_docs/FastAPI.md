# FastAPI

A modern, high-performance web framework for building APIs with Python 3.7+ based on standard Python type hints.

## Role in SovereignAI Edge

[[FastAPI]] serves as the ==backend API gateway== for SovereignAI Edge. It handles all REST and WebSocket communication between the frontend interfaces and the inference core:

- **REST Endpoints:** `GET /models`, `POST /chat`, `GET /status`
- **WebSocket Streaming:** Real-time token delivery via `WS /api/stream`
- **Plugin Integration:** Middleware hooks for pre/post-processing via the [[Plugin System]]
- **Validation:** Request payload validation via [[Pydantic]] models

## Key Features

- **Async-native:** Built on `asyncio` for non-blocking I/O during inference
- **Auto-generated Docs:** Swagger UI at `/docs` for debugging
- **Dependency Injection:** Clean service layer separation

## See Also

- [[TRD]] — Technical requirements and stack details
- [[Technical Architecture]] — System layers and component interactions
- [[Pydantic]] — Data validation models
- [[React]] — Frontend UI framework
- [[Electron]] — Desktop application shell
