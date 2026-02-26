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


@router.get("/{model_name}", response_model=ModelInfo)
async def get_model(request: Request, model_name: str):
    """Get model details"""
    model = await request.app.state.model_manager.get_model(model_name)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return ModelInfo(**model)


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


@router.get("/pull/status/{model_name}")
async def pull_status(request: Request, model_name: str):
    """Get download status"""
    status = request.app.state.model_manager.get_download_status(model_name)
    return PullStatus(**status)


@router.post("/load")
async def load_model(request: Request, load_request: LoadRequest):
    """Load a model into memory"""
    app = request.app
    model_manager = app.state.model_manager
    
    # Get model metadata
    model = await model_manager.get_model(load_request.model)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Determine mode
    mode = load_request.mode or "auto"
    
    # Create engine factory
    factory = EngineFactory(app.state.hardware_profile)
    
    # Unload current model if any
    if app.state.active_engine:
        await app.state.active_engine.unload()
    
    # Create and load engine
    try:
        engine = await factory.create_engine(
            model_path=model["path"],
            mode=mode
        )
        
        app.state.active_engine = engine
        app.state.active_model = load_request.model
        app.state.active_mode = engine.mode
        
        return {
            "status": "loaded",
            "model": load_request.model,
            "mode": engine.mode,
            "ram_usage": engine.get_memory_usage()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unload")
async def unload_model(request: Request):
    """Unload current model"""
    app = request.app
    
    if app.state.active_engine:
        await app.state.active_engine.unload()
        app.state.active_engine = None
        app.state.active_model = None
        app.state.active_mode = None
    
    return {"status": "unloaded"}


@router.delete("/{model_name}")
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