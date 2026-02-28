from pydantic import BaseModel
from typing import List, Optional

class ChatRequest(BaseModel):
    model: str
    messages: List[dict]
    mode: str = "auto"
    stream: bool = True

class ModelPullRequest(BaseModel):
    name: str

class ModeSwitchRequest(BaseModel):
    mode: str

class BenchmarkRequest(BaseModel):
    model: str
