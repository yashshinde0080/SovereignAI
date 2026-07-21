---
tags: [desktop, shell, packaging]
source: "[[Docs/Electron.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Electron

Electron wraps the SovereignAI Edge web interface into a native desktop application, providing seamless integration with the local operating system. It manages the full application lifecycle: spawning the FastAPI backend as a child process, creating the main application window, handling graceful shutdown via SIGTERM (halting inference, unmapping GGUF bindings, closing SQLite connections), and discovering and passing the backend port to the frontend.

Electron adds native OS features including a system tray for background operation with a quick-access menu, native menu bars for settings and controls, and IPC bridges for communication between the renderer (React) and the Electron main process. Desktop builds target Windows (electron-builder), macOS, and Linux.

## Key Points

- Wraps the React frontend in a Chromium-based native desktop shell
- Spawns and manages the FastAPI backend as a child process
- System tray for background operation and quick-access menu
- Graceful shutdown: SIGTERM halts inference, unmaps GGUF files, closes SQLite
- Port discovery passes the backend port from FastAPI to the frontend
- Cross-platform builds via electron-builder (Win, Mac, Linux)

## Related
- [[FastAPI]]
- [[React]]
- [[Technical Architecture]]
- [[Working Flow]]
