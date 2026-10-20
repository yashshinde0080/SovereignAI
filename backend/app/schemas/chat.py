"""Chat Schemas"""
import time
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str = Field(..., description="Role: system, user, or assistant")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    messages: List[Message]
    model: Optional[str] = None
    # Saved custom agent to answer as. Resolved and validated server-side —
    # the client never supplies the instructions itself.
    agent_id: Optional[str] = None
    # Mirrors GeneralSettings.max_tokens (le=32768). Capping the request lower
    # than the saved setting turned a valid config into an HTTP 422.
    max_tokens: int = Field(default=512, ge=1, le=32768)
    temperature: float = Field(default=0.7, ge=0, le=2)
    top_p: float = Field(default=0.9, ge=0, le=1)
    stream: bool = False
    use_rag: bool = False


class Choice(BaseModel):
    index: int
    message: Optional[Dict[str, str]] = None
    delta: Optional[Dict[str, str]] = None
    finish_reason: Optional[str] = None


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]


class StreamChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    choices: List[Dict[str, Any]]