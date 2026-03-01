"""Main FastAPI Application"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.api.router import api_router
from app.websocket.metrics import router as metrics_router
from app.core.hardware_detector import HardwareDetector
from app.services.model_manager import ModelManager
from app.plugins.manager import PluginManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application Lifespan Events"""
    # Startup
    print(f"Starting {settings.app_name} v{settings.app_version}")
    
    # Initialize database
    from app.database.manager import DatabaseManager
    from pathlib import Path
    config_path = str(Path(__file__).parent / "config" / "storage.toml")
    app.state.db = DatabaseManager(config_path=config_path)
    app.state.db.initialize()
    
    # Initialize vector store
    from app.vectorstore.manager import VectorStoreManager
    from pathlib import Path
    config_path = str(Path(__file__).parent / "config" / "storage.toml")
    app.state.vector_store = VectorStoreManager(config_path=config_path)
    app.state.vector_store.initialize()
    
    
    # Detect hardware
    hardware = HardwareDetector()
    app.state.hardware_profile = hardware.detect()
    print(f"Hardware: {app.state.hardware_profile}")
    
    # Initialize model manager
    app.state.model_manager = ModelManager()
    await app.state.model_manager.initialize()
    
    # Initialize plugin manager
    app.state.plugin_manager = PluginManager()
    await app.state.plugin_manager.load_plugins()
    
    # Active engine reference
    app.state.active_engine = None
    app.state.active_model = None
    app.state.active_mode = None
    
    yield
    
    # Shutdown
    print("Shutting down...")
    if app.state.active_engine:
        await app.state.active_engine.unload()
    if hasattr(app.state, 'db'):
        app.state.db.shutdown()
    if hasattr(app.state, 'vector_store'):
        app.state.vector_store.shutdown()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Portable Offline AI Compute Platform",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(api_router, prefix="/v1")
app.include_router(metrics_router)


@app.get("/")
async def root():
    """Health Check"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running"
    }


@app.get("/health")
async def health():
    """Detailed Health Check"""
    return {
        "status": "healthy",
        "model_loaded": app.state.active_model is not None,
        "current_model": app.state.active_model,
        "current_mode": app.state.active_mode
    }