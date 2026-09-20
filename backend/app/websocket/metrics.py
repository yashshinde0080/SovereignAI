"""WebSocket Metrics Streaming"""
import asyncio
import subprocess
from fastapi import APIRouter, WebSocket
from typing import Set, Dict
import psutil

router = APIRouter()

# Connected clients
clients: Set[WebSocket] = set()

# ── Shared GPU cache ──────────────────────────────────────────────────────
# Single nvidia-smi subprocess shared across all WS clients, refreshed
# once per second by a background task.  On non-NVIDIA systems the
# subprocess times out silently and returns zeros.
_gpu_cache: Dict[str, float] = {"gpu_percent": 0, "gpu_vram_used": 0}
_gpu_cache_lock = asyncio.Lock()
_gpu_cache_started = False


def _refresh_gpu_cache_sync() -> Dict[str, float]:
    """Run nvidia-smi once, return GPU stats."""
    try:
        res = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=utilization.gpu,memory.used",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=0.5
        )
        if res.returncode == 0:
            parts = res.stdout.strip().split(",")
            if len(parts) >= 2:
                return {
                    "gpu_percent": float(parts[0]),
                    "gpu_vram_used": round(float(parts[1]) / 1024, 2),
                }
    except Exception:
        pass
    return {"gpu_percent": 0, "gpu_vram_used": 0}


async def _gpu_cache_loop():
    """Background loop: refresh GPU stats once per second."""
    global _gpu_cache
    while True:
        stats = await asyncio.to_thread(_refresh_gpu_cache_sync)
        async with _gpu_cache_lock:
            _gpu_cache = stats
        await asyncio.sleep(1)


async def _ensure_gpu_cache():
    """Start the background GPU poller once."""
    global _gpu_cache_started
    if not _gpu_cache_started:
        _gpu_cache_started = True
        asyncio.ensure_future(_gpu_cache_loop())


async def _get_gpu_stats() -> Dict[str, float]:
    """Read cached GPU stats — non-blocking."""
    async with _gpu_cache_lock:
        return _gpu_cache.copy()


# ── WebSocket handler ─────────────────────────────────────────────────────

@router.websocket("/ws/metrics")
async def metrics_websocket(websocket: WebSocket):
    """Stream system metrics."""
    await websocket.accept()
    clients.add(websocket)
    await _ensure_gpu_cache()

    try:
        # Seed cpu_percent so the first real call returns a delta (non-blocking)
        psutil.cpu_percent(interval=None)
        prev_disk_io = psutil.disk_io_counters()

        while True:
            # Non-blocking: returns CPU% since last call (0ms)
            cpu = psutil.cpu_percent(interval=None)
            await asyncio.sleep(1)

            memory = psutil.virtual_memory()

            try:
                disk_io = psutil.disk_io_counters()
                if disk_io and prev_disk_io:
                    disk_read = (disk_io.read_bytes - prev_disk_io.read_bytes) / (1024**2)
                    disk_write = (disk_io.write_bytes - prev_disk_io.write_bytes) / (1024**2)
                else:
                    disk_read = 0
                    disk_write = 0
                prev_disk_io = disk_io
            except Exception:
                disk_read = 0
                disk_write = 0

            gpu = await _get_gpu_stats()

            task_type = None
            is_generative = False
            app = websocket.app
            engine_stats = {}

            if hasattr(app.state, 'active_engine') and app.state.active_engine:
                engine_stats = app.state.active_engine.get_memory_usage()
                task_metadata = getattr(app.state.active_engine, "task_metadata", {})
                task_type = task_metadata.get("task_type")
                is_generative = task_metadata.get("is_generative", False)

            metrics = {
                "cpu_percent": cpu,
                "gpu_percent": gpu["gpu_percent"],
                "gpu_vram_used": gpu["gpu_vram_used"],
                "ram_used_gb": round(memory.used / (1024**3), 2),
                "ram_total_gb": round(memory.total / (1024**3), 2),
                "ram_percent": memory.percent,
                "disk_read_mb": round(disk_read, 2),
                "disk_write_mb": round(disk_write, 2),
                "model_loaded": app.state.active_model if hasattr(app.state, 'active_model') else None,
                "mode": app.state.active_mode if hasattr(app.state, 'active_mode') else None,
                "task_type": task_type,
                "is_generative": is_generative,
                "engine_stats": engine_stats
            }

            await websocket.send_json(metrics)

    except Exception:  # includes WebSocketDisconnect
        clients.discard(websocket)


async def broadcast_metrics(metrics: dict):
    """Broadcast metrics to all connected clients"""
    for client in clients.copy():
        try:
            await client.send_json(metrics)
        except Exception:
            clients.discard(client)
            try:
                await client.close()
            except Exception:
                pass  # ponytail: socket already dead, nothing to close