"""Main FastAPI Application"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.api.router import api_router
from app.websocket.metrics import router as metrics_router
from app.core.hardware_llmfit import detect_hardware as detect_hardware
from app.services.model_manager import ModelManager
from app.plugins.manager import PluginManager


# Rate limiter — per-IP, local-first (falls back to remote_address)
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


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

    # Detect hardware (llmfit-powered, falls back to legacy)
    app.state.hardware_profile = detect_hardware()
    print(f"Hardware: {app.state.hardware_profile}")

    # Initialize model manager
    app.state.model_manager = ModelManager()
    await app.state.model_manager.initialize(app=app)

    # Initialize settings service
    from app.settings.service import SettingsService
    app.state.settings_service = SettingsService()

    # Load startup model if configured
    try:
        general = app.state.settings_service.get_general()
        startup_model = general.get("startup_model")
        mode = general.get("default_mode", "auto")
        if startup_model:
            print(f"Loading startup model: {startup_model} (mode={mode})")
            await app.state.model_manager.load_model(startup_model, mode=mode)
    except Exception as e:
        print(f"Startup model error: {e}")

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

# Rate limiter setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "app://-"],
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