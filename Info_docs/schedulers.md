# System Schedulers

## 1. Overview
A completely local and portable LLM execution environment has significant resource contention. Schedulers manage queue prioritization, allocate compute resources (CPU threads/GPU VRAM), and choreograph background processes like database compaction or plugin execution.

## 2. The Core Request Queue (Job Manager)
If multiple API requests hit the backend simultaneously (e.g., from different browser tabs on the same local machine), running them strictly in parallel would cause catastrophic out-of-memory errors and thermal throttling.

**Scheduling Pattern:**
1. Incoming requests enter an asynchronous ==FIFO== (First-In-First-Out) queue.
2. The orchestrator checks if the inference thread is `IDLE`.
3. If `IDLE`, the request at index `0` is popped and processed.
4. If `BUSY`, incoming requests are held with an HTTP `202 Accepted` status until yielding text.

## 3. Worker Thread Pool
Models running in CPU mode heavily utilize ==OpenMP== thread pooling.
- **Allocation Rule:** The scheduler queries `os.cpu_count(logical=False)` and allocates `Max_Cores - 1` to the Llama.cpp backend. Reserving 1 core ensures the OS and API remain responsive for canceling tasks.

## 4. Background Schedulers
A lightweight `apscheduler` framework manages non-blocking tasks.
- **Every 5 minutes:** Database compaction (vacuum) on [[SQLite]] to minimize file footprint.
- **On Startup / Every hour (if allowed):** Plugin registry scan for modified `.py` scripts to trigger hot-reloading without restarting the app.

## 5. Request Scheduling Flow Visual
```text
  Local Net 
  +---------+   +---------+   +---------+
  | Client A|   | Client B|   | Script C|
  +----+----+   +----+----+   +----+----+
       |             |             |
       v             v             v
  +-------------------------------------+
  |          API Entry Point            |
  +------------------+------------------+
                     |
  [ Enqueue Request: Priority via Config]
                     |
            +--------v--------+
            |  Job FIFO Queue | (Stores prompt payload)
            +--------+--------+
                     |
         +-----------v-------------+
         | Inference Task Manager  |
         |                         |
         | Is Engine `IDLE`?       |
         | -> YES: Pop from Queue  |
         | -> NO:  Hold Request    |
         +-----------+-------------+
                     | (Locks Engine State: BUSY)
         +-----------v-------------+
         | Llama.cpp Engine Loop   | (Returns Tokens)
         +-------------------------+
                     | (Completes, Sets State: IDLE)
                     v
             [ Serve Result ]
```

## See Also
- [[Working]] — State machine and core operational states
- [[Pipelines]] — End-to-end inference pipeline
- [[Technical Architecture]] — System layers and component interactions
