import uvicorn
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api import chat, models, system, benchmark, rag
from app.websocket import metrics
from app.core.hardware_detector import HardwareDetector
from app.core.engine_factory import EngineFactory
from app.services.registry import ModelRegistry
from app.database.sqlite import Database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing SovereignAI Edge...")
    
    # Initialize database
    db = Database()
    await db.initialize()
    app.state.db = db
    
    # Detect hardware
    detector = HardwareDetector()
    profile = detector.detect()
    app.state.hardware_profile = profile
    logger.info(f"Hardware detected: {profile}")
    
    # Initialize registry
    registry = ModelRegistry(db)
    await registry.initialize()
    app.state.registry = registry
    
    # Initialize engine factory
    engine_factory = EngineFactory(profile)
    app.state.engine_factory = engine_factory
    app.state.active_engine = None
    app.state.active_model = None
    app.state.active_mode = None
    
    logger.info("SovereignAI Edge ready.")
    yield
    
    # Cleanup
    if app.state.active_engine:
        app.state.active_engine.unload()
    await db.close()
    logger.info("SovereignAI Edge shutdown complete.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="SovereignAI Edge",
        version="1.0.0",
        description="Portable Offline AI Runtime",
        lifespan=lifespan
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(chat.router, prefix="/v1/chat", tags=["Chat"])
    app.include_router(models.router, prefix="/v1/models", tags=["Models"])
    app.include_router(system.router, prefix="/v1/system", tags=["System"])
    app.include_router(benchmark.router, prefix="/v1/benchmark", tags=["Benchmark"])
    app.include_router(rag.router, prefix="/v1/rag", tags=["RAG"])
    app.include_router(metrics.router, tags=["WebSocket"])
    
    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info"
    )