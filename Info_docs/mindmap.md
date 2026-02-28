# Hierarchical Mindmap

## 1. Structural Overview
The mindmap details the vast scale and modular architecture of SovereignAI Edge. Because the platform acts as a monolith, mapping out its components visualizes responsibilities from the presentation layer down to OS-level tensor execution.

## 2. Detailed Mindmap Visual Structure
```text
========================================================================
                          [ SovereignAI Edge ]
                          (Core Platform Hub)
========================================================================
       |                         |                          |
+------v------+            +-----v-----+              +-----v------+
| UI Interfaces |            | Backend API |              | Core Logic |
+------+------+            +-----+-----+              +------+-------+
       |                         |                           |
       +--> React Web App        +--> FastAPI App            +--> Llama.cpp Bindings
       |    - React Context      |    - Models Router        |    (FullRAM Execution)
       |    - Tailwind CSS       |    - Chat Router          |
       |    - Vite Bundler       |    - Settings Router      +--> LayerStream Core
       |                         |                           |    (Sequential SSD I/O)
       +--> Desktop Wrapper      +--> Websocket Mgr          |
       |    - Electron.js        |    - Real-time Stream     +--> Plugin Registry
       |    - IPC Bridge         |    - Connection Pools     |    - Hook Injection
       |                         |                           |    - Local Search Sim
       +--> Python CLI           +--> Background Tasks       |
            - Curses UI               - DB Garbage Collect.  +--> State Manager
            - Headless Mode           - Log Rotation              - SQLite Connector
                                                                  - Config Parser

                      |                            |
                 +----v----+                  +----v-----+
                 | Storage |                  | Security |
                 +----+----+                  +----+-----+
                      |                            |
                      +--> ./models/               +--> Hardware Bounds
                      |    (GGUF/Bin weights)      |    (Memory protection caps)
                      |                            |
                      +--> ./database/             +--> OS Sandboxing 
                      |    (SQLite db file)        |    (No reverse shells)
                      |                            |
                      +--> ./plugins/              +--> Data Privacy
                           (Custom py scripts)          (0 bytes leave localhost)
```
