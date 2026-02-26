"""Model Schemas"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ModelInfo(BaseModel):
    id: str
    name: str
    size_gb: float
    quant: str
    family: str
    parameters: str
    path: str
    downloaded: bool = True
    modes_supported: List[str] = ["fullram", "layerstream"]
    created_at: Optional[datetime] = None


class ModelList(BaseModel):
    models: List[ModelInfo]


class PullRequest(BaseModel):
    model: str = Field(..., description="Model identifier (e.g., llama3:8b)")
    quant: str = Field(default="Q4_K_M", description="Quantization level")


class PullStatus(BaseModel):
    model: str
    status: str  # downloading, verifying, complete, error
    progress: float = 0.0
    downloaded_gb: float = 0.0
    total_gb: float = 0.0
    error: Optional[str] = None


class LoadRequest(BaseModel):
    model: str = Field(..., description="Model to load")
    mode: Optional[str] = Field(
        default="auto",
        description="Execution mode: fullram, layerstream, auto"
    )