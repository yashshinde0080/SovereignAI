import asyncio
import json
import logging
from typing import Dict, Any

from fastapi import APIRouter, WebSocket
from app.api.routes import current_state
from app.core.hardware_detector import HardwareDetector

router = APIRouter()
logger = logging.getLogger("sovereign-websocket")
hardware = HardwareDetector()

@router.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected to metrics")
    try:
        while True:
            # Broadcast the current engine state and hardware metrics
            live_hw = hardware.get_live_metrics()
            metrics = {
                "ram_usage": live_hw["ram_usage_gb"],
                "disk_io": current_state["disk_io"],
                "tokens_per_sec": current_state["tps"],
                "kv_cache": current_state["kv_cache"],
                "mode": current_state["mode"],
                "model": current_state["model"],
                "status": current_state["status"]
            }
            await websocket.send_json(metrics)
            await asyncio.sleep(1.0)
    except Exception as e:
        logger.error(f"WebSocket closed: {e}")
