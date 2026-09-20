# Database System

SovereignAI Edge uses two separate SQLite databases, both in WAL mode for concurrent reads.

## Database 1: sovereign.db

**Path:** `workspace/database/sovereign.db`
**Managed by:** `DatabaseManager` (`backend/app/database/manager.py`)
**Connection:** `ConnectionPool` — thread-local connections, WAL mode, `synchronous=NORMAL`, `mmap_size=256MB`

### Tables

| Table | Purpose |
|---|---|
| `schema_version` | Tracks migration versions (idempotent, never re-runs) |
| `models` | Model registry (id, name, family, size_label, quant, file_path, checksum, status, engines_supported) |
| `sessions` | Chat session tracking (model_name, engine_mode, tokens, peak_ram) |
| `hardware_profiles` | CPU/RAM/GPU/disk capabilities per profile |
| `documents` | RAG document metadata (filename, chunks, embeddings, status) |
| `plugins` | Installed plugins (entry_point, permissions, signature) |
| `audit_log` | Event log (event_type, severity, source, message) |
| `benchmark_results` | Performance benchmarks (tokens/sec, first_token_latency, peak_ram) |

### Migration System

`MigrationRunner` (`backend/app/database/migrations.py`) — applies SQL migrations in order, tracks `schema_version` table. Each migration is atomic (transaction per version). Never re-runs applied versions.

```
v1: Core tables (models, sessions, hardware_profiles, documents)
v2: Plugins and audit tables
v3: Benchmark results table
```

### ConnectionPool

`ConnectionPool` (`backend/app/database/connection.py`):
- Thread-safe via `threading.local()` — each thread gets its own `sqlite3.Connection`
- WAL mode for concurrent reads
- `PRAGMA synchronous=NORMAL` — balance between durability and speed
- `PRAGMA mmap_size=268435456` — 256MB memory-mapped I/O
- `TransactionContext` — atomic commit/rollback context manager

## Database 2: sovereign_settings.db

**Path:** `workspace/database/sovereign_settings.db`
**Managed by:** `SettingsDatabase` (`backend/app/settings/database.py`)
**Access:** `SettingsService` (`backend/app/settings/service.py`)

### Tables

| Table | Purpose |
|---|---|
| `settings` | JSON blobs per section (general, personalization, data_controls, security, parental_controls, project) |
| `agents` | AI agent configs (name, role, system_instruction, temperature, max_tokens, is_active) |
| `audit_log` | Settings change audit trail |

### Settings Sections

| Section | Key Fields |
|---|---|
| `general` | `startup_model`, `default_mode`, app version |
| `personalization` | `base_style_tone`, `characteristics`, `response_length`, `custom_instructions` |
| `security` | `bind_localhost_only`, `api_token`, `require_password`, `password_hash` |
| `data_controls` | Data retention, export settings |
| `parental_controls` | Content filtering, PIN |
| `project` | Project-level overrides |

### Settings Flow

1. `SettingsDatabase.__init__()` creates tables, inserts defaults for missing sections
2. `SettingsService.get_general()` → `SettingsDatabase.get_section("general")` → returns JSON dict
3. `SettingsService.get_system_prompt()` — builds system prompt from personalization + active agent
4. Security cache: `_security_cache` avoids repeated DB reads for auth middleware

## Database Cleanup

- `DatabaseManager.shutdown()` → `checkpoint()` (WAL flush) → `close_all()` (thread connections)
- `SessionsTable.mark_crashed_sessions()` — marks orphaned active sessions from crashes
- `DatabaseManager.vacuum()` — reclaim space after large deletes

## Related

- [[00-architecture-overview]] — Where DBs fit in the architecture
- [[08-settings-system]] — Settings service and schemas
- [[09-security]] — Auth middleware reads settings DB
- [[02-chat-api-flow]] — Chat uses sessions table
