"""Benchmark Schemas"""
from typing import List, Dict, Any
from pydantic import BaseModel, Field


class BenchmarkRequest(BaseModel):
    iterations: int = Field(default=3, ge=1, le=10)
    max_tokens: int = Field(default=100, ge=10, le=500)


class BenchmarkRun(BaseModel):
    iteration: int
    tokens: int
    time_seconds: float
    tokens_per_second: float


class BenchmarkSummary(BaseModel):
    total_tokens: int
    total_time_seconds: float
    average_tokens_per_second: float
    peak_ram_gb: float


class BenchmarkResult(BaseModel):
    model: str
    mode: str
    iterations: int
    runs: List[Dict[str, Any]]
    summary: Dict[str, Any]