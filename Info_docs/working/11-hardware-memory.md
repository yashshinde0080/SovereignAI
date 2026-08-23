# Hardware Detection & Memory Management

Hardware profiling drives mode selection (fullram vs layerstream) and resource allocation.

## Hardware Detection

**File:** `backend/app/core/hardware_detector.py`

`HardwareDetector.detect()` returns:

| Field | Source |
|---|---|
| `cpu_name` | Platform-specific (Win registry, /proc/cpuinfo, sysctl) |
| `cpu_cores` | `psutil.cpu_count(logical=False)` |
| `cpu_threads` | `psutil.cpu_count(logical=True)` |
| `has_avx2` | `/proc/cpuinfo` string match |
| `has_avx512` | `/proc/cpuinfo` string match |
| `ram_total_gb` | `psutil.virtual_memory().total` |
| `gpu_name` | `nvidia-smi --query-gpu=name` |
| `gpu_vram_gb` | `nvidia-smi --query-gpu=memory.total` |
| `disk_type` | SSD/HDD via `/sys/block/sda/queue/rotational` |
| `disk_speed_mb_s` | 10MB write benchmark |

`detect_hardware()` (`hardware_llmfit.py`) — tries llmfit-powered detection first, falls back to legacy `HardwareDetector`.

## Memory Manager

**File:** `backend/app/core/memory_manager.py`

`MemoryManager.suggest_mode(model_size_bytes, model_metadata)` — returns `"fullram"`, `"layerstream"`, or `"insufficient"`.

### Mode Selection (auto)

**Priority 1: llmfit scoring** (when model_metadata has name/id):
```python
from llmfit import score_model_fit
from llmfit.hardware import probe_hardware

hw = probe_hardware()
fit = score_model_fit(model_name, hw)

if fit.fit_score > 0.85 and fit.ram_required_gb < hw.ram_total_gb * 0.7:
    return "fullram"
elif fit.fit_score > 0.6:
    return "layerstream"
else:
    return "insufficient"
```

**Priority 2: Threshold-based fallback** (when llmfit unavailable):

Residency multipliers:
- GGUF models: `ram_residency = 4.0x` (transformers dequants to fp32 on CPU)
- fp16/fp32 models: `ram_residency = 2.0x`
- CUDA VRAM: `vram_residency = 2.0x` (GGUF) or `1.0x` (fp16)
- Headroom: `1.15x`

```
CUDA available:
  if model_size * vram_residency * 1.15 < free_vram → fullram
  
RAM check:
  if model_size * ram_residency * 1.15 < available_ram → fullram
  elif model_size * 0.1 < available_ram → layerstream
  else → insufficient
```

### Non-generative Override

In `EngineFactory.create_engine()`:
```python
if suggested == "layerstream" and not is_generative:
    mode = "fullram"  # non-generative tasks force fullram
```

## EngineFactory Mode Selection

`EngineFactory.create_engine()` ties it together:

1. `TaskResolver.resolve()` → is_generative
2. `MemoryManager.suggest_mode()` → fullram/layerstream/insufficient
3. Non-generative + layerstream → forced fullram
4. `insufficient` → RuntimeError

## RAM Usage Reporting

Each engine reports memory via `get_memory_usage()`:

**FullRAMEngine:**
```python
{"ram_used_gb": process.rss / GB, "peak_ram_gb": ..., "vram_used_mb": ..., "vram_peak_mb": ...}
```

**LayerStreamEngine:**
```python
{"ram_used_gb": peak_ram_mb/1024, "layers_loaded": N, "kv_cache_mb": ..., "peak_vram_mb": ...}
```

## Measured Performance

| Engine | Model | tok/s | Notes |
|---|---|---|---|
| FullRAM CPU | 469MB Q4_K_M GGUF | 3.84 | Default for fitting models |
| FullRAM CUDA | 469MB Q4_K_M GGUF | 24.0 | With GPU |
| LayerStream | Qwen2-0.5B int4 | 8.0 | After 08-17 device-cache fix |
| LayerStream | Qwen3.5-0.8B hybrid | 0.48 | Bounded by missing causal-conv1d |

GGUF residency: 469 MB on-disk → ~2 GB RSS (~4x) on both CPU and CUDA.

## Related

- [[12-task-resolution]] — Task type determines if layerstream is allowed
- [[04-engine-system]] — Engine creation uses mode selection
- [[05-layer-by-layer]] — LayerStream's memory-bounded execution
- [[03-model-loading]] — Load flow uses mode selection
- [[00-architecture-overview]] — Hardware detection at startup
