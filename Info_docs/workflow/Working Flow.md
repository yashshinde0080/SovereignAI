---
tags: [architecture, lifecycle, boot]
source: "[[Docs/Working Flow.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Working Flow

The application follows a cold-boot-to-active-session lifecycle designed for zero-configuration offline deployment. Execution begins when a user double-clicks `launch.bat` (Windows) or `./launch.sh` (Linux/Mac). The launch script validates embedded Python and Node binaries, maps working directories, then starts the FastAPI backend on a random open port between 8000 and 8080. Once the backend reports ready, the Electron shell (or web browser) opens the React frontend, which queries `GET /status` to confirm hardware readiness and loaded models.

During an active session, the user selects a model and submits a prompt. The frontend opens a WebSocket connection to `/api/stream`, the backend loads the model if needed, formats the prompt against the model's template, and pipes it to the C++ inference core. Tokens stream back one-by-one over the WebSocket, where React renders them incrementally using markdown parsing. On completion, the backend writes the chat history to SQLite and signals `event: done`.

## Key Points

- Boot sequence: launch script validates dependencies, starts FastAPI on a random port, then launches Electron
- Active session: user prompt triggers WebSocket stream, tokens render incrementally in React
- Graceful shutdown: SIGTERM halts inference, unmaps GGUF bindings, and closes SQLite cleanly
- Frontend-backend communication flows through REST (status), WebSocket (streaming), and SSE (state changes)

## Related
- [[Working]]
- [[Technical Architecture]]
- [[Pipelines]]
- [[Electron]]
- [[FastAPI]]
