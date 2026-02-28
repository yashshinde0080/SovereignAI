from fastapi import APIRouter
from app.api.routes import router as routes_router
from app.api.rag import router as rag_router
from app.websocket.metrics import router as ws_router

router = APIRouter()
router.include_router(routes_router)
router.include_router(rag_router)
router.include_router(ws_router)
