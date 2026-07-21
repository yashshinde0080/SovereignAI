# Electron

A framework for building cross-platform desktop applications using web technologies (Chromium + Node.js).

## Role in SovereignAI Edge

[[Electron]] wraps the SovereignAI Edge web interface into a ==native desktop application==, providing seamless integration with the local operating system:

- **Lifecycle Management:** Starts/stops the Python backend process automatically
- **System Tray:** Background operation with quick-access menu
- **Menu Bar:** Native OS menus for settings and controls
- **IPC Bridge:** Communication between renderer ([[React]]) and main process

## Key Responsibilities

1. **Launcher:** Spawns the [[FastAPI]] backend as a child process
2. **Window Management:** Creates the main application window
3. **Graceful Shutdown:** Handles SIGTERM to cleanly stop inference and close [[SQLite]] connections
4. **Port Discovery:** Passes the backend port to the frontend

## See Also

- [[TRD]] — Technical requirements and stack details
- [[React]] — Frontend UI framework
- [[FastAPI]] — Backend API gateway
- [[Working Flow]] — Boot sequence and session lifecycle
