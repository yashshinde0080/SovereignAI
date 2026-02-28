import asyncio
import json
import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, WebSocket, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.registry import ModelRegistry
from app.plugins.plugin_manager import PluginManager
from app.services.downloader import Downloader
from app.core.engine_factory import EngineFactory
from app.core.hardware_detector import HardwareDetector
from app.schemas.models import ChatRequest, ModelPullRequest, ModeSwitchRequest, BenchmarkRequest

logger = logging.getLogger("sovereign-backend")

router = APIRouter(prefix="/v1")
registry = ModelRegistry()
hardware = HardwareDetector()
plugin_manager = PluginManager()

# Global state to hold current running model and mode
current_state = {
    "model": "llama3:8b",
    "mode": "fullram",
    "status": "idle",
    "ram_usage": 0,
    "tps": 0,
    "disk_io": 0,
    "kv_cache": 0
}

@router.get("/system")
def get_system():
    return hardware.get_profile()

@router.get("/models")
def list_models():
    return registry.get_all_models()

async def download_callback(model_name: str, progress: float):
    # In a real app we would use websockets or SSE for UI updates
    logger.info(f"Downloading {model_name}: {progress:.2f}%")

@router.post("/models/pull")
async def pull_model(req: ModelPullRequest, background_tasks: BackgroundTasks):
    if req.name in registry.get_all_models() and registry.get_all_models()[req.name].get("downloaded"):
        return {"status": "already downloaded"}

    async def do_download():
        current_state["status"] = "downloading"
        success = await Downloader.download_model(req.name, callback=download_callback)
        if success:
            registry.register_model(req.name, {
                "id": f"{req.name.replace(':', '-')}",
                "source": "huggingface",
                "size_gb": 4.5,
                "quant": "Q4_K_M",
                "downloaded": True,
                "modes": ["fullram", "layerstream"]
            })
            current_state["status"] = "idle"

    background_tasks.add_task(do_download)
    return {"status": "download started"}

@router.delete("/models/{name}")
def remove_model(name: str):
    if registry.remove_model(name):
        return {"status": "removed"}
    raise HTTPException(status_code=404, detail="Model not found")

@router.post("/chat")
async def chat(req: ChatRequest):
    model_data = registry.get_model(req.model)
    if not model_data or not model_data.get("downloaded"):
        raise HTTPException(status_code=404, detail="Model not found or not downloaded")

    current_state["model"] = req.model
    current_state["mode"] = req.mode if req.mode != "auto" else "fullram"

    engine = EngineFactory.get_engine(current_state["mode"], current_state["model"])
    prompt = " ".join([m.get("content", "") for m in req.messages])

    async def stream_generator():
        current_state["status"] = "generating"
        async for token in engine.chat_stream(prompt):
            # simulate TPS and IO updates
            current_state["tps"] = 24.5
            current_state["disk_io"] = 0 if current_state["mode"] == "fullram" else 1500
            yield json.dumps({"token": token}) + "\n"
        current_state["status"] = "idle"
        current_state["tps"] = 0
        current_state["disk_io"] = 0

    if req.stream:
        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    else:
        # non-streaming (mock)
        resp = "Non-streaming generated response mock."
        return {"response": resp}

@router.post("/mode/switch")
def switch_mode(req: ModeSwitchRequest):
    if req.mode not in ["fullram", "layerstream", "auto"]:
        raise HTTPException(status_code=400, detail="Invalid mode")
    current_state["mode"] = req.mode
    return {"status": "mode switched", "new_mode": req.mode}

@router.post("/benchmark")
def benchmark(req: BenchmarkRequest):
    # Mock benchmark
    return {
        "model": req.model,
        "mode": current_state["mode"],
        "tokens_per_sec": 21.4,
        "first_token_latency_ms": 320,
        "peak_ram_gb": 9.6
    }

@router.get("/plugins")
def list_plugins():
    return plugin_manager.get_all_plugins()

class PluginExecuteRequest(BaseModel):
    name: str
    payload: Any

@router.post("/plugins/execute")
def execute_plugin(req: PluginExecuteRequest):
    try:
        return plugin_manager.execute_plugin(req.name, req.payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
