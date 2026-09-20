# Settings System

Per-section CRUD backed by SQLite. Security settings power auth middleware. Personalization settings build the system prompt.

## Architecture

```
SettingsService (backend/app/settings/service.py)
  → SettingsDatabase (backend/app/settings/database.py)
    → sovereign_settings.db (SQLite, WAL mode)
```

## Settings Sections

| Section | Schema Class | Key Fields |
|---|---|---|
| `general` | `GeneralSettings` | `startup_model`, `default_mode`, `app_version` |
| `personalization` | `PersonalizationSettings` | `base_style_tone`, `characteristics`, `response_length`, `headers_lists_mode`, `preferred_name`, `profession`, `user_context`, `custom_instructions` |
| `data_controls` | `DataControlsSettings` | Data retention, export settings |
| `security` | `SecuritySettings` | `bind_localhost_only`, `api_token`, `require_password`, `password_hash` |
| `parental_controls` | `ParentalControlsSettings` | Content filtering, `pin_hash`, `require_pin_for_settings` |
| `project` | `ProjectSettings` | Project-level overrides |

## Settings Database

`SettingsDatabase` (`backend/app/settings/database.py`):

### Tables

```sql
settings (section TEXT PRIMARY KEY, data TEXT, updated_at TIMESTAMP)
agents (id TEXT PRIMARY KEY, name, role, system_instruction, is_active, temperature, max_tokens, ...)
audit_log (id INTEGER PRIMARY KEY, action, section, details, timestamp)
```

### Operations

- `get_section(section)` → JSON dict
- `update_section(section, data)` → UPSERT + audit log
- `reset_all()` → restore all sections to defaults + delete/reset agents

### Defaults

`FullSettings()` pydantic model provides defaults. On init, missing sections are inserted.

## System Prompt Builder

`SettingsService.get_system_prompt()` assembles a system prompt from:

1. **Base style** — `Respond in a {style} style.` (professional/casual/etc.)
2. **Characteristics** — `Be {creative, technical, ...} in your responses.`
3. **Headers/lists mode** — always/never/minimal usage guidance
4. **Response length** — short/long/detailed
5. **User context** — preferred_name, profession, user_context
6. **Custom instructions** — free-form text
7. **Active agent** — `--- Agent Role: {name} ---\n{system_instruction}`

This prompt is injected into every chat request (prepended to existing system message or inserted as first message).

## Password System

- `set_password(password)` → bcrypt hash stored in `security.password_hash`
- `verify_password(password)` → `bcrypt.checkpw()`
- Security cache (`_security_cache`) avoids repeated DB reads

## Parental Controls

- `set_parental_pin(pin)` → bcrypt hash in `parental_controls.pin_hash`
- `verify_parental_pin(pin)` → bcrypt check
- `require_pin_for_settings` gate

## Agents

Default agents loaded from `backend/app/settings/defaults.py`:
- Pre-configured agent personas (coder, writer, analyst, etc.)
- One active at a time (`is_active` flag)
- `activate_agent(id)` → deactivate all, set one active
- Agent's `system_instruction` appended to system prompt

## API Router

`backend/app/settings/router.py` — CRUD endpoints for all sections:
- `GET /v1/settings/{section}` — get section
- `PUT /v1/settings/{section}` — update section
- `GET /v1/settings/agents` — list agents
- `POST /v1/settings/agents` — create agent
- `PUT /v1/settings/agents/{id}` — update agent
- `POST /v1/settings/agents/{id}/activate` — activate agent

## Related

- [[02-chat-api-flow]] — System prompt injection into chat
- [[09-security]] — Auth middleware reads security settings
- [[00-architecture-overview]] — Settings service in startup sequence
- [[01-database-system]] — Settings DB structure
