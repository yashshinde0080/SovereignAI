# Model Loading Flow

Model loading is orchestrated by `ModelManager` → `EngineFactory` → Engine.

## Load Sequence

```
POST /v1/models/load
  → ModelManager.load_model(model_id, mode="auto")
    1. Registry lookup (list_models → dict lookup)
    2. Fuzzy match if not found (normalize slashes/colons)
    3. Wait for background scan if model not in registry
    4. Acquire _load_lock (asyncio.Lock — serializes loads)
    5. _load_model_locked()
       a. Split model handling (auto → layerstream; fullram → redirect to base)
       b. Disk-full preflight for LayerStream
       c. EngineFactory.create_engine(model_path, mode, model_metadata)
       d. engine.load()
       e. Unload previous engine
       f. Update app.state (active_engine, active_model, active_mode)
```

## Model Registry Lookup

`ModelManager.load_model()` first tries `list_models()` → dict lookup by ID. Only awaits the background scan task if the model isn't found yet (lazy wait pattern).

`_fuzzy_match_model()` handles display names:
- Normalizes `/` → `-`, `:` → `-`, lowercase
- Prefers exact normalized matches over containment
- Split variants (`split:...`) are excluded from fuzzy matches (always match the base)

## Split Model Handling

If `mode == "fullram"` and model ID starts with `split:`:
1. Strip `split:` prefix to get the base model name
2. Fuzzy-match the base model from `all_models`
3. Redirect `model_path` to the base model's path
4. FullRAM loads the consolidated model, not the per-layer files

If `mode == "auto"` and model is split → forced to `layerstream`.

## Disk-Full Preflight

Before LayerStream load:
```python
free_bytes = shutil.disk_usage(settings.workspace_dir).free
need_bytes = model_size_bytes  # from registry size_gb
if free_bytes < need_bytes:
    raise RuntimeError("Not enough free disk space for LayerStream swap cache")
```

## EngineFactory

`EngineFactory.create_engine(model_path, mode, model_metadata)`:

1. **Size from registry** — uses `size_gb` metadata to avoid O(n) rglob scan
2. **Path resolution** — determines `engine_model_path_str` (file or directory)
3. **TaskResolver** — `AutoConfig.from_pretrained()` → task_type, is_generative
4. **Mode selection** (auto):
   - `MemoryManager.suggest_mode(model_size, model_metadata)` — llmfit scoring
   - Non-generative + layerstream → forced to fullram
   - `insufficient` → RuntimeError
5. **Engine instantiation** — `FullRAMEngine(...)` or `LayerStreamEngine(...)`

See [[12-task-resolution]] and [[11-hardware-memory]] for mode selection details.

## Model Download Flow

```
POST /v1/models/download
  → ModelManager.download_model(model_name, quant="Q4_K_M")
    1. download_status dict initialized
    2. HuggingFaceProvider.get_model_info()
    3. Create model_dir under workspace/models/installed/
    4. provider.download() — GGUF file or full repo
    5. Calculate total_size_bytes
    6. Create metadata.json
    7. registry.add_model()
```

See [[07-model-downloading]] for download details.

## Background Model Scan

`ModelManager.scan_installed()` runs in background at startup:
- Scans `workspace/models/installed/` folders and `.gguf` files
- Scans `workspace/offload_cache/` for pre-split models
- Batch upserts all discovered models (single DB transaction)
- Cleans up stale registry entries (models deleted from disk)

## Error Recovery

If `engine.load()` fails:
1. `engine.unload()` — clean up partial state
2. Restore previous engine/model/mode to `app.state`
3. Re-raise the exception
4. Previous engine stays active (user doesn't lose their model)

## Concurrent Load Serialization

`_load_lock = asyncio.Lock()` — only one model can load at a time. Two concurrent load requests would both try to unload the active engine and fight over `app.state`.

## Related

- [[04-engine-system]] — Engine internals after loading
- [[05-layer-by-layer]] — LayerStream's split + load process
- [[06-weight-splitting]] — How models are split for LayerStream
- [[07-model-downloading]] — Model download from HuggingFace
- [[12-task-resolution]] — Task type determination
- [[11-hardware-memory]] — Mode selection (auto/fullram/layerstream)
