# WebSocket Metrics

Real-time system metrics streamed via WebSocket at `/ws/metrics`.

## Endpoint

```
WS /ws/metrics
```

## Metrics Broadcast

1-second cycle per client:

```json
{
    "cpu_percent": 12.5,
    "gpu_percent": 45.0,
    "gpu_vram_used": 2.1,
    "ram_used_gb": 6.4,
    "ram_total_gb": 16.0,
    "ram_percent": 40.0,
    "disk_read_mb": 1.2,
    "disk_write_mb": 0.5,
    "model_loaded": "Qwen2-0.5B",
    "mode": "layerstream",
    "task_type": "causal_lm",
    "is_generative": true,
    "engine_stats": {
        "peak_ram_mb": 1024,
        "layers_loaded": 24,
        "kv_cache_size_mb": 128
    }
}
```

## Collection

| Metric | Source | Method |
|---|---|---|
| CPU | `psutil.cpu_percent(interval=0.1)` | 0.1s sample + 0.9s sleep = 1s cycle |
| RAM | `psutil.virtual_memory()` | `.used`, `.total`, `.percent` |
| GPU | `nvidia-smi --query-gpu=utilization.gpu,memory.used` | subprocess, 0.5s timeout |
| Disk I/O | `psutil.disk_io_counters()` | Delta between samples (MB) |
| Engine | `app.state.active_engine.get_memory_usage()` | Per-engine metrics |

## Client Management

```python
clients: Set[WebSocket] = set()

@router.websocket("/ws/metrics")
async def metrics_websocket(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    # ... broadcast loop ...
    clients.remove(websocket)
```

- Auto-cleanup on disconnect
- `broadcast_metrics()` — push to all connected clients

## Frontend Usage

The React frontend connects to `ws://localhost:8000/ws/metrics` and renders:
- CPU/RAM/GPU gauges
- Model loaded status
- Engine-specific stats (layers, KV cache, VRAM)

## Related

- [[00-architecture-overview]] — WebSocket router in startup
- [[04-engine-system]] — Engine stats reported
- [[11-hardware-memory]] — Hardware metrics collection
