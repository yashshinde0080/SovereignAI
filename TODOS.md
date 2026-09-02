# Online Mode — Cloud API Integration Plan

**Status:** Planning  
**Branch:** main  
**Date:** 2026-09-02  
**Scope:** Add a third execution mode ("cloud") alongside FullRAM and LayerStream, allowing users to connect external API providers (OpenAI, Anthropic, Google, Mistral, custom/self-hosted endpoints) with API keys and custom base URLs.

---

## 1. Problem Statement

SovereignAI Edge currently only supports **local inference** (FullRAM + LayerStream). Users who have low-RAM hardware or want access to frontier models (GPT-4o, Claude Opus, Gemini 2.5) have no path to use them. Online mode bridges this gap: users add their API keys, select a cloud model, and chat through the same UI and API surface — no model download, no VRAM required.

## 2. Architecture

```
Client (React / Electron / CLI)
  → REST / WebSocket  (127.0.0.1:8000)
  → FastAPI Gateway  (/v1/*)
      Chat: system prompt + RAG context → apply_chat_template
            → engine.generate() or stream_response() SSE
            → if engine is CloudAPIEngine:
                forward messages to provider API
                stream SSE tokens back
            → if engine is FullRAM/LayerStream:
                local inference as before
  → Provider API (OpenAI / Anthropic / Google / custom)
```

### New component: `CloudAPIEngine`

A new engine implementing `BaseEngine` that proxies requests to external APIs. No local model weights loaded — the "model" is a remote API endpoint.

### Provider Registry

A new database table (`cloud_providers`) in `sovereign_settings.db` storing:
- Provider name, type (openai/anthropic/google/mistral/custom)
- API key (encrypted via Fernet)
- Base URL (for custom/self-hosted endpoints like vLLM, Ollama, LiteLLM)
- Enabled/disabled flag
- Rate limit settings (optional)

---

## 3. Backend Changes

### 3.1 New Engine: `CloudAPIEngine`

**File:** `backend/app/engines/cloud/engine.py`

```
Implements BaseEngine ABC:
  - load(): validate API key, fetch model list, set self.loaded = True
  - unload(): clean up session state
  - generate(): POST to provider's chat completions endpoint
  - generate_stream(): SSE stream from provider
  - get_memory_usage(): return zero (no local memory used)
```

Key design:
- Uses `aiohttp` (already a dependency) for HTTP calls
- OpenAI-compatible providers (OpenAI, Together, Groq, vLLM, Ollama) use the same `/v1/chat/completions` format
- Anthropic uses `/v1/messages` format (different request/response shape)
- Google Gemini uses `/v1/models/{model}:generateContent`
- Custom providers: assume OpenAI-compatible format (user provides base URL)
- `mode = "cloud"` — new mode value alongside `fullram` and `layerstream`

**Streaming:**
- For OpenAI-compatible: parse SSE from provider, re-emit as SovereignAI SSE chunks
- For Anthropic: parse SSE events (`content_block_delta`), re-emit as SovereignAI SSE chunks
- For Google: use REST streaming if available, else fall back to non-streaming

**Request translation:**
- SovereignAI's `ChatRequest` messages → provider-specific format
- System prompt injection (already in `chat.py`) stays the same
- Token counting: use provider's returned usage data

### 3.2 Provider Registry

**File:** `backend/app/engines/cloud/registry.py`

```python
class CloudProviderRegistry:
    """Manages cloud provider credentials and model lists in sovereign_settings.db"""
    
    async def add_provider(provider: CloudProviderConfig) -> None
    async def remove_provider(provider_id: str) -> None
    async def list_providers() -> List[CloudProviderConfig]
    async def get_provider(provider_id: str) -> CloudProviderConfig
    async def update_provider(provider_id: str, updates: dict) -> None
    
    async def fetch_models(provider_id: str) -> List[CloudModel]
    async def get_all_cloud_models() -> List[CloudModel]
```

**Database schema** (new table in `sovereign_settings.db`):
```sql
CREATE TABLE IF NOT EXISTS cloud_providers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider_type TEXT NOT NULL,  -- openai, anthropic, google, mistral, custom
    api_key_encrypted TEXT,       -- Fernet-encrypted API key
    base_url TEXT,                -- custom endpoint URL
    is_enabled INTEGER DEFAULT 1,
    rate_limit_rpm INTEGER DEFAULT 60,
    created_at TEXT,
    updated_at TEXT
);
```

### 3.3 Schemas

**File:** `backend/app/schemas/cloud.py` (new)

```python
class CloudProviderConfig(BaseModel):
    id: str
    name: str
    provider_type: Literal["openai", "anthropic", "google", "mistral", "custom"]
    api_key: str                    # write-only, never returned in GET
    base_url: Optional[str] = None  # required for "custom" type
    is_enabled: bool = True
    rate_limit_rpm: int = 60

class CloudModel(BaseModel):
    id: str
    name: str
    provider_id: str
    provider_type: str
    context_window: Optional[int] = None
    supports_streaming: bool = True
    supports_vision: bool = False

class CloudModelList(BaseModel):
    models: List[CloudModel]
```

### 3.4 API Endpoints

**File:** `backend/app/api/cloud.py` (new)

New router mounted at `/v1/cloud`:

```
GET    /v1/cloud/providers          — list all configured providers (keys redacted)
POST   /v1/cloud/providers          — add a new provider (validates API key)
DELETE /v1/cloud/providers/{id}     — remove a provider
PUT    /v1/cloud/providers/{id}     — update provider config

GET    /v1/cloud/models             — list all available cloud models (across providers)
POST   /v1/cloud/models/refresh     — re-fetch model lists from all enabled providers
GET    /v1/cloud/models/{provider}  — list models for a specific provider

POST   /v1/cloud/test/{provider_id} — test API key validity + connectivity
```

### 3.5 Engine Factory Update

**File:** `backend/app/core/engine_factory.py`

Add `"cloud"` mode branch in `create_engine()`:
```python
elif mode == "cloud":
    # CloudAPIEngine takes provider config, not a local path
    engine = CloudAPIEngine(
        provider_config=...,
        model_id=...,
        hardware=self.hardware,
        memory_manager=self.memory_manager,
    )
```

The `model_path` for cloud mode is interpreted as `{provider_id}/{model_id}`.

### 3.6 Model Manager Update

**File:** `backend/app/services/model_manager.py`

- `load_model()` already handles mode switching — add cloud mode handling
- Cloud models don't need disk scanning, downloading, or VRAM checks
- `scan_installed()` remains unchanged (cloud models aren't local files)
- `list_models()` should include cloud models from the provider registry alongside local models

### 3.7 Chat API Update

**File:** `backend/app/api/chat.py`

- `chat_completions()` currently requires `app.state.active_engine` to be loaded
- Cloud mode uses the same flow: `CloudAPIEngine.generate()` / `generate_stream()`
- No changes needed to chat.py itself — the engine abstraction handles it
- The `stream_response()` function works with any engine that implements `generate_stream()`

### 3.8 Settings Integration

**File:** `backend/app/settings/schemas.py`

Add `CloudSettings` section:
```python
class CloudSettings(BaseModel):
    providers: List[CloudProviderConfig] = []
    default_provider: Optional[str] = None  # provider_id
    auto_fallback: bool = True  # if cloud model fails, try next provider
```

Add to `FullSettings`:
```python
class FullSettings(BaseModel):
    ...
    cloud: CloudSettings = CloudSettings()
```

### 3.9 Security

- API keys stored encrypted (Fernet via existing `ModelEncryption` class)
- API keys never returned in GET responses (only `****` masked preview)
- API keys never logged
- Bearer auth middleware already covers cloud endpoints (opt-in via `security.bind_localhost_only`)

---

## 4. Frontend Changes

### 4.1 Settings Page — Cloud Providers Tab

**File:** `frontend/app/settings/page.tsx` (or new component)

New "Cloud Providers" section in settings:
- List configured providers (name, type, status indicator)
- Add provider form: select type → enter API key + optional base URL
- "Test Connection" button → calls `/v1/cloud/test/{id}`
- Delete provider button with confirmation
- Enable/disable toggle

### 4.2 Model Picker — Cloud Models

**File:** `frontend/components/models/` (new or extend existing)

- Model list shows both local and cloud models
- Cloud models marked with a cloud icon badge
- Group by: "Local" and "Online" sections
- Cloud model cards show: provider name, context window, streaming support
- Click cloud model → calls `/v1/models/load` with `mode=cloud`

### 4.3 Chat UI Updates

**File:** `frontend/components/chat/ChatWindow.tsx`

- Show indicator when connected to cloud model (e.g., "Online · GPT-4o via OpenAI")
- Streaming works the same — CloudAPIEngine emits same SSE format
- No visible difference in chat experience between local and cloud

### 4.4 State Management

**File:** `frontend/lib/stores/` (Zustand store)

Add cloud-related state:
```typescript
interface CloudState {
  providers: CloudProvider[]
  cloudModels: CloudModel[]
  fetchProviders: () => Promise<void>
  addProvider: (config: CloudProviderConfig) => Promise<void>
  removeProvider: (id: string) => Promise<void>
  refreshModels: () => Promise<void>
}
```

### 4.5 Onboarding / First-Run

- If no providers configured and user tries to load a cloud model → show setup prompt
- "Connect your first API key" wizard with step-by-step guide

---

## 5. CLI Changes

**File:** `backend/app/cli/main.py`

New typer commands:
```bash
sovereign cloud add --name "OpenAI" --type openai --key "sk-..."
sovereign cloud list
sovereign cloud remove <id>
sovereign cloud test <id>
sovereign cloud models [--provider <id>]
```

---

## 6. Provider-Specific API Translation

### OpenAI / OpenAI-Compatible (Together, Groq, vLLM, Ollama)
- Base URL: `https://api.openai.com/v1` (default for openai type)
- Request: standard `/v1/chat/completions` format
- Response: standard OpenAI format — passthrough

### Anthropic
- Base URL: `https://api.anthropic.com` (default)
- Request conversion: `{messages, model, system, max_tokens, temperature}`
- Response conversion: Anthropic `content` → OpenAI `choices[0].message.content`
- Streaming: Anthropic SSE events → SovereignAI SSE format

### Google Gemini
- Base URL: `https://generativelanguage.googleapis.com`
- Request conversion: `contents[]` array with `role`/`parts`
- Response conversion: `candidates[0].content.parts[0].text`
- Streaming: REST streaming or batch fallback

### Custom (OpenAI-compatible)
- User provides base URL (e.g., `http://localhost:11434/v1` for Ollama)
- Assume OpenAI-compatible request/response format
- Validate connectivity with a test request

---

## 7. File Inventory (new/modified)

### New Files
| File | Purpose |
|---|---|
| `backend/app/engines/cloud/__init__.py` | Package init |
| `backend/app/engines/cloud/engine.py` | CloudAPIEngine — BaseEngine impl |
| `backend/app/engines/cloud/registry.py` | Provider registry + DB operations |
| `backend/app/engines/cloud/providers.py` | Provider-specific API translation (OpenAI, Anthropic, Google) |
| `backend/app/api/cloud.py` | REST endpoints for cloud provider management |
| `backend/app/schemas/cloud.py` | Pydantic models for cloud providers |

### Modified Files
| File | Change |
|---|---|
| `backend/app/core/engine_factory.py` | Add `"cloud"` mode branch |
| `backend/app/services/model_manager.py` | Handle cloud models in `list_models()`, `load_model()` |
| `backend/app/api/router.py` | Mount cloud router |
| `backend/app/settings/schemas.py` | Add `CloudSettings` to `FullSettings` |
| `backend/app/api/models.py` | Include cloud models in list endpoint |
| `backend/app/cli/main.py` | Add `cloud` subcommand group |
| `frontend/components/models/ModelList.tsx` | Show cloud models with badge |
| `frontend/components/settings/CloudProviders.tsx` | New settings panel |
| `frontend/lib/stores/` | Add cloud state slice |

---

## 8. Implementation Phases

### Phase 1: Backend Core (Estimated: 1-2 days)
- [ ] Create `CloudAPIEngine` implementing `BaseEngine` (OpenAI-compatible first)
- [ ] Create provider registry with DB schema
- [ ] Create API endpoints (`/v1/cloud/*`)
- [ ] Wire into `EngineFactory` and `ModelManager`
- [ ] Add cloud mode to `ModelManager.load_model()`
- [ ] Write unit tests for `CloudAPIEngine` and provider registry

### Phase 2: Multi-Provider Support (Estimated: 1 day)
- [ ] Add Anthropic provider adapter
- [ ] Add Google Gemini provider adapter
- [ ] Add custom endpoint support (OpenAI-compatible)
- [ ] Add API key encryption via Fernet
- [ ] Add connectivity test endpoint

### Phase 3: Frontend Integration (Estimated: 1-2 days)
- [ ] Cloud provider settings panel
- [ ] Model picker with cloud/local grouping
- [ ] Cloud model loading flow
- [ ] Chat UI cloud model indicator
- [ ] Zustand state management for cloud state

### Phase 4: CLI + Polish (Estimated: 0.5 day)
- [ ] CLI `cloud` subcommand group
- [ ] Error handling for API failures (rate limits, auth, network)
- [ ] Integration tests
- [ ] Documentation update (AGENTS.md, Info_docs/)

---

## 9. Testing Plan

### Unit Tests
- `CloudAPIEngine.generate()` — mock provider HTTP responses
- `CloudAPIEngine.generate_stream()` — mock SSE responses
- Provider registry CRUD operations
- API key encryption/decryption roundtrip
- Request translation for each provider type

### Integration Tests
- Full chat flow: `/v1/chat/completions` → `CloudAPIEngine` → mock provider → response
- Streaming flow: SSE chunk assembly
- Provider management: add/test/remove via API
- Error handling: invalid API key, rate limit, network timeout

### Manual QA
- OpenAI connection: test with real key (if available)
- Anthropic connection: test with real key (if available)
- Custom endpoint: test with local Ollama instance
- Switch between cloud and local models mid-session

---

## 10. Error Handling

| Error | HTTP Code | User Message |
|---|---|---|
| No API key configured | 400 | "Add an API key in Settings → Cloud Providers" |
| Invalid API key | 401 | "API key rejected by {provider}. Check your key." |
| Rate limited | 429 | "Rate limited by {provider}. Wait {retry_after}s." |
| Network timeout | 504 | "Could not reach {provider}. Check your network." |
| Model not found | 404 | "Model '{model}' not available on {provider}." |
| Provider offline | 503 | "Provider {provider} is unreachable." |

---

## 11. Security Considerations

1. **API key encryption:** Fernet + PBKDF2HMAC (same as model encryption)
2. **Key never exposed:** GET endpoints return `****sk-...xxxx` mask only
3. **Key never logged:** Sanitize all log output
4. **Localhost-first:** Cloud endpoints respect existing `bind_localhost_only` setting
5. **No key in frontend:** API calls go through backend; frontend never sees raw keys
6. **HTTPS enforcement:** Warn if base URL is HTTP (except localhost)

---

## 12. NOT in Scope (Deferred)

- **Streaming tool calls** — Phase 2, after basic chat works
- **Image/vision via cloud** — requires provider-specific multimodal support
- **Audio models via cloud** — low priority, high complexity
- **Usage tracking/billing** — nice-to-have, defer to later
- **Model caching** — cloud responses aren't cached locally
- **Offline fallback** — auto-switch to local if cloud fails (complex, defer)
