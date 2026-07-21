---
tags: [database, storage, persistence]
source: "[[Docs/SQLite.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# SQLite

SQLite serves as the primary local database for SovereignAI Edge, storing all persistent data in a single `.db` file without requiring any database server. It handles chat history (all conversation messages and sessions), the model registry (available models, paths, and configurations), plugin states (enabled/disabled plugins and their settings), cached hardware detection results, and user preferences.

SQLite's zero-configuration, serverless architecture is a natural fit for a portable offline AI platform. The single-file database can be moved alongside the application on a USB drive, requires no installation or maintenance, and provides ACID compliance with crash recovery. The background scheduler runs periodic VACUUM operations to compact the database file and minimize storage footprint.

## Key Points

- Serverless, zero-configuration, single-file embedded database
- Stores chat history, model registry, plugin states, hardware profiles, and user settings
- ACID-compliant with crash recovery for safe offline operation
- Periodic VACUUM compaction via background scheduler (every 5 min)
- Minimal memory footprint (~250 KB) suitable for constrained environments

## Related
- [[Technical Architecture]]
- [[Schedulers]]
- [[Working Flow]]
