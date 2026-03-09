"""
FastAPI router for model management.
All /v1/models/* endpoints.
"""

import logging
import psutil
import torch
from typing import Optional
from pathlib import Path

from fastapi import (
    APIRouter,
    HTTPException,
    BackgroundTasks,
)
from fastapi.responses import StreamingResponse

from .schemas import (
    ModelPullRequest,
    ModelLoadRequest,
    ModelInfo,
    LoadedModelInfo,
    InferenceRequest,
    InferenceResponse,
    SystemResources,
    ErrorResponse,
)
from .config import ModelStatus, MODELS_DIR
from .registry import ModelRegistry
from .downloader import ModelDownloader
from .loader import ModelLoader
from .inference import InferenceEngine

logger = logging.getLogger("sovereign.api.models")

router = APIRouter(prefix="/models", tags=["models"])

# Singletons
registry = ModelRegistry()
downloader = ModelDownloader()
loader = ModelLoader()
engine = InferenceEngine()


# ─── LIST MODELS ─────────────────────────────────────────

@router.get(
    "",
    response_model=list[ModelInfo],
    summary="List all models",
)
async def list_models(
    status: Optional[str] = None,
):
    """
    List all downloaded models.
    Optionally filter by status: ready, loaded, downloading, failed.
    """
    try:
        if status:
            model_status = ModelStatus(status)
            models = registry.list_models(status=model_status)
        else:
            models = registry.list_models()
        return models
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status: {status}",
        )


# ─── GET MODEL ───────────────────────────────────────────

@router.get(
    "/{model_id}",
    response_model=ModelInfo,
    summary="Get model details",
)
async def get_model(model_id: str):
    """Get details of a specific model."""
    model = registry.get_model(model_id)
    if not model:
        raise HTTPException(
            status_code=404,
            detail=f"Model {model_id} not found",
        )
    return model


# ─── PULL MODEL ──────────────────────────────────────────

@router.post(
    "/pull",
    summary="Download model from HuggingFace",
)
async def pull_model(
    request: ModelPullRequest,
    background_tasks: BackgroundTasks,
):
    """
    Download a model from HuggingFace.
    Runs in background. Returns model_id immediately.
    """
    try:
        # Check if already exists
        existing = registry.get_model_by_repo(
            request.repo_id, request.revision
        )
        if existing and existing.status in ("ready", "loaded"):
            return {
                "model_id": existing.id,
                "status": "already_downloaded",
                "message": (
                    f"Model {request.repo_id} already available"
                ),
            }
        
        # Start async download
        model_id = downloader.pull_async(
            repo_id=request.repo_id,
            revision=request.revision,
            task_override=request.task_override,
            trust_remote_code=request.trust_remote_code,
        )
        
        return {
            "model_id": model_id,
            "status": "downloading",
            "message": (
                f"Downloading {request.repo_id}. "
                f"Check status with GET /v1/models/{model_id}"
            ),
        }
    
    except RuntimeError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


# ─── PULL MODEL SYNC ────────────────────────────────────

@router.post(
    "/pull/sync",
    summary="Download model (synchronous)",
)
async def pull_model_sync(request: ModelPullRequest):
    """
    Download model synchronously. Blocks until complete.
    Use for CLI or when you need immediate result.
    """
    try:
        model_id = downloader.pull(
            repo_id=request.repo_id,
            revision=request.revision,
            task_override=request.task_override,
            trust_remote_code=request.trust_remote_code,
        )
        
        model = registry.get_model(model_id)
        return {
            "model_id": model_id,
            "status": "ready",
            "model": model,
        }
    
    except RuntimeError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


# ─── LOAD MODEL ─────────────────────────────────────────

@router.post(
    "/load",
    response_model=LoadedModelInfo,
    summary="Load model into memory",
)
async def load_model(request: ModelLoadRequest):
    """
    Load a model into memory for inference.
    
    IMPORTANT: Only ONE model can be loaded at a time.
    Loading a new model automatically unloads the current one.
    """
    try:
        info = loader.load(
            model_id=request.model_id,
            device=request.device,
            dtype=request.dtype,
        )
        return info
    
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ─── UNLOAD MODEL ───────────────────────────────────────

@router.post(
    "/unload",
    summary="Unload current model from memory",
)
async def unload_model():
    """Unload the currently loaded model. Frees memory."""
    success = loader.unload()
    
    if not success:
        return {
            "status": "no_model_loaded",
            "message": "No model is currently loaded.",
        }
    
    return {
        "status": "unloaded",
        "message": "Model unloaded. Memory freed.",
    }


# ─── GET LOADED MODEL ───────────────────────────────────

@router.get(
    "/loaded/current",
    summary="Get currently loaded model",
)
async def get_loaded_model():
    """Get information about the currently loaded model."""
    info = loader.get_loaded_info()
    
    if not info:
        return {
            "loaded": False,
            "message": "No model currently loaded.",
        }
    
    return {
        "loaded": True,
        "model": info,
    }


# ─── INFERENCE ───────────────────────────────────────────

@router.post(
    "/infer",
    response_model=InferenceResponse,
    summary="Run inference on loaded model",
)
async def run_inference(request: InferenceRequest):
    """
    Run inference on the currently loaded model.
    Input format depends on model task type.
    """
    try:
        response = engine.run(request)
        return response
    
    except RuntimeError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=str(e),
        )


# ─── CHAT (Convenience for Causal LM) ───────────────────

@router.post(
    "/chat",
    summary="Chat with loaded model (Causal LM shortcut)",
)
async def chat(
    message: str,
    max_tokens: int = 256,
    temperature: float = 0.7,
):
    """
    Simple chat endpoint.
    Only works if loaded model is a Causal LM.
    """
    if not loader.is_loaded:
        raise HTTPException(
            status_code=400,
            detail="No model loaded.",
        )
    
    request = InferenceRequest(
        input_text=message,
        max_new_tokens=max_tokens,
        temperature=temperature,
    )
    
    try:
        response = engine.run(request)
        return {
            "response": response.output.get(
                "generated_text", ""
            ),
            "model_id": response.model_id,
            "task_type": response.task_type,
            "inference_time_ms": response.inference_time_ms,
            "tokens_generated": response.tokens_generated,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ─── REMOVE MODEL ───────────────────────────────────────

@router.delete(
    "/{model_id}",
    summary="Remove a model",
)
async def remove_model(model_id: str):
    """
    Remove a model from disk and registry.
    Cannot remove a currently loaded model.
    """
    try:
        success = downloader.remove_model_files(model_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Model {model_id} not found.",
            )
        
        return {
            "status": "removed",
            "model_id": model_id,
        }
    
    except RuntimeError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


# ─── VERIFY MODEL ───────────────────────────────────────

@router.get(
    "/{model_id}/verify",
    summary="Verify model integrity",
)
async def verify_model(model_id: str):
    """Check if model files are intact and valid."""
    result = downloader.verify_model(model_id)
    return result


# ─── SYSTEM RESOURCES ────────────────────────────────────

@router.get(
    "/system/resources",
    response_model=SystemResources,
    summary="Get system resource info",
)
async def get_system_resources():
    """Get current system RAM, CPU, GPU, disk info."""
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(str(MODELS_DIR))
    
    gpu_available = torch.cuda.is_available()
    gpu_name = None
    gpu_vram = None
    gpu_vram_used = None
    
    if gpu_available:
        gpu_name = torch.cuda.get_device_name(0)
        gpu_vram = round(
            torch.cuda.get_device_properties(0).total_mem 
            / (1024**3), 2
        )
        gpu_vram_used = round(
            torch.cuda.memory_allocated(0) / (1024**3), 2
        )
    
    return SystemResources(
        ram_total_gb=round(mem.total / (1024**3), 2),
        ram_used_gb=round(mem.used / (1024**3), 2),
        ram_available_gb=round(mem.available / (1024**3), 2),
        cpu_count=psutil.cpu_count(logical=True),
        gpu_available=gpu_available,
        gpu_name=gpu_name,
        gpu_vram_gb=gpu_vram,
        gpu_vram_used_gb=gpu_vram_used,
        disk_total_gb=round(disk.total / (1024**3), 2),
        disk_used_gb=round(disk.used / (1024**3), 2),
        disk_free_gb=round(disk.free / (1024**3), 2),
    )


# ─── STORAGE STATS ───────────────────────────────────────

@router.get(
    "/system/storage",
    summary="Model storage statistics",
)
async def get_storage_stats():
    """Get total model storage usage."""
    total_bytes = registry.get_total_storage_used()
    model_count = len(registry.list_models())
    loaded = registry.get_loaded_model()
    
    return {
        "total_models": model_count,
        "total_storage_bytes": total_bytes,
        "total_storage_human": (
            f"{total_bytes / (1024**3):.2f}GB"
        ),
        "currently_loaded": (
            loaded.repo_id if loaded else None
        ),
    }