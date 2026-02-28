"""Chat API Endpoints"""
import asyncio
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
import json

from app.schemas.chat import (
    ChatRequest, 
    ChatResponse, 
    Message,
    StreamChunk
)
from app.core.engine_factory import EngineFactory


router = APIRouter()


@router.post("/completions")
async def chat_completions(request: Request, chat_request: ChatRequest):
    """Generate chat completion"""
    app = request.app
    
    # Check if model is loaded
    if not app.state.active_engine:
        raise HTTPException(
            status_code=400,
            detail="No model loaded. Use /v1/models/load first."
        )
    
    # Build prompt from messages using tokenizer's template if possible
    # Fallback to string concatenation if not available
    tokenizer = getattr(app.state.active_engine, "tokenizer", None)
    
    messages_dicts = [{"role": msg.role, "content": msg.content} for msg in chat_request.messages]
    
    prompt = ""
    if tokenizer and hasattr(tokenizer, "apply_chat_template"):
        try:
            prompt = tokenizer.apply_chat_template(
                messages_dicts, 
                tokenize=False, 
                add_generation_prompt=True
            )
        except Exception as e:
            # Fallback
            prompt = build_prompt(chat_request.messages)
    else:
        prompt = build_prompt(chat_request.messages)
    
    if chat_request.stream:
        return StreamingResponse(
            stream_response(app.state.active_engine, prompt, chat_request),
            media_type="text/event-stream"
        )
    
    # Non-streaming response
    response = await app.state.active_engine.generate(
        prompt=prompt,
        max_tokens=chat_request.max_tokens,
        temperature=chat_request.temperature,
        top_p=chat_request.top_p
    )
    
    return ChatResponse(
        id=f"chat-{id(response)}",
        model=app.state.active_model,
        choices=[{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": response["text"]
            },
            "finish_reason": response.get("finish_reason", "stop")
        }],
        usage={
            "prompt_tokens": response.get("prompt_tokens", 0),
            "completion_tokens": response.get("completion_tokens", 0),
            "total_tokens": response.get("total_tokens", 0)
        }
    )


async def stream_response(
    engine, 
    prompt: str, 
    request: ChatRequest
) -> AsyncGenerator[str, None]:
    """Stream tokens"""
    async for chunk in engine.generate_stream(
        prompt=prompt,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        top_p=request.top_p
    ):
        data = StreamChunk(
            id=f"chunk-{id(chunk)}",
            choices=[{
                "index": 0,
                "delta": {"content": chunk["token"]},
                "finish_reason": chunk.get("finish_reason")
            }]
        )
        yield f"data: {json.dumps(data.model_dump())}\n\n"
    
    yield "data: [DONE]\n\n"


def build_prompt(messages: list[Message]) -> str:
    """Build prompt from messages (fallback)"""
    prompt_parts = []
    
    for msg in messages:
        if msg.role == "system":
            prompt_parts.append(f"System: {msg.content}")
        elif msg.role == "user":
            prompt_parts.append(f"User: {msg.content}")
        elif msg.role == "assistant":
            prompt_parts.append(f"Assistant: {msg.content}")
    
    prompt_parts.append("Assistant: ")
    return "\n".join(prompt_parts)


@router.post("/mode/switch")
async def switch_mode(request: Request, mode: str):
    """Switch execution mode"""
    app = request.app
    
    if mode not in ["fullram", "layerstream", "auto"]:
        raise HTTPException(status_code=400, detail="Invalid mode")
    
    if not app.state.active_model:
        raise HTTPException(status_code=400, detail="No model loaded")
    
    # Get model metadata
    model_meta = await app.state.model_manager.get_model(app.state.active_model)
    
    # Create new engine
    factory = EngineFactory(app.state.hardware_profile)
    
    # Unload current
    if app.state.active_engine:
        await app.state.active_engine.unload()
    
    # Load with new mode
    app.state.active_engine = await factory.create_engine(
        model_path=model_meta["path"],
        mode=mode
    )
    app.state.active_mode = mode
    
    return {
        "status": "success",
        "model": app.state.active_model,
        "mode": app.state.active_mode
    }