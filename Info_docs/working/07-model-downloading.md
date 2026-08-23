# Model Downloading

Models are downloaded from HuggingFace Hub via `HuggingFaceProvider` and stored in `workspace/models/installed/`.

## Download Flow

```
POST /v1/models/download
  → ModelManager.download_model(model_name, quant="Q4_K_M")
    1. Initialize download_status dict
    2. HuggingFaceProvider.get_model_info(model_name)
    3. Create model_dir: workspace/models/installed/{safe_name}/
    4. provider.download(model_id, destination, quantization, progress_callback)
    5. Calculate total_size_bytes
    6. Create metadata.json
    7. registry.add_model(metadata)
```

## HuggingFaceProvider

**File:** `backend/app/providers/huggingface.py`

### Search

- Queries HF API with `filter=gguf`, sorted by downloads
- Filters for GGUF repos using pattern matching
- Returns `ModelMetadata` with repo_id, files, quantizations

### Model Info

- Resolves short-form IDs (e.g. `llama3:8b`) to full repo IDs via search
- Lists files from `/api/models/{repo_id}/tree/main`
- Detects quantization from filename patterns (Q4_K_M, Q5_K_M, Q8_0, etc.)
- Filters files < 10MB (not model weights)

### Single File Download

1. Check for partial download (`.part` file)
2. HTTP GET with `Range` header for resume
3. 8MB chunk writes via `aiofiles`
4. Progress updates every second
5. SHA256 checksum verification
6. Rename `.part` → final filename

### Full Repository Download

Uses `huggingface_hub.snapshot_download()`:
1. `HfApi.model_info()` to get total size
2. Ignore patterns: `*.msgpack, *.h5, *.ot, *.ckpt, .git*`
3. `snapshot_download()` with 8 workers, progress tracking
4. Polling task tracks bytes downloaded for progress callbacks

### Auth & TLS

- Bearer token from `config.get("token")`
- Custom CA bundle via `SOVEREIGN_CA_BUNDLE` env var
- Mirror support via `config.get("mirror")`

## Metadata Creation

After download, `metadata.json` is saved:

```json
{
  "id": "model_name",
  "name": "display name",
  "family": "llama|qwen|mistral|...",
  "parameters": "8B|...",
  "quant": "Q4_K_M",
  "quant_method": "gguf|none",
  "size_gb": 4.5,
  "path": "workspace/models/installed/model-name/",
  "checksum": "sha256...",
  "downloaded": true,
  "modes_supported": ["fullram", "layerstream"],
  "created_at": "2026-08-23T..."
}
```

`quant_method` mapping:
- GGUF quant variants (Q4_K_M, Q5_K_M, etc.) → `quant_method: "gguf"`
- Full model repos → `quant_method: "none"` (LayerStream can re-quantize)

## Model Catalog

Custom model definitions (enterprise/USB bundles) loaded from `workspace/plugins/user/models/`:
- `CustomModelCatalog` loads YAML definitions
- Supplements the HuggingFace provider

## Related

- [[03-model-loading]] — Loading downloaded models into engines
- [[06-weight-splitting]] — Splitting downloaded models for LayerStream
- [[12-task-resolution]] — Task type from downloaded model config
- [[04-engine-system]] — Engine creation after download
