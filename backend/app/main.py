"""Main FastAPI Application"""
import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from enum import IntEnum
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.api.router import api_router
from app.websocket.metrics import router as metrics_router
from app.core.hardware_llmfit import detect_hardware as detect_hardware
from app.services.model_manager import ModelManager
from app.plugins.manager import PluginManager
from app.security.middleware import lan_auth_middleware

logger = logging.getLogger(__name__)


def _configure_logging():
    """One structured format for all app logs; level via SOVEREIGN_LOG_LEVEL."""
    level = os.environ.get("SOVEREIGN_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _patch_gguf_quant_types():
    """Add newer GGML quantization types missing from the installed gguf package.

    The PyPI gguf package (0.19.0 as of 2026-07) doesn't include IQ2_BN (135)
    and possibly other newer quants. Tensor data is read by offset from the file
    so only the enum value and size metadata need to exist for the reader to work.
    """
    try:
        import gguf.constants
        import gguf.gguf_reader
        import gguf.quants
    except ImportError:
        return  # gguf not installed, nothing to patch

    old = gguf.constants.GGMLQuantizationType
    # Check if IQ2_BN already exists (newer gguf version)
    if hasattr(old, 'IQ2_BN'):
        return
    logger.info("gguf %s lacks IQ2_BN — applying compatibility patch", getattr(gguf, "__version__", "?"))

    # Build extended enum with IQ2_BN (BitNet b1.58 2-bit block-normalized)
    members = {m.name: m.value for m in old}
    members['IQ2_BN'] = 135
    new = IntEnum('GGMLQuantizationType', members)
    gguf.constants.GGML_QUANT_SIZES[new.IQ2_BN] = (256, 64)  # block_size, type_size

    # Swap into every gguf submodule that imported the old ref
    for mod_name, mod in list(sys.modules.items()):
        if mod and hasattr(mod, 'GGMLQuantizationType') and mod.GGMLQuantizationType is old:
            mod.GGMLQuantizationType = new
    logger.info("GGUF: patched IQ2_BN quantization type support")


# Rate limiter — per-IP, local-first (falls back to remote_address)
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application Lifespan Events"""
    # Startup
    _configure_logging()
    _patch_gguf_quant_types()
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)

    # Seed cpu_percent so non-blocking calls (interval=None) return real values
    import psutil as _psutil
    _psutil.cpu_percent(interval=None)

    # Initialize database
    from app.database.manager import DatabaseManager
    app.state.db = DatabaseManager()
    app.state.db.initialize()

    # Initialize vector store
    from app.vectorstore.manager import VectorStoreManager
    app.state.vector_store = VectorStoreManager()
    app.state.vector_store.initialize()

    # Detect hardware (llmfit-powered, falls back to legacy)
    app.state.hardware_profile = detect_hardware()
    logger.info("Hardware: %s", app.state.hardware_profile)

    # Initialize settings service first — ModelManager reads it for
    # encrypt_models / allowed_models, and chat.py reads it for every request.
    from app.settings.service import SettingsService
    app.state.settings_service = SettingsService()

    # Initialize model manager
    app.state.model_manager = ModelManager()
    await app.state.model_manager.initialize(app=app)

    # Cloud provider registry (sovereign_settings.db, Fernet-encrypted keys)
    from app.engines.cloud.registry import CloudProviderRegistry
    app.state.cloud_provider_registry = CloudProviderRegistry()

    # Per-request generation concurrency cap (security.max_concurrent_requests).
    # Only the engine call is gated — RAG/tokenizer work stays un-gated so the
    # semaphore slots aren't held while doing disk work.
    try:
        _max_conc = int(app.state.settings_service.get_security().get("max_concurrent_requests", 4) or 4)
    except Exception:
        _max_conc = 4
    app.state.gen_semaphore = asyncio.Semaphore(max(1, _max_conc))

    # Auto-delete expired session snapshots hourly (data_controls.auto_delete_sessions).
    # Files carry their own mtime — no index to maintain.
    async def _sweep_sessions():
        import time as _time
        from app.lib.retention import RETENTION_SECONDS
        while True:
            try:
                dc = app.state.settings_service.get_data_controls()
                if dc.get("auto_delete_sessions"):
                    secs = RETENTION_SECONDS.get(dc.get("data_retention"))
                    sess_dir = settings.workspace_dir / "sessions"
                    now = _time.time()
                    if secs is not None and sess_dir.exists():
                        for f in sess_dir.glob("*.json"):
                            try:
                                if now - f.stat().st_mtime > secs:
                                    f.unlink()
                            except OSError:
                                pass
            except asyncio.CancelledError:
                raise
            except Exception:
                pass  # a sweep hiccup must never take the sweep task down
            await asyncio.sleep(3600)

    sweep_task = asyncio.ensure_future(_sweep_sessions())

    # Load startup model if configured
    try:
        general = app.state.settings_service.get_general()
        startup_model = general.get("startup_model")
        mode = general.get("default_mode", "auto")
        if startup_model:
            logger.info("Loading startup model: %s (mode=%s)", startup_model, mode)
            await app.state.model_manager.load_model(startup_model, mode=mode)
    except Exception as e:
        logger.error("Startup model error: %s", e)

    # Initialize plugin manager (reads settings for disable_external_plugins)
    app.state.plugin_manager = PluginManager(
        settings_service=app.state.settings_service
    )
    await app.state.plugin_manager.load_plugins()

    # Active engine reference
    app.state.active_engine = None
    app.state.active_model = None
    app.state.active_mode = None

    yield

    # Shutdown
    logger.info("Shutting down...")
    sweep_task.cancel()
    if app.state.active_engine:
        await app.state.active_engine.unload()
    if hasattr(app.state, 'model_manager') and hasattr(app.state.model_manager, 'provider'):
        await app.state.model_manager.provider.cleanup()
    if hasattr(app.state, 'db'):
        app.state.db.shutdown()
    if hasattr(app.state, 'vector_store'):
        app.state.vector_store.shutdown()
    if hasattr(app.state, 'cloud_provider_registry'):
        app.state.cloud_provider_registry.close()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Portable Offline AI Compute Platform",
    lifespan=lifespan
)

# OpenAI-compatible error shape: {"error": {"message": ..., "type": ..., "param": ..., "code": ...}}
@app.exception_handler(HTTPException)
async def _openai_error_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"message": str(detail), "type": "invalid_request_error", "param": None, "code": None}}
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

# Auth boundary: token required when bound beyond localhost. Localhost stays
# auth-free so Electron/CLI loopback keeps working (E2, 08-05 F6).
app.middleware("http")(lan_auth_middleware)

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