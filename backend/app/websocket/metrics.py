"""WebSocket Metrics Streaming"""
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Set
import psutil

router = APIRouter()

# Connected clients
clients: Set[WebSocket] = set()


@router.websocket("/ws/metrics")
async def metrics_websocket(websocket: WebSocket):
    """Stream system metrics"""
    await websocket.accept()
    clients.add(websocket)
    
    try:
        # Initialize baseline for calculations
        psutil.cpu_percent(interval=None)
        prev_disk_io = psutil.disk_io_counters()
        
        while True:
            await asyncio.sleep(1)  # Update every second
            
            # Gather metrics
            memory = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=None)
            
            try:
                disk_io = psutil.disk_io_counters()
                if disk_io and prev_disk_io:
                    disk_read = (disk_io.read_bytes - prev_disk_io.read_bytes) / (1024**2)
                    disk_write = (disk_io.write_bytes - prev_disk_io.write_bytes) / (1024**2)
                else:
                    disk_read = 0
                    disk_write = 0
                prev_disk_io = disk_io
            except:
                disk_read = 0
                disk_write = 0
            
            # Get engine stats if available
            engine_stats = {}
            app = websocket.app
            if hasattr(app.state, 'active_engine') and app.state.active_engine:
                engine_stats = app.state.active_engine.get_memory_usage()
            
            metrics = {
                "cpu_percent": cpu,
                "ram_used_gb": round(memory.used / (1024**3), 2),
                "ram_total_gb": round(memory.total / (1024**3), 2),
                "ram_percent": memory.percent,
                "disk_read_mb": round(disk_read, 2),
                "disk_write_mb": round(disk_write, 2),
                "model_loaded": app.state.active_model if hasattr(app.state, 'active_model') else None,
                "mode": app.state.active_mode if hasattr(app.state, 'active_mode') else None,
                "engine_stats": engine_stats
            }
            
            await websocket.send_json(metrics)
            
    except WebSocketDisconnect:
        clients.remove(websocket)
    except Exception:
        clients.discard(websocket)


async def broadcast_metrics(metrics: dict):
    """Broadcast metrics to all connected clients"""
    for client in clients.copy():
        try:
            await client.send_json(metrics)
        except:
            clients.discard(client)