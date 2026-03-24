# SovereignAI Edge: System Visuals & Architecture Diagrams
> **Status:** Senior System Designer View
> **Note:** These diagrams use standard ASCII box-drawing characters for maximum compatibility across terminals and text editors.

---

## 1. High-Level System Architecture
The SovereignAI Edge platform is built on a "Local-First, Decoupled-Compute" model. It treats the host machine as a self-contained cloud environment.

```text
+-----------------------------------------------------------------------+
|                         SovereignAI Edge System                       |
+-----------------------------------------------------------------------+
|                                                                       |
|   +-------------------+          +------------------------------+     |
|   |   USER INTERFACE  |          |       BACKEND GATEWAY        |     |
|   |   (Electron App)  |          |          (FastAPI)           |     |
|   +---------+---------+          +--------------+---------------+     |
|             |                                   ^                     |
|             |       REST / WebSocket            |                     |
|             +-----------------------------------+                     |
|             |        (127.0.0.1:PORT)           |                     |
|             v                                   v                     |
|   +-------------------+          +------------------------------+     |
|   |   REACT FRONTEND  |          |      CORE INFERENCE ENGINE   |     |
|   |   (States/UI)     |          |      (Llama.cpp / Torch)     |     |
|   +-------------------+          +--------------+---------------+     |
|                                                 |                     |
|                                     +-----------+-----------+         |
|                                     |                       |         |
|                        +------------v-----------+  +--------v-------+ |
|                        |     FullRAM Engine     |  |  LayerStream   | |
|                        | (High Perf / VRAM)     |  | (Low RAM / SSD)| |
|                        +------------+-----------+  +--------+-------+ |
|                                     |                       |         |
|                                     +-----------+-----------+         |
|                                                 |                     |
|   +---------------------------------------------v-----------------+   |
|   |                  FILESYSTEM / HARDWARE LAYER                  |   |
|   |  +------------+    +------------+    +---------------------+  |   |
|   |  | GGUF Models|    | SQLite DB  |    | Plugins / Middleware|  |   |
|   |  +------------+    +------------+    +---------------------+  |   |
|   +---------------------------------------------------------------+   |
|                                                                       |
+-----------------------------------------------------------------------+
```

---

## 2. The Decision Logic (Engine Selection)
A critical feature of the platform is its "Hardware Awareness." Before any inference starts, the system profiles the host machine to choose the optimal execution path.

```text
       [ START INFERENCE REQUEST ]
                    |
                    v
        +-----------------------+
        |   Hardware Profiler   | <--- Query psutil / NVML (VRAM)
        +-----------+-----------+
                    |
           +--------v---------+
           |  Is Model Size   |
           |  < 80% Avail RAM?|
           +--------+---------+
                    |
          +---------+---------+
          |                   |
    [ YES: FullRAM ]    [ NO: LayerStream ]
          |                   |
  +-------v-------+   +-------v-------+
  | MAP ALL TENSORS |   | INIT SCAFFOLD |
  | INTO VRAM/RAM   |   | (Empty Weights)|
  +-------+-------+   +-------+-------+
          |                   |
          +---------+---------+
                    |
          [ EXECUTE FORWARD PASS ]
```

---

## 3. LayerStream Engine: Deep Dive
The LayerStream engine enables running massive models (e.g., 70B) on low-memory hardware (e.g., 8GB RAM) by treating the SSD as virtualized layer memory.

```text
 PHYSICAL DISK (SSD)             SYSTEM RAM (Inference Loop)
+-------------------+          +-------------------------------------+
| [Model Shards]    |          |                                     |
|                   |          |  1. LOAD LAYER N (e.g. Layer 5)     |
| +---------------+ |  Streaming  +------------+                      |
| | Layer 1 (.saf)| | ---------> | [ ACTIVE ] |                      |
| +---------------+ |     IO     | [ TENSOR ] |                      |
| | Layer 2 (.saf)| |            +-----+------+                      |
| +---------------+ |                  |                             |
| | ...           | |          2. PROCESS HIDDEN STATE               |
| +---------------+ |                  |                             |
| | Layer N (.saf)| |          3. UPDATE KV CACHE                    |
| +---------------+ |                  |                             |
|                   |          4. PURGE LAYER N (Free RAM)           |
+-------------------+                  |                             |
                                       +--------------> 5. REPEAT    |
                                                           FOR N+1   |
                               +-------------------------------------+
```

---

## 4. The End-to-End Inference Pipeline
This diagram traces the lifecycle of a token from the user's keystroke to the UI update.

```text
    USER          FRONTEND (REACT)         BACKEND (FASTAPI)         INFERENCE CORE
     |                |                       |                       |
     |--- "Hello" --->|                       |                       |
     |                |--- POST /chat ------> |                       |
     |                |                       |--- Pre-Process Plugins|
     |                |                       |                       |
     |                |--- Format Template -->|                       |
     |                |                       |                       |
     |                |<-- 200 OK (Stream) ---|                       |
     |                |                       |<-- Load Engine -------|
     |                |                       |                       |
     |                |     [ TOKEN LOOP START ]                      |
     |                |                       |                       |
     |                |                       |<-- Forward Pass ------|
     |                |                       |                       |
     |                | <--- {token: "Hi"} ---|                       |
     |<- Display "Hi"-|                       |                       |
     |                |                       |                       |
     |                |     [ TOKEN LOOP END ]                        |
     |                |                       |                       |
     |                |                       |--- Post-Process Plugins
     |                |                       |                       |
     |                |                       |--- Write SQLite ------|
     |                | <--- {event: "done"} -|                       |
```

---

## 5. Deployment Structure (USB Portability)
How SovereignAI Edge maintains "Zero-Configuration" portability across different host environments.

```text
---

## 6. LayerStream Double-Buffering (Algorithm 16)
To hide disk latency, LayerStream utilizes a "Ping-Pong" double-buffering technique. While Layer N is being processed by the CPU/GPU, Layer N+1 is being pre-emptively loaded from the SSD.

```text
       [ SYSTEM RAM ]                   [ NVMe SSD / DISK ]
+---------------------------+        +-----------------------+
|                           |        |                       |
|  +---------------------+  |        |  +-----------------+  |
|  |   BUFFER A (Active) |  | <----------|   Layer N       |  |
|  |   [ Computing... ]  |  |  (IO)  |  +-----------------+  |
|  +----------+----------+  |        |                       |
|             |             |        |  +-----------------+  |
|             v             |  +---------|   Layer N+1     |  |
|  +----------+----------+  |  |     |  +-----------------+  |
|  |   BUFFER B (Wait)   |  | <+     |                       |
|  |   [ Pre-Loading ]   |  |        |        (...)          |
|  +---------------------+  |        +-----------------------+
|                           |
|      [ HIDDEN STATE ] ----+----> [ LOGITS / SAMPLER ]
+---------------------------+
```

---

## 7. Context Window Sliding (Algorithm 26)
When the conversation exceeds the maximum token limit, the system employs "Anchor-Pinning" and "KV-Sliding" to maintain continuity without crashing.

```text
[ INITIAL CONTEXT WINDOW ]
+-------------------------------------------------------------+
| System Prompt |  Chat Turn 1  |  Chat Turn 2  |  Chat Turn 3 |
| (Pinned 512t) | (Token IDs)   | (Token IDs)   | (Available)  |
+-------------------------------------------------------------+
      ^                                               ^
      |                                               |
[ PINNED ANCHOR ]                             [ CURRENT HEAD ]


[ EXCEEDED LIMIT - SLIDING TRIGGERED ]
+-------------------------------------------------------------+
| System Prompt | [ PRUNED ] |  Chat Turn 2  |  Chat Turn 3   |
| (Pinned 512t) | (Discarded)| (New History) | (New Generation)|
+-------------------------------------------------------------+
      |               |               ^               ^
      +---------------+---------------+---------------+
                      |
              [ KV CACHE SHIFTED ]
```

---

## 8. Data Flow Matrix (Senior Designer View)
A summary of how data types move through the different system components.

| Component      | Primary Data Input | Transformation Logic | Primary Data Output |
| :------------- | :----------------- | :------------------- | :------------------ |
| **Electron**  | User Keystrokes    | IPC / Process Mgmt   | UI State Updates   |
| **FastAPI**   | UI JSON Payloads   | Plugin Hook Routing  | WS / SSE Stream     |
| **Profiler**  | OS Syscalls        | Comparison Logic     | Engine Choice (ID)  |
| **Tokenizer** | UTF-8 String       | Vocabulary Mapping   | Int32 Token Tensors |
| **Inference** | Hidden States      | Matrix Dot-Product   | Logit Probability   |
| **Sampler**   | Logit Tensors      | Temp/Top-P/Top-K     | Scalar Token ID     |
| **SQLite**    | Chat Chunks        | SQL INSERT / UPDATE  | Chat Search Index   |

---

## 9. Deployment Structure (USB Portability)
How SovereignAI Edge maintains "Zero-Configuration" portability across different host environments.

```text
[ ROOT ]
|-- launch.bat/sh        <-- Entry point (Resolves relative paths)
|-- .env.local           <-- Dynamic environment config
|
|-- [ bin ]              <-- Bundled Binaries
|   |-- python_env/      <-- Embedded Python (No host install needed)
|   |-- node_runtime/    <-- Embedded Node (For UI)
|
|-- [ core ]             <-- Source Code (Backend/Frontend)
|   |-- backend/
|   |-- frontend/
|
|-- [ data ]             <-- Persistent Storage
|   |-- sovereign.db     <-- SQLite (History, Settings)
|   |-- [ models ]       <-- .gguf files
|   |-- [ plugins ]      <-- Custom hooks
|   |-- [ cache ]        <-- KV Cache and Layer Shards
```

