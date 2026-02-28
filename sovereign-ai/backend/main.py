import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.api import router as main_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sovereign-backend")

app = FastAPI(title="SovereignAI Edge", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(main_router)

@app.get("/")
def read_root():
    return {"status": "ok", "app": "SovereignAI Edge Backend API"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
