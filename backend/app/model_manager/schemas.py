"""
Pydantic schemas for model manager API.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from .config import ModelStatus, ModelTaskType


class ModelPullRequest(BaseModel):
    """Request to download a model from HuggingFace."""
    repo_id: str = Field(
        ..., 
        description="HuggingFace repo ID, e.g. 'meta-llama/Llama-3-8B'",
        examples=["microsoft/phi-2", "google/gemma-2b"]
    )
    revision: Optional[str] = Field(
        None, 
        description="Git revision (branch/tag/commit)"
    )
    task_override: Optional[ModelTaskType] = Field(
        None,
        description="Override auto-detected task type"
    )
    trust_remote_code: bool = Field(
        False,
        description="Allow running remote code from the model repo"
    )


class ModelLoadRequest(BaseModel):
    """Request to load a model into memory."""
    model_id: str = Field(
        ..., 
        description="Local model ID from registry"
    )
    device: Optional[str] = Field(
        None,
        description="Device override: cpu, cuda, cuda:0, mps, auto"
    )
    dtype: Optional[str] = Field(
        None,
        description="Data type: float32, float16, bfloat16, int8, int4"
    )


class ModelInfo(BaseModel):
    """Model information from registry."""
    id: str
    repo_id: str
    local_name: str
    task_type: str
    status: str
    size_bytes: int
    size_human: str
    architectures: Optional[str]
    revision: Optional[str]
    downloaded_at: str
    last_loaded_at: Optional[str]
    load_count: int
    local_path: str
    
    class Config:
        from_attributes = True


class LoadedModelInfo(BaseModel):
    """Information about the currently loaded model."""
    model_id: str
    repo_id: str
    task_type: str
    device: str
    dtype: str
    loaded_at: str
    memory_used_mb: float


class InferenceRequest(BaseModel):
    """Generic inference request."""
    input_text: Optional[str] = None
    input_texts: Optional[list[str]] = None
    image_url: Optional[str] = None
    image_path: Optional[str] = None
    audio_path: Optional[str] = None
    context: Optional[str] = None
    question: Optional[str] = None
    
    # Generation params
    max_new_tokens: int = Field(256, ge=1, le=4096)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    top_p: float = Field(0.9, ge=0.0, le=1.0)
    top_k: int = Field(50, ge=0)
    do_sample: bool = True
    repetition_penalty: float = Field(1.1, ge=1.0, le=2.0)
    
    # Classification params
    candidate_labels: Optional[list[str]] = None


class InferenceResponse(BaseModel):
    """Generic inference response."""
    output: dict
    model_id: str
    task_type: str
    inference_time_ms: float
    tokens_generated: Optional[int] = None


class DownloadProgress(BaseModel):
    """Download progress update."""
    repo_id: str
    status: str
    progress_percent: float
    downloaded_bytes: int
    total_bytes: int
    speed_mbps: float
    eta_seconds: float


class SystemResources(BaseModel):
    """Current system resource usage."""
    ram_total_gb: float
    ram_used_gb: float
    ram_available_gb: float
    cpu_count: int
    gpu_available: bool
    gpu_name: Optional[str]
    gpu_vram_gb: Optional[float]
    gpu_vram_used_gb: Optional[float]
    disk_total_gb: float
    disk_used_gb: float
    disk_free_gb: float


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: str
    suggestion: Optional[str] = None