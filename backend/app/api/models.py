"""Models API Endpoints"""
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from typing import Optional

from app.schemas.models import (
    ModelInfo,
    ModelList,
    PullRequest,
    PullStatus,
    LoadRequest
)
from app.core.engine_factory import EngineFactory


router = APIRouter()


@router.get("/", response_model=ModelList)
async def list_models(request: Request):
    """List installed models"""
    models = await request.app.state.model_manager.list_models()
    return ModelList(models=models)





@router.post("/pull")
async def pull_model(
    request: Request, 
    pull_request: PullRequest,
    background_tasks: BackgroundTasks
):
    """Pull/download a model"""
    model_manager = request.app.state.model_manager
    
    # Check if already downloading
    if model_manager.is_downloading(pull_request.model):
        return {"status": "already_downloading", "model": pull_request.model}
    
    # Check if already exists
    if await model_manager.model_exists(pull_request.model):
        return {"status": "exists", "model": pull_request.model}
    
    # Start download in background
    background_tasks.add_task(
        model_manager.download_model,
        pull_request.model,
        pull_request.quant
    )
    
    return {"status": "downloading", "model": pull_request.model}


@router.get("/pull/status/{model_name:path}")
async def pull_status(request: Request, model_name: str):
    """Get download status"""
    status = request.app.state.model_manager.get_download_status(model_name)
    return PullStatus(**status)


@router.post("/load")
async def load_model(request: Request, load_request: LoadRequest):
    """Load model into RAM/VRAM"""
    app = request.app
    manager: ModelManager = app.state.model_manager
    
    try:
        result = await manager.load_model(
            model_id=load_request.model,
            mode=load_request.mode
        )
        return result
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=500, detail=f"Model configuration error: {msg}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to load model: {str(e)}")


@router.post("/unload")
async def unload_model(request: Request):
    """Unload active model"""
    manager: ModelManager = request.app.state.model_manager
    await manager.unload_model()
    return {"status": "unloaded"}


@router.post("/refresh")
async def refresh_models(request: Request):
    """Scan models directory and update registry"""
    manager: ModelManager = request.app.state.model_manager
    await manager.scan_installed()
    models = await manager.list_models()
    return {"status": "refreshed", "count": len(models)}


@router.get("/current")
async def get_current_model(request: Request):
    """Get metadata about currently loaded model for dynamic task UI routing"""
    app = request.app
    if not app.state.active_engine:
        return {"loaded": False}
        
    engine = app.state.active_engine
    
    # Try fetching task_metadata
    task_info = getattr(engine, "task_metadata", {})
    if not task_info:
        # Fallback
        from app.core.task_resolver import TaskResolver
        task_info = TaskResolver.resolve(engine.model_path)
        
    return {
        "loaded": True,
        "model": app.state.active_model,
        "mode": app.state.active_mode,
        "task_type": task_info.get("task_type", "unknown"),
        "input_modality": task_info.get("input_modality", "text"),
        "is_generative": task_info.get("is_generative", False),
        "ram_usage": getattr(engine, "get_memory_usage", lambda: {})()
    }


@router.get("/{model_name:path}", response_model=ModelInfo)
async def get_model(request: Request, model_name: str):
    """Get model details"""
    model = await request.app.state.model_manager.get_model(model_name)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return ModelInfo(**model)


@router.delete("/{model_name:path}")
async def delete_model(request: Request, model_name: str):
    """Delete a model"""
    model_manager = request.app.state.model_manager
    
    # Check if model is currently loaded
    if request.app.state.active_model == model_name:
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete currently loaded model"
        )
    
    success = await model_manager.delete_model(model_name)
    if not success:
        raise HTTPException(status_code=404, detail="Model not found")
    
    return {"status": "deleted", "model": model_name}