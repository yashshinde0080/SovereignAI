# SovereignAI Edge — Complete Pipeline Reference

> Every major data flow and control path through the system, traced from source to sink.

---

## Table of Contents

1. [Application Startup Pipeline](#1-application-startup-pipeline)
2. [Chat Request Pipeline (Streaming)](#2-chat-request-pipeline-streaming)
3. [Chat Request Pipeline (Non-Streaming)](#3-chat-request-pipeline-non-streaming)
4. [Model Loading Pipeline](#4-model-loading-pipeline)
5. [Engine Selection Pipeline](#5-engine-selection-pipeline)
6. [FullRAM Inference Pipeline](#6-fullram-inference-pipeline)
7. [LayerStream Inference Pipeline](#7-layerstream-inference-pipeline)
8. [RAG Ingestion Pipeline](#8-rag-ingestion-pipeline)
9. [RAG Query Pipeline](#9-rag-query-pipeline)
10. [Model Download Pipeline](#10-model-download-pipeline)
11. [Model Deletion Pipeline](#11-model-deletion-pipeline)
12. [Mode Switch Pipeline](#12-mode-switch-pipeline)
13. [Plugin Execution Pipeline](#13-plugin-execution-pipeline)
14. [Settings Pipeline](#14-settings-pipeline)
15. [System Status Pipeline](#15-system-status-pipeline)
16. [WebSocket Metrics Pipeline](#16-websocket-metrics-pipeline)
17. [Electron Startup Pipeline](#17-electron-startup-pipeline)
18. [CLI Chat Pipeline](#18-cli-chat-pipeline)
19. [LayerStream Weight Splitting Pipeline](#19-layerstream-weight-splitting-pipeline)
20. [LayerStream Prefetch & Cache Pipeline](#20-layerstream-prefetch--cache-pipeline)

---

## 1. Application Startup Pipeline

The `lifespan()` async context manager in `backend/app/main.py` orchestrates the entire boot sequence before the first request can be served.

**Flow:**

```
SOVEREIGN_RELOAD=1 python main.py  (or uvicorn, or Electron spawns it)
  │
  ▼ uvicorn loads app.main:app
  │
  ▼ lifespan() context manager enters
  │
  ├─ 1. _configure_logging()
  │     Read SOVEREIGN_LOG_LEVEL env var (default: INFO)
  │     Set format: "%(asctime)s %(levelname)s %(name)s: %(message)s"
  │
  ├─ 2. _patch_gguf_quant_types()
  │     Import gguf.constants
  │     Check if IQ2_BN enum member exists
  │     If missing: extend GGMLQuantizationType enum with value 135
  │     Swap into all loaded gguf submodules
  │     Purpose: supports BitNet b1.58 2-bit GGUF models
  │
  ├─ 3. DatabaseManager.initialize()
  │     Open workspace/database/sovereign.db
  │     WAL mode, synchronous=NORMAL, mmap_size=256MB
  │     Create tables if missing (models, sessions, documents, etc.)
  │     Attach to app.state.db
  │
  ├─ 4. VectorStoreManager.initialize()
  │     Load config/storage.toml (or defaults)
  │     Create DocumentChunker, EmbeddingPipeline, FAISSIndexBuilder
  │     Create VectorMetadataStore (SQLite)
  │     Try loading existing FAISS index from workspace/vectors/
  │     If none exists: wait for first ingest
  │     Attach to app.state.vector_store
  │
  ├─ 5. detect_hardware()
  │     HardwareDetector probes:
  │       CPU: model name, core count, frequency
  │       RAM: total, available
  │       GPU: CUDA device name, VRAM (torch.cuda.mem_get_info)
  │       Disk: sequential read speed benchmark via llmfit
  │     Returns hardware_profile dict
  │     Attach to app.state.hardware_profile
  │
  ├─ 6. ModelManager.initialize(app)
  │     Link to app.state for dependency injection
  │     Scan workspace/models/installed/ in background thread
  │       - HuggingFace dirs (config.json present)
  │       - Standalone GGUF files
  │       - Pre-split models in workspace/offload_cache/
  │     Sync discovered models with sovereign.db registry
  │     Clean stale registry entries for deleted files
  │     Attach to app.state.model_manager
  │
  ├─ 7. SettingsService.initialize()
  │     Open workspace/database/sovereign_settings.db
  │     WAL mode, same pragmas
  │     Create settings, agents, audit_log tables if missing
  │     Attach to app.state.settings_service
  │
  ├─ 8. Auto-load startup model
  │     Read general.startup_model from settings DB
  │     Read general.default_mode from settings DB
  │     If both set: await model_manager.load_model(startup_model, default_mode)
  │     On failure: log warning, continue (server starts without model)
  │
  └─ 9. PluginManager.load_plugins()
        Scan backend/app/plugins/builtin/ + workspace/plugins/
        importlib.util for each .py file
        Find PluginInterface subclasses
        Call initialize() on each
        Attach to app.state.plugin_manager
  │
  ▼ lifespan() yields — server accepts requests
  │
  ▼ On shutdown: plugin cleanup, vector store save, DB close
```

**Key details:**
- Steps 1–2 are synchronous and fast (< 1s)
- Step 3–4 open SQLite databases with WAL mode for concurrent read access
- Step 5 uses llmfit for hardware scoring (falls back to psutil if llmfit unavailable)
- Step 6 is partially async — background scan runs concurrently with server startup
- Step 8 may block for seconds to minutes depending on model size and engine mode
- All services attached to `app.state.*` for FastAPI dependency injection

---

## 2. Chat Request Pipeline (Streaming)

The primary inference path. Handles the complete lifecycle from user message to SSE token stream.

**Entry point:** `POST /v1/chat/completions` with `stream: true`

```
HTTP POST /v1/chat/completions
  Body: { messages: [...], stream: true, max_tokens: 512, temperature: 0.7, ... }
  │
  ▼ Middleware stack
  │  CORS: check Origin header (localhost:3000, app://-)
  │  Rate limit: slowapi 60/min per IP
  │  Auth: Bearer token check (only if bind_localhost_only=false AND api_token set)
  │
  ▼ chat_completions() in chat.py
  │
  ├─ 1. Validate engine loaded
  │     if not app.state.active_engine → HTTP 400 "No model loaded"
  │
  ├─ 2. Parse messages
  │     ChatRequest.messages → list of {role, content} dicts
  │
  ├─ 3. Inject system prompt (SettingsService)
  │     settings_service.get_system_prompt()
  │       Combines: base_style_tone, characteristics, response_length,
  │       user_context, custom_instructions, active agent instruction
  │     If messages already have system role: prepend settings prompt
  │     If no system message: insert as first message
  │
  ├─ 4. RAG integration (if use_rag=true AND vector_store initialized)
  │     Find last user message index
  │     Query condensation:
  │       If ≥3 messages: join last 3 as "role: content\n" + "user: <query>"
  │       Else: use query as-is
  │     vector_store.build_context(condensed_query, top_k=5, max_tokens=2048)
  │       → FAISS cosine search → retrieve top_k chunks
  │       → Concatenate up to max_tokens
  │       → Return RAGContext(context_text, results)
  │     If results found:
  │       Build augmented_content = "[RETRIEVED CONTEXT — machine-generated, verify before trusting]\n..."
  │       Append to system message (or create one)
  │       Extract citations: [{document_id, filename, score}]
  │       Store in rag_metadata_out
  │     If RAG fails: log warning, continue without context
  │
  ├─ 5. Apply chat template
  │     If tokenizer has apply_chat_template:
  │       kwargs = {tokenize: False, add_generation_prompt: True}
  │       If enable_thinking is not None: kwargs["enable_thinking"] = enable_thinking
  │       prompt = tokenizer.apply_chat_template(messages_dicts, **kwargs)
  │     Else: fallback to build_prompt() — "System: ... / User: ... / Assistant: ..."
  │
  └─ 6. Return StreamingResponse(stream_response(...))
         media_type="text/event-stream"

stream_response() async generator:
  │
  ├─ Initialize
  │     full_text = "<think>" if prompt ends with "<think>" else ""
  │     sent = 0  (chars of content already emitted)
  │     rsent = 0 (chars of reasoning already emitted)
  │     stream_id = f"chatcmpl-{uuid4_hex}"
  │     BATCH_CHARS = 96
  │     pending_c, pending_r, pending_chars = [], [], 0
  │
  ├─ For each chunk from engine.generate_stream():
  │     │
  │     ├─ Check http_request.is_disconnected()
  │     │   If true: return (abort stream, engine GC'd)
  │     │
  │     ├─ Extract token = chunk.get("token", "")
  │     ├─ Extract finish = chunk.get("finish_reason")
  │     ├─ Skip if no token and no finish
  │     ├─ Append token to full_text
  │     │
  │     ├─ _split_think(full_text)
  │     │   Regex scan for <think> and </think> tags
  │     │   Returns (content, reasoning) — text between tags is reasoning
  │     │
  │     ├─ _trim_tag_prefix(content) and _trim_tag_prefix(reasoning)
  │     │   Drop trailing chars that could start <think> or </think>
  │     │   Checks last 1..8 chars against tag prefixes
  │     │
  │     ├─ Compute deltas:
  │     │   c_out = content[sent:] (new content since last emit)
  │     │   r_out = reasoning[rsent:] (new reasoning since last emit)
  │     │   Update sent, rsent
  │     │
  │     ├─ Batch accumulation:
  │     │   pending_c.append(c_out), pending_r.append(r_out)
  │     │   pending_chars += len(c_out) + len(r_out)
  │     │   If pending_chars >= BATCH_CHARS:
  │     │     _take_pending() → _emit() → yield SSE frame
  │     │
  │     └─ If finish is not None:
  │           Flush pending batch
  │           Yield finish frame: _emit("", "", finish)
  │
  ├─ After loop:
  │     Yield rag_metadata chunk (if any):
  │       {delta: {rag_metadata: [{document_id, filename, score}]}}
  │
  └─ Yield "data: [DONE]\n\n"

SSE output format per frame:
  data: {"id":"chatcmpl-abc123","choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}

  data: {"id":"chatcmpl-abc123","choices":[{"delta":{"reasoning":"Let me think..."},"finish_reason":null}]}

  data: {"id":"chatcmpl-abc123","choices":[{"delta":{"rag_metadata":[...]},"finish_reason":null}]}

  data: {"id":"chatcmpl-abc123","choices":[{"delta":{},"finish_reason":"stop"}]}

  data: [DONE]
```

**Key details:**
- The 96-char batch size cuts SSE frames ~10x vs one-frame-per-token
- `_split_think` handles unclosed think blocks (model stopped mid-reasoning)
- `_trim_tag_prefix` prevents partial `<think>` or `</think>` tags leaking across frames
- Disconnection check on every token prevents wasted compute on abandoned streams
- RAG metadata arrives as a special chunk before `[DONE]`, not inline with content
- The `<think>` reasoning path is only activated when the chat template opens a think block

---

## 3. Chat Request Pipeline (Non-Streaming)

Identical to streaming through step 5, then diverges:

```
  ... (steps 1–5 same as streaming)
  │
  └─ Non-streaming path:
       │
       ├─ Check http_request.is_disconnected() → HTTP 499 if true
       │
       ├─ await engine.generate(
       │     input_data=prompt,
       │     max_tokens=chat_request.max_tokens,
       │     temperature=chat_request.temperature,
       │     top_p=chat_request.top_p
       │   )
       │
       ├─ Extract raw_output = response["output"] or response["text"]
       │
       ├─ If prompt ends with "<think>": prepend "<think>" to raw_output
       │
       ├─ _split_think(raw_output) → (content, reasoning)
       │   If "<think>" in raw_output: strip whitespace, set reasoning=None if empty
       │
       └─ Return ChatResponse:
            {
              id: "chatcmpl-...",
              model: "...",
              choices: [{index: 0, message: {role: "assistant", content, reasoning}, finish_reason: "stop"}],
              usage: {prompt_tokens, completion_tokens, total_tokens}
            }
```

**Key details:**
- Non-streaming waits for the entire generation to complete before returning
- The `_prompt_opens_think` check handles thinking mode where the template puts `<think>` in the prompt
- The `finish_reason` comes from the engine's internal detection (EOS vs length limit)

---

## 4. Model Loading Pipeline

The most complex pipeline — involves multiple decision points, lock management, and error rollback.

**Entry point:** `POST /v1/models/load` with `{model: "Qwen2-0.5B", mode: "auto"}`

```
POST /v1/models/load
  Body: { model: "Qwen2-0.5B", mode: "auto" }
  │
  ▼ models.py:load_model()
  │
  ├─ 1. Validate request
  │     LoadRequest has model (required) and mode (default: "auto")
  │
  ├─ 2. ModelManager.load_model(model_id, mode)
  │     │
  │     ├─ Wait for background scan
  │     │   If _scan_task is running: await it
  │     │   Purpose: ensure registry is complete before loading
  │     │
  │     ├─ Resolve model
  │     │   Direct lookup: get_model(model_id)
  │     │   If not found: list all models → _fuzzy_match_model()
  │     │     Normalizes slashes/colons, prefers exact match, then containment
  │     │   If still not found: raise ValueError
  │     │
  │     ├─ Acquire _load_lock (asyncio.Lock)
  │     │   Serializes concurrent loads — two simultaneous loads would fight
  │     │   over app.state.active_engine/model/mode
  │     │
  │     └─ _load_model_locked(model_id, mode, model)
  │         │
  │         ├─ Save previous state
  │         │   prev_engine = app.state.active_engine
  │         │   prev_model = app.state.active_model
  │         │   prev_mode = app.state.active_mode
  │         │
  │         ├─ Mode correction
  │         │   If mode=="auto" AND model_id starts with "split:":
  │         │     mode = "layerstream"  (split models only support LayerStream)
  │         │
  │         │   If mode=="fullram" AND model_id starts with "split:":
  │         │     Find base model via fuzzy matching (strip "split:" prefix)
  │         │     Redirect to base model path
  │         │
  │         ├─ Disk full preflight (LayerStream only)
  │         │   free_bytes = shutil.disk_usage(workspace_dir).free
  │         │   need_bytes = _model_size_bytes(model)  (sum of all files)
  │         │   If free_bytes < need_bytes: raise RuntimeError with GB amounts
  │         │
  │         ├─ EngineFactory.create_engine(model_path, mode, model_metadata)
  │         │   (See Pipeline #5 below)
  │         │
  │         ├─ engine.load()
  │         │   (See Pipeline #6 or #7 below)
  │         │
  │         ├─ On success: unload previous engine
  │         │   if prev_engine: await prev_engine.unload()
  │         │
  │         ├─ Update app.state
  │         │   app.state.active_engine = engine
  │         │   app.state.active_model = model_id
  │         │   app.state.active_mode = engine.mode
  │         │
  │         └─ On engine.load() failure:
  │             await engine.unload()
  │             Restore prev_engine/prev_model/prev_mode
  │             Raise exception (user keeps their previous model)
  │
  └─ Return {status: "loaded", model: model_id, mode: resolved_mode}
```

**Key details:**
- The load lock prevents race conditions when two clients try to load models simultaneously
- Error rollback ensures the user doesn't lose their active model if a new load fails
- Split model detection prevents FullRAM from trying to load per-layer files
- Disk preflight catches OOM-before-it-happens for LayerStream's swap cache
- The background scan must complete before loading to ensure the registry is accurate

---

## 5. Engine Selection Pipeline

Decides which engine to instantiate based on model capabilities and available hardware.

**Called by:** `ModelManager._load_model_locked()` via `EngineFactory.create_engine()`

```
EngineFactory.create_engine(model_path, mode, model_metadata)
  │
  ├─ 1. Compute model size
  │     If directory with config.json:
  │       model_size = sum of all file sizes in directory
  │     If directory with GGUF files:
  │       model_size = size of first .gguf file
  │     If directory with safetensors only:
  │       model_size = sum of .safetensors + .safetensors.enc files
  │     If single file:
  │       model_size = file.stat().st_size
  │
  ├─ 2. TaskResolver.resolve(model_path)
  │     (See sub-pipeline below)
  │     Returns: {task_type, input_modality, is_generative, ...}
  │
  ├─ 3. Mode resolution
  │     If mode == "auto":
  │       │
  │       ├─ Try llmfit scoring (if model_metadata has name/id)
  │       │   score_model_fit(model_name, hw) → fit score
  │       │   fit > 0.85 AND ram_required < 70% total → "fullram"
  │       │   fit > 0.6 → "layerstream"
  │       │   else → "insufficient"
  │       │
  │       ├─ Fallback: legacy threshold
  │       │   CUDA VRAM: model_size * 1.1 < free_vram → "fullram"
  │       │   System RAM: model_size * 1.1 < available → "fullram"
  │       │   model_size * 0.1 < available → "layerstream"
  │       │   else → "insufficient"
  │       │
  │       └─ Override: if suggested "layerstream" AND not is_generative:
  │             mode = "fullram"  (non-generative tasks can't use LayerStream)
  │
  │     If mode == "insufficient": raise RuntimeError
  │
  ├─ 4. Read quant_method from metadata.json
  │     Maps GGUF quant strings (Q4_K_M, Q5_K_M, Q8_0) to quant_method="gguf"
  │     Default: "none"
  │
  └─ 5. Instantiate engine
        If mode == "fullram":
          FullRAMEngine(model_path, hardware, memory_manager)
        If mode == "layerstream":
          LayerStreamEngine(model_path, hardware, memory_manager,
                           quant_method, turboquant_config)
```

**TaskResolver.resolve() sub-pipeline:**

```
TaskResolver.resolve(model_path)
  │
  ├─ 1. AutoConfig.from_pretrained(model_path, local_files_only=True)
  │     Try local first → fallback to remote
  │     If both fail: return safe default {causal_lm, generative: True}
  │
  ├─ 2. Read config attributes
  │     architectures = getattr(config, "architectures", [])
  │     model_type = getattr(config, "model_type", "").lower()
  │     is_encoder_decoder = getattr(config, "is_encoder_decoder", False)
  │
  ├─ 3. Architecture mapping (20+ task types)
  │     "ForCausalLM" → causal_lm, generative=True
  │     "ForSeq2SeqLM" + is_encoder_decoder → seq2seq_lm
  │     "ForConditionalGeneration" + NOT is_encoder_decoder → causal_lm
  │     "ForMaskedLM" → masked_lm
  │     "ForSequenceClassification" → sequence_classification
  │     "ForImageClassification" → image_classification, modality=image
  │     "ForConditionalGeneration" + vision_config → vision2seq, modality=multimodal
  │     Whisper architectures → speech_seq2seq, modality=audio
  │     ... and more
  │
  └─ 4. Heuristic guard
        vision_config attribute only triggers vision2seq if no task was matched
        Prevents Qwen3.5 (which has vision_config but is text-only) misclassification

Returns: {model_path, architectures, model_type, task_type, input_modality, is_generative}
```

**Key details:**
- llmfit scoring uses a trained model to predict fit; the threshold fallback uses raw size comparison
- Non-generative tasks (classification, QA) are forced to FullRAM even if memory is low
- The `is_encoder_decoder` check prevents Qwen3.5's `ForConditionalGeneration` from being routed to seq2seq
- Quant method is metadata-driven, not detected at load time

---

## 6. FullRAM Inference Pipeline

The fast path: loads the entire model into RAM/VRAM.

```
FullRAMEngine.load()
  │
  ├─ 1. TaskResolver.resolve() → task_type, input_modality, is_generative
  │
  ├─ 2. TaskRouter.get_model_class(task_type)
  │     Maps task → AutoModelForCausalLM, AutoModelForSeq2SeqLM, etc.
  │
  ├─ 3. Configure device
  │     CUDA available: device_map="auto", dtype=float16
  │     CPU only: device_map="cpu", dtype=float32
  │
  ├─ 4. Load model
  │     If GGUF file:
  │       model_class.from_pretrained(model_dir, gguf_file=basename, **kwargs)
  │     If .bin checkpoint:
  │       ensure_safetensors(model_path)  ← CVE-2025-32434 mitigation
  │       model_class.from_pretrained(model_path, **kwargs)
  │
  ├─ 5. Load tokenizer
  │     AutoTokenizer.from_pretrained(tok_dir, **kwargs)
  │     If no pad_token: set pad_token = eos_token
  │
  ├─ 6. Load processor (modality-dependent)
  │     text/generative: skip
  │     image/multimodal: AutoProcessor or AutoImageProcessor
  │     audio: AutoProcessor
  │
  └─ 7. GGUF fallback chain (on transformers failure)
        Try ik_llama_cpp.IkLlama → handles BitNet / IQ2_BN
        Fallback to llama_cpp.Llama → standard GGUF
        If both fail: descriptive error message

FullRAMEngine.generate(input_data, max_tokens, temperature, top_p)
  │
  ├─ If llama_cpp backend:
  │     Call llama.create_completion(prompt, max_tokens, temperature, top_p)
  │     Extract text from completion object
  │
  ├─ Else (transformers):
  │     Tokenize prompt → input_ids
  │     Route via TaskRouter.execute() based on task_type:
  │       causal_lm: model.generate(input_ids, max_new_tokens, temperature, top_p, do_sample)
  │       classification: model(input_ids) → argmax
  │       seq2seq: model.generate(input_ids, max_new_tokens)
  │       vision2seq: process image + text → model.generate()
  │     Decode output tokens → text
  │
  └─ Return {output, finish_reason, prompt_tokens, completion_tokens, total_tokens}

FullRAMEngine.generate_stream(input_data, max_tokens, temperature, top_p)
  │
  ├─ If llama_cpp backend:
  │     llama.create_completion(prompt, stream=True, ...)
  │     Yield each chunk as {"token": text, "finish_reason": None}
  │
  ├─ Else (transformers):
  │     Create TextIteratorStreamer(tokenizer, skip_prompt=True)
  │     Spawn thread: model.generate(input_ids, streamer=streamer, ...)
  │     For text in streamer:
  │       yield {"token": text, "finish_reason": None}
  │     yield {"token": "", "finish_reason": "stop"}
  │
  └─ Note: ik_llama_cpp doesn't support streaming — yields full output at once
```

**Key details:**
- `device_map="auto"` lets transformers decide GPU/CPU placement across layers
- `low_cpu_mem_usage=True` reduces peak RAM during loading
- `ignore_mismatched_sizes=True` handles quantized models with mismatched weight shapes
- The CVE-2025-32434 mitigation converts `.bin` checkpoints to `.safetensors` before loading
- TextIteratorStreamer runs `model.generate()` in a thread to keep the event loop free

---

## 7. LayerStream Inference Pipeline

The memory-bounded path: swaps layer weights from disk per forward pass.

```
LayerStreamEngine.load()
  │
  ├─ 1. Create offload cache directory
  │     workspace/offload_cache/<model_name>/
  │
  ├─ 2. Weight splitting (if not already split)
  │     Check for embed.safetensors in weights_dir
  │     If missing: WeightSplitter.split_and_save()
  │       (See Pipeline #19 below)
  │     If present but tokenizer files missing: copy from source
  │
  ├─ 3. Load tokenizer
  │     Try from weights_dir first (split model)
  │     Fallback to model_path
  │     For GGUF: pass gguf_file kwarg
  │     If no pad_token: set pad_token = eos_token
  │
  ├─ 4. Load config
  │     AutoConfig.from_pretrained(weights_dir)
  │     Force _attn_implementation = "eager" (required for manual layer execution)
  │     If config has text_config: use text_config for LayerStream params
  │
  ├─ 5. Create empty model skeleton
  │     init_empty_weights() context manager
  │     AutoModelForCausalLM.from_config(config) — no weights loaded
  │     Fallback: AutoModel.from_config(config) for non-standard architectures
  │
  ├─ 6. Detect model components
  │     ModelIntrospector.detect_model_components(model)
  │     Returns: {embed_tokens, layers, norm, lm_head, ...}
  │
  ├─ 7. Detect hybrid architecture
  │     Check config.layer_types (and text_config.layer_types)
  │     Qwen3.5 example: mix of linear_attention and full_attention layers
  │
  ├─ 8. Determine cache budget
  │     If cache_budget_mb from settings: use it
  │     Else: _default_cache_budget_mb(weights_dir)
  │       Auto-scaled: largest per-layer file × 4.5, floor 256MB
  │
  └─ 9. Create LayerExecutor
        components, config, weights_dir, device,
        turboquant_config, layer_types,
        prefetch_depth (default 3), cache_budget_mb

LayerStreamEngine.generate_stream(input_data, max_tokens, temperature, top_p)
  │
  ├─ 1. Apply chat template (same as FullRAM)
  │
  ├─ 2. Tokenize prompt → input_ids (on device)
  │
  ├─ 3. Clear KV cache (hybrid: cache.clear(), standard: kv_manager.clear())
  │
  └─ 4. Two-phase generation:
        │
        │  Phase 1: PREFILL (via asyncio.to_thread)
        │  ┌─────────────────────────────────────────────┐
        │  │ logits = executor.execute_forward(           │
        │  │     input_ids, mode="prefill"               │
        │  │ )                                           │
        │  │                                             │
        │  │ For each layer i:                           │
        │  │   weights = loader.get_weights(i)           │
        │  │     → LRU cache hit: return cached          │
        │  │     → cache miss: load from disk via        │
        │  │       safetensors.torch.safe_open()         │
        │  │       dequantize_on_device() if int8/int4   │
        │  │   output = components[i](hidden, ...)       │
        │  │   Store KV in cache (KVCacheManager or      │
        │  │     StatefulCache for hybrid)               │
        │  │   Prefetch next layers (async ThreadPool)   │
        │  └─────────────────────────────────────────────┘
        │
        │  Sample first token: Sampler.sample(logits, temp, top_p)
        │  Yield first token
        │
        │  Phase 2: DECODE (loop max_tokens - 1 times)
        │  ┌─────────────────────────────────────────────┐
        │  │ For each layer i:                           │
        │  │   weights = loader.get_weights(i)           │
        │  │   output = components[i](single_token, ...) │
        │  │   KV reused from prefill cache              │
        │  │   Prefetch next layers                      │
        │  └─────────────────────────────────────────────┘
        │
        │  Sample next token
        │  _stream_delta(tokenizer, all_tokens, decoded_text)
        │    → Rolling-window overlap matching (8 tokens)
        │    → Robust to BPE subword merge instability
        │  Yield delta text
        │
        │  If EOS or max_tokens → break
        │
        └─ Yield final {"token": "", "finish_reason": "stop"|"length"}
```

**Key details:**
- The two-phase approach (prefill + decode) mirrors how transformers work internally, but at the Python level
- Prefill processes the entire prompt in one pass; decode generates one token at a time
- `asyncio.to_thread` keeps the event loop free during compute-heavy passes
- `_stream_delta` uses rolling-window overlap matching instead of simple prefix subtraction, which is more robust against BPE tokenizer edge cases
- The "length" finish_reason is reported when the loop exhausts max_tokens without hitting EOS

---

## 8. RAG Ingestion Pipeline

Transforms uploaded documents into searchable vector embeddings.

**Entry point:** `POST /v1/rag/upload` (multipart form)

```
POST /v1/rag/upload
  Body: multipart form with file + optional metadata
  │
  ▼ Read file content (text extraction from upload)
  │
  ▼ VectorStoreManager.ingest_text(text, filename)
  │
  ├─ 1. Generate document ID
  │     SHA-256 hash of text content, first 12 hex chars
  │     Format: "doc_{hash}"
  │     Purpose: deterministic — same content always gets same ID
  │
  ├─ 2. Chunk text
  │     DocumentChunker.chunk_text(text, document_id)
  │       chunk_size: configurable (default from config)
  │       chunk_overlap: configurable
  │       max_chunks: configurable cap
  │     Add filename to chunk metadata
  │     Returns: List[TextChunk]
  │
  ├─ 3. Store chunks in metadata DB
  │     metadata_store.insert_chunks_batch(chunks)
  │     SQLite table: chunks with content, metadata, document_id
  │
  ├─ 4. Generate embeddings
  │     texts = [chunk.content for chunk in chunks]
  │     embedding_pipeline.embed_texts(texts, batch_size=32)
  │       Uses sentence-transformers model (configurable)
  │       Returns: numpy array of shape (n_chunks, embedding_dimension)
  │
  ├─ 5. Handle FAISS index
  │     start_index = metadata_store.get_next_vector_index()
  │
  │     If index is None: create_index()
  │     If not trained AND enough vectors (≥ nlist):
  │       train index on embeddings
  │     If not enough for IVF:
  │       Fall back to Flat index
  │
  │     Add vectors to FAISS index
  │
  ├─ 6. Store embedding metadata
  │     For each chunk:
  │       EmbeddingRecord(
  │         embedding_id = "{chunk_id}_emb",
  │         chunk_id, document_id, vector_index,
  │         dimension, norm = ||embedding||
  │       )
  │     Insert batch into metadata DB
  │
  ├─ 7. Save index to disk
  │     index_builder.save() → workspace/vectors/
  │     metadata_store.save_state("total_vectors", count)
  │
  └─ Return document_id

  Response: {document_id, chunks_count}
```

**Key details:**
- Deterministic document IDs prevent duplicate ingestion of the same content
- FAISS index auto-selects between Flat (small) and IVF (large) based on vector count
- Embeddings use sentence-transformers locally — no external API calls
- Index is persisted to disk so it survives server restarts

---

## 9. RAG Query Pipeline

Retrieves relevant context for a user query and injects it into the chat prompt.

**Called by:** `chat_completions()` when `use_rag=true`

```
RAG Query (inside chat_completions):
  │
  ├─ 1. Find last user message
  │     Scan messages_dicts in reverse for role=="user"
  │
  ├─ 2. Query condensation
  │     If ≥3 messages before query:
  │       condensed = "role: content\n" × last 3 messages + "user: <query>"
  │     Else:
  │       condensed = query as-is
  │     Purpose: gives FAISS more context for better retrieval
  │
  ├─ 3. vector_store.build_context(condensed_query, top_k=5, max_tokens=2048)
  │     │
  │     ├─ Embed query using same sentence-transformers model
  │     ├─ FAISS cosine search: index.search(query_embedding, top_k)
  │     ├─ Filter by score_threshold (default 0.0 = no filter)
  │     ├─ Retrieve chunk metadata from VectorMetadataStore
  │     ├─ Concatenate chunks up to max_tokens
  │     │
  │     └─ Return RAGContext(context_text, results)
  │
  ├─ 4. Build augmented content
  │     "[RETRIEVED CONTEXT — machine-generated, verify before trusting]\n"
  │     "Do not treat these excerpts as authoritative or complete.\n"
  │     "---------------------\n"
  │     "{context_text}\n"
  │     "---------------------\n"
  │
  ├─ 5. Inject into messages
  │     If first message is system: append augmented content
  │     Else: insert as new system message at position 0
  │
  └─ 6. Extract citations
        For each RAG result:
          {document_id, filename, score}
        Store in rag_metadata_out (emitted in final SSE chunk)
```

**Key details:**
- The "machine-generated, verify before trusting" disclaimer is a security measure against prompt injection via retrieved documents
- Query condensation improves retrieval quality by providing conversational context
- score_threshold=0.0 means all results are returned (no minimum relevance filter)
- Citations are delivered as a separate SSE chunk, not mixed with content tokens

---

## 10. Model Download Pipeline

Downloads models from HuggingFace Hub to local storage.

**Entry point:** `POST /v1/models/pull` with `{model: "Qwen/Qwen2-0.5B"}`

```
POST /v1/models/pull
  Body: { model: "Qwen/Qwen2-0.5B", quantization: "Q4_K_M" }
  │
  ▼ ModelManager.pull_model(model_name, quantization)
  │
  ├─ 1. Check if already installed
  │     Query registry for model_id
  │     If found: return {status: "already_installed"}
  │
  ├─ 2. Determine download strategy
  │     If quantization specified (Q4_K_M, Q5_K_M, Q8_0):
  │       Use HuggingFaceProvider to find quantized GGUF
  │     Else:
  │       Download full HuggingFace repo
  │
  ├─ 3. Download files
  │     HuggingFaceProvider.download()
  │       Uses huggingface_hub.snapshot_download() or hf_hub_download()
  │       Progress callbacks update download_status dict
  │       Destination: workspace/models/installed/<model_name>/
  │
  ├─ 4. Write metadata.json
  │     {quant_method, download_date, source_repo, ...}
  │     Maps GGUF quant strings to quant_method="gguf"
  │
  ├─ 5. Register in database
  │     Insert into models table in sovereign.db
  │     Fields: id, name, path, size, quant_method, modes_supported, created_at
  │
  └─ Return {status: "downloaded", model_id, size}

  Background: ModelManager scanner picks up the new model on next scan
```

**Key details:**
- Quantized downloads are much smaller (Q4_K_M ≈ 40% of full model size)
- Progress callbacks allow the frontend to show download progress in real-time
- metadata.json is critical — EngineFactory reads quant_method from it at load time

---

## 11. Model Deletion Pipeline

Removes a model from disk and the registry.

**Entry point:** `DELETE /v1/models/{model_id}`

```
DELETE /v1/models/{model_id}
  │
  ▼ ModelManager.delete_model(model_id)
  │
  ├─ 1. Resolve model
  │     get_model(model_id) → {id, path, ...}
  │     If not found: raise ValueError
  │
  ├─ 2. Safety check: path root guard
  │     Verify model path is within workspace/models/ directory
  │     Prevents deletion if registry metadata is tampered with
  │     If outside allowed path: refuse deletion
  │
  ├─ 3. Delete from disk
  │     If directory: shutil.rmtree(path)
  │     If file: os.remove(path)
  │
  ├─ 4. Delete from registry
  │     Remove from sovereign.db models table
  │
  ├─ 5. Delete split cache (if exists)
  │     Check workspace/offload_cache/<model_name>/
  │     If exists: remove it too
  │
  └─ Return {status: "deleted", model_id}
```

**Key details:**
- The path root guard is a security measure against path traversal attacks via crafted registry entries
- Split model caches in offload_cache are cleaned up alongside the base model

---

## 12. Mode Switch Pipeline

Reloads the current model in a different execution mode (fullram ↔ layerstream).

**Entry point:** `POST /v1/chat/mode/switch?mode=layerstream`

```
POST /v1/chat/mode/switch?mode=layerstream
  │
  ▼ switch_mode() in chat.py
  │
  ├─ 1. Check app.state.active_model
  │     If None: HTTP 400 "No model loaded"
  │
  ├─ 2. Delegate to ModelManager.load_model()
  │     model_id = app.state.active_model
  │     mode = request.query_params["mode"]
  │
  │     This triggers the full Model Loading Pipeline (#4)
  │     with the new mode value:
  │       - Old engine is unloaded after new one loads
  │       - Disk preflight runs for layerstream
  │       - Engine factory creates the appropriate engine
  │
  └─ Return {status: "loaded", model, mode}
```

**Key details:**
- Mode switching is effectively a full model reload with a different mode
- The old model's weights stay on disk — only the execution engine changes
- LayerStream mode requires the model to be split first (done automatically on first load)

---

## 13. Plugin Execution Pipeline

Dynamically loads and executes user-written Python plugins.

**Entry point:** `POST /v1/plugins/{plugin_id}/execute`

```
POST /v1/plugins/{plugin_id}/execute
  Body: { action: "analyze", params: {...} }
  │
  ▼ PluginManager.execute_action(plugin_id, action, params)
  │
  ├─ 1. Find plugin instance
  │     plugins[plugin_id] → PluginInterface instance
  │     If not found: raise ValueError
  │
  ├─ 2. Validate action
  │     Check action in plugin.get_actions()
  │     If not: raise ValueError
  │
  ├─ 3. Execute in sandbox
  │     PluginSandbox.execute_with_timeout(
  │       plugin.execute(action, params),
  │       timeout=30  seconds
  │     )
  │     Note: timeout-only sandbox — no FS/network/memory isolation on Windows
  │
  └─ Return result

Plugin loading (at startup):
  │
  ├─ Scan backend/app/plugins/builtin/ + workspace/plugins/
  ├─ For each .py file:
  │     importlib.util.spec_from_file_location()
  │     importlib.util.module_from_spec()
  │     module.__loader__.exec_module()
  │     Scan module for PluginInterface subclasses
  │     Instantiate → call initialize() → store in plugins dict
  └─ On shutdown: call cleanup() on each plugin
```

**Key details:**
- Plugins are loaded via importlib — no registration step needed, just drop a .py file
- The 30-second timeout prevents runaway plugins from blocking the server
- Sandbox is intentionally minimal — documented gap, no process-level isolation on Windows

---

## 14. Settings Pipeline

Per-section CRUD for user configuration.

**Entry points:** `GET/POST/PUT/DELETE /v1/settings/{section}`

```
GET /v1/settings/general
  │
  ▼ SettingsService.get_section("general")
  │
  ├─ SettingsDatabase.get_settings(section)
  │     SELECT data FROM settings WHERE section = ?
  │     Parse JSON blob → dict
  │
  └─ Return {startup_model, default_mode, ...}

POST /v1/settings/general
  Body: {startup_model: "Qwen2-0.5B", default_mode: "fullram"}
  │
  ▼ SettingsService.update_section("general", data)
  │
  ├─ Merge with existing data (partial update)
  ├─ Serialize to JSON
  ├─ SettingsDatabase.save_settings(section, json_data)
  │     INSERT OR REPLACE INTO settings (section, data) VALUES (?, ?)
  │
  └─ Return {status: "updated"}

Special settings endpoints:
  POST /v1/settings/security/password  — bcrypt hash, stored in password_hash
  POST /v1/settings/security/pin      — bcrypt hash, stored in pin_hash
  POST /v1/settings/agents            — CRUD for agent definitions
```

**Key details:**
- Settings are stored as JSON blobs, not individual columns — flexible schema
- System prompt is dynamically constructed from personalization settings on every chat request
- Password/PIN use bcrypt with configurable rounds — no plaintext storage
- Agent system instructions are injected into chat prompts when active

---

## 15. System Status Pipeline

Returns hardware info and system health.

**Entry point:** `GET /v1/system/status`

```
GET /v1/system/status
  │
  ▼ system.py:system_status()
  │
  ├─ 1. Hardware profile (from app.state.hardware_profile)
  │     CPU, RAM, GPU, disk info (detected at startup)
  │
  ├─ 2. Model status
  │     active_engine: loaded or None
  │     active_model: model_id or None
  │     active_mode: "fullram" | "layerstream" or None
  │
  ├─ 3. Engine memory usage
  │     if active_engine:
  │       engine.get_memory_usage()
  │         FullRAM: RSS, peak WSET, VRAM allocated/peak
  │         LayerStream: RAM, peak VRAM, KV cache size, layers loaded
  │
  ├─ 4. Vector store stats
  │     vector_store.get_stats()
  │       total_vectors, total_chunks, total_documents, index_type
  │
  ├─ 5. Plugin status
  │     List of loaded plugins with their actions
  │
  └─ Return aggregated status dict
```

---

## 16. WebSocket Metrics Pipeline

Real-time system metrics broadcast every 1 second.

**Entry point:** `ws://127.0.0.1:8000/ws/metrics`

```
WebSocket /ws/metrics
  │
  ▼ Connect
  │
  ├─ Every 1 second:
  │     Collect:
  │       CPU usage (psutil)
  │       RAM usage (psutil)
  │       GPU usage (torch.cuda if available)
  │       Active model info
  │       Engine memory stats
  │       Active sessions count
  │
  │     Serialize to JSON
  │     Send via WebSocket
  │
  └─ On disconnect: stop broadcasting

Frontend (React):
  │
  ├─ Connect to ws://127.0.0.1:8000/ws/metrics
  ├─ Auto-reconnect on disconnect
  ├─ Update Zustand store with metrics
  └─ Render in dashboard components
```

---

## 17. Electron Startup Pipeline

Desktop app boot sequence — parallel UI and backend startup.

```
npm start (from electron/)
  │
  ▼ Electron main process starts (main.js)
  │
  ├─ 1. Register custom protocol
  │     protocol.registerSchemesAsPrivileged([{scheme: "app", ...}])
  │     protocol.handle("app://", handler)
  │       Serves frontend/out/ files
  │       Directory indexing: look for index.html in subdirs
  │       SPA fallback: serve root index.html for unknown paths
  │
  ├─ 2. app.whenReady()
  │     │
  │     ├─ createWindow()
  │     │   new BrowserWindow({width: 1400, height: 900, ...})
  │     │   Show when ready-to-show (prevents white flash)
  │     │   Load URL:
  │     │     Dev mode (USE_DEV_SERVER=true): http://localhost:3000
  │     │     Production: app://-/
  │     │
  │     ├─ createMenu() — custom application menu
  │     ├─ createTray() — system tray with minimize-to-tray
  │     │
  │     └─ startBackend()
  │         │
  │         ├─ Find Python executable:
  │         │   Check .venv/bin/python or .venv/Scripts/python
  │         │   Fallback to system python
  │         │
  │         ├─ Spawn: python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
  │         │   Working directory: ../backend/
  │         │   Pipe stdout/stderr
  │         │
  │         ├─ Wait for "Uvicorn running" in stdout (or 10s timeout)
  │         │   Resolve even on error (app opens regardless)
  │         │
  │         └─ Store child process reference for shutdown
  │
  ├─ 3. IPC handlers
  │     get-app-path, get-version, show-notification
  │     show-open-dialog, show-save-dialog
  │     restart-backend — kill + respawn Python process
  │
  └─ 4. Shutdown
        before-quit → stopBackend()
          Windows: taskkill /F /PID
          Unix: SIGTERM → wait → SIGKILL
        window-all-closed → app.quit() (except macOS)
```

**Key details:**
- UI renders immediately while backend boots in parallel — no blocking
- The custom `app://` protocol serves static files without a web server
- Backend restart via IPC kills the old process and spawns a new one
- The 10-second timeout prevents the app from hanging if Python is slow to start

---

## 18. CLI Chat Pipeline

Interactive terminal chat via the `sovereign chat` command.

```
sovereign chat [model_name]
  │
  ▼ typer CLI entry point
  │
  ├─ 1. Resolve model
  │     If model_name provided: use it
  │     Else: use settings default (startup_model)
  │
  ├─ 2. Load model
  │     HTTP POST to 127.0.0.1:8000/v1/models/load
  │     If server not running: start it first (sovereign serve)
  │
  ├─ 3. Start REPL
  │     prompt_toolkit for input
  │     rich for formatted output
  │
  │     Loop:
  │       │
  │       ├─ Input: prompt_toolkit prompt (with history)
  │       │
  │       ├─ HTTP POST to /v1/chat/completions
  │       │   stream: true
  │       │
  │       ├─ Parse SSE response
  │       │   Stream tokens to terminal in real-time
  │       │   Handle <think> blocks (display separately or skip)
  │       │
  │       ├─ Display response with rich formatting
  │       │
  │       └─ Continue loop (or exit on /quit, Ctrl+C)
  │
  └─ On exit: optional model unload
```

---

## 19. LayerStream Weight Splitting Pipeline

Splits a consolidated model into per-layer files for LayerStream inference.

```
WeightSplitter.split_and_save(dtype)
  │
  ├─ 1. Load source model
  │     AutoConfig.from_pretrained(model_path)
  │     AutoModelForCausalLM.from_pretrained(model_path, torch_dtype=dtype)
  │
  ├─ 2. Split components
  │     embed_tokens → embed.safetensors
  │     layers[0] → layer_0.safetensors
  │     layers[1] → layer_1.safetensors
  │     ...
  │     layers[N] → layer_N.safetensors
  │     model.norm → norm.safetensors
  │     lm_head → lm_head.safetensors
  │
  ├─ 3. Write quant_config.json
  │     {quant_method: "none"|"int8"|"int4"|"gguf"}
  │
  ├─ 4. Copy tokenizer files
  │     tokenizer.json, tokenizer_config.json, vocab.json, merges.txt
  │     (from source model directory)
  │
  └─ 5. Save to offload cache
        workspace/offload_cache/<model_name>/
        Each component saved via safetensors.torch.save_file()

Output structure:
  offload_cache/Qwen2-0.5B/
    embed.safetensors
    layer_0.safetensors
    layer_1.safetensors
    ...
    layer_23.safetensors
    norm.safetensors
    lm_head.safetensors
    quant_config.json
    tokenizer.json
    tokenizer_config.json
    config.json
```

**Key details:**
- Splitting is a one-time cost — subsequent loads skip this step
- The config.json is copied so LayerStream can reconstruct the model skeleton
- quant_method determines whether dequantization is needed at load time

---

## 20. LayerStream Prefetch & Cache Pipeline

Manages layer weight loading with asynchronous prefetching and LRU eviction.

```
LayerWeightLoader.get_weights(layer_idx)
  │
  ├─ 1. Check LRU cache
  │     If layer_idx in cache: return cached weights
  │
  ├─ 2. Check pinned paths
  │     embed, norm, lm_head are "pinned" — never evicted
  │
  ├─ 3. Load from disk
  │     _load_file(weights_dir / f"layer_{layer_idx}.safetensors")
  │       safetensors.torch.safe_open(path, framework="pt")
  │       Read weight tensors into memory
  │
  ├─ 4. Dequantize (if needed)
  │     dequantize_on_device(tensor, quant_method)
  │       int8: scale + reshape → float tensor
  │       int4: packed 2-values/byte → unpack + scale → float tensor
  │       none/gguf: pass through
  │
  ├─ 5. Store in LRU cache
  │     cache[layer_idx] = weights
  │
  └─ 6. Enforce byte budget
        _enforce_budget()
          Calculate total cache size in bytes
          While total > budget:
            Pop least-recently-used non-pinned entry
            Delete from cache, free memory
          Budget = max(largest_layer × 4.5, 256MB)

Prefetch (concurrent with current layer execution):
  │
  ├─ ThreadPoolExecutor(prefetch_depth=3)
  │     Submit load tasks for layers [current+1, current+2, current+3]
  │
  ├─ Futures stored in prefetch queue
  │     When get_weights() is called for a prefetched layer:
  │       Await the future → weights already in memory
  │
  └─ Cleanup on engine unload:
        executor.shutdown(wait=False)
        Clear all caches
        gc.collect()
        torch.cuda.empty_cache()
```

**Key details:**
- The 3-layer prefetch depth means while layer N is computing, layers N+1, N+2, N+3 are loading from disk
- LRU eviction ensures the most recently used layers stay in memory
- Pinned paths (embed/norm/lm_head) are always needed and never evicted
- The 4.5× multiplier provides headroom for the current layer + prefetched layers
- Dequantization happens on device (GPU/CPU) after loading — raw bytes are read from disk

---

## Flow Color Key

For reference when tracing flows:

| Color | Meaning |
|-------|---------|
| **Orange** | Primary data flow (user input → response) |
| **Blue** | Control/orchestration flow (engine selection, mode switching) |
| **Green** | Validation/success path (RAG context injection, settings CRUD) |
| **Purple** | Intelligence flow (inference, embedding, sampling) |
| **Red** | Error/rollback path (load failure, disconnect, disk full) |
| **Gray** | Metadata/monitoring (metrics, logging, stats) |

---

*Generated from source code analysis of SovereignAI Edge codebase.*
*Last updated: August 26, 2026.*
