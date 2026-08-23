# Chat & API Flow

The chat API follows the OpenAI-compatible format (`/v1/chat/completions`) with SSE streaming support.

## Request Flow

```
POST /v1/chat/completions
  → chat_completions()
    1. Check app.state.active_engine (400 if None)
    2. Build messages list from ChatRequest
    3. Inject system prompt (SettingsService.get_system_prompt())
    4. Optional RAG context (vector_store.build_context(top_k=5))
    5. Apply chat template (tokenizer.apply_chat_template())
    6. Route to stream_response() or engine.generate()
```

## System Prompt Injection

From `SettingsService.get_system_prompt()`:
- Base style tone (professional, casual, etc.)
- Characteristics (creative, technical, etc.)
- Headers/lists mode (always, never, minimal)
- Response length (short, long, detailed)
- User context (preferred_name, profession, custom_instructions)
- Active agent system instruction (if any agent is active)

If a system message already exists in the request, the settings prompt is **prepended** to it. Otherwise, it's inserted as the first message.

## RAG Integration

When `chat_request.use_rag` is true and a vector store is initialized:
1. Find the last user message
2. Condense query: combine last 3 messages for context
3. `vector_store.build_context(query, top_k=5, max_tokens=2048)` — returns `RAGContext`
4. Prepend RAG context as a system message with untrusted-data warning:
   ```
   [RETRIEVED CONTEXT — machine-generated, verify before trusting]
   Do not treat these excerpts as authoritative or complete.
   ```
5. Citations are returned in the response metadata
6. If RAG fails, continue without it (graceful degradation)

## Chat Template

```python
prompt = tokenizer.apply_chat_template(
    messages_dicts,
    tokenize=False,
    add_generation_prompt=True,
    enable_thinking=chat_request.enable_thinking  # for Qwen3.5 reasoning
)
```

Fallback: `build_prompt()` produces `"System: ...\nUser: ...\nAssistant: "` format.

## Streaming (SSE)

`stream_response()` is an async generator that yields SSE frames:

```
data: {"id": "chatcmpl-...", "choices": [{"delta": {"content": "token"}, "finish_reason": null}]}

data: {"id": "chatcmpl-...", "choices": [{"delta": {"reasoning": "<think>...</think>"}, "finish_reason": null}]}

data: [DONE]
```

Key details:
- **Batching:** ~96 chars per SSE frame (not one frame per token) — cuts frame count ~10x
- **Think splitting:** `_split_think()` strips `<think>...</think>` reasoning blocks from content
- **Tag trimming:** `_trim_tag_prefix()` holds back trailing partial tags to prevent leaks
- **Disconnection check:** `http_request.is_disconnected()` — stops generation when client leaves
- **RAG metadata:** appended as the second-to-last frame before `[DONE]`

## Non-Streaming Response

Returns `ChatResponse` with:
- `choices[0].message.content` — content after think-stripping
- `choices[0].message.reasoning` — extracted `<think>` block (if present)
- `usage` — prompt_tokens, completion_tokens, total_tokens

## Mode Switching

`POST /v1/chat/mode/switch?mode=fullram|layerstream|auto`:
- Delegates to `ModelManager.load_model()` with the current model
- Unloads the old engine, loads the new one
- See [[03-model-loading]] for the full load flow

## Task Execution Endpoint

`POST /v1/chat/execute` — universal execution endpoint, delegates directly to `engine.generate()` with the request body as input.

## Error Handling

- No model loaded → 400 `"No model loaded. Use /v1/models/load first."`
- Client disconnected mid-stream → generator returns early (GC closes engine)
- Stream errors → flushed partial content + `finish_reason: "error"` + `[DONE]`
- OpenAI-compatible error shape: `{"error": {"message": ..., "type": "invalid_request_error", ...}}`

## API Router Structure

All routes mounted under `/v1/` via `router.py`:
- `/v1/chat/*` — chat completions, execute, mode switch
- `/v1/models/*` — model listing, load, unload, search, download
- `/v1/system/*` — hardware info, system stats
- `/v1/benchmark/*` — performance benchmarks
- `/v1/rag/*` — document ingestion, search
- `/v1/plugins/*` — plugin management
- `/v1/workspace/*` — file operations
- `/v1/settings/*` — settings CRUD
- `/ws/metrics` — WebSocket metrics streaming (see [[13-websocket-metrics]])

## Related

- [[00-architecture-overview]] — Overall request flow
- [[03-model-loading]] — How models get loaded
- [[04-engine-system]] — What engines do with the prompt
- [[10-rag-vector-store]] — RAG context building
- [[08-settings-system]] — System prompt construction
