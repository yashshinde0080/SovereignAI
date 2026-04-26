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
    
    # Apply Personalization & Agent Settings
    settings_service = getattr(app.state, "settings_service", None)
    if settings_service:
        system_prompt = settings_service.get_system_prompt()
        
        if system_prompt:
            # If there's already a system message, prepend our settings-based prompt
            if messages_dicts and messages_dicts[0]["role"] == "system":
                if system_prompt not in messages_dicts[0]["content"]:
                    messages_dicts[0]["content"] = system_prompt + "\n\n" + messages_dicts[0]["content"]
            else:
                # Otherwise, insert it as the first message
                messages_dicts.insert(0, {"role": "system", "content": system_prompt})
    
    # RAG Integration
    rag_metadata_out = None
    if chat_request.use_rag and getattr(app.state, "vector_store", None):
        try:
            vector_store = app.state.vector_store
            # Find the last user message
            last_user_idx = -1
            for i in range(len(messages_dicts) - 1, -1, -1):
                if messages_dicts[i]["role"] == "user":
                    last_user_idx = i
                    break
            
            if last_user_idx != -1:
                query_text = messages_dicts[last_user_idx]["content"]
                
                # Query Condensation: combine last 3 messages for context if available
                if last_user_idx >= 2:
                    history_context = "\n".join([f"{m['role']}: {m['content']}" for m in messages_dicts[-3:]])
                    condensed_query = f"{history_context}\nuser: {query_text}"
                else:
                    condensed_query = query_text

                # Get RAG context
                rag_context = vector_store.build_context(
                    query_text=condensed_query,
                    top_k=5,
                    max_tokens=2048,
                    score_threshold=0.0  # Removed hardcoded 0.3 threshold
                )
                
                if rag_context and rag_context.results:
                    # Extract citations
                    citations = []
                    for r in rag_context.results:
                        citations.append({
                            "document_id": r.document_id,
                            "filename": r.metadata.get("filename", "Unknown"),
                            "score": r.score
                        })
                    rag_metadata_out = citations
                    
                    # Modify the prompt with RAG context isolated as System directive
                    augmented_content = (
                        "Use the following retrieved context to answer the user's question.\n"
                        "If the answer is not contained in the context, use your existing knowledge.\n"
                        "Context:\n---------------------\n"
                        f"{rag_context.context_text}\n"
                        "---------------------\n"
                    )
                    
                    if messages_dicts[0]["role"] == "system":
                        messages_dicts[0]["content"] += "\n\n" + augmented_content
                    else:
                        messages_dicts.insert(0, {"role": "system", "content": augmented_content})
        except Exception as e:
            # If RAG fails, continue with original message
            print(f"RAG error: {e}")
            
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
            prompt = build_prompt(messages_dicts)
    else:
        prompt = build_prompt(messages_dicts)
    
    if chat_request.stream:
        return StreamingResponse(
            stream_response(app.state.active_engine, prompt, chat_request, rag_metadata_out),
            media_type="text/event-stream"
        )
    
    # Non-streaming response
    response = await app.state.active_engine.generate(
        input_data=prompt,
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
                "content": response.get("output", "") if "output" in response else response.get("text", "")
            },
            "finish_reason": response.get("finish_reason", "stop")
        }],
        usage={
            "prompt_tokens": response.get("prompt_tokens", 0),
            "completion_tokens": response.get("completion_tokens", 0),
            "total_tokens": response.get("total_tokens", 0)
        }
    )

@router.post("/execute")
async def execute_task(request: Request):
    """Universal Execution Endpoint returning structured JSON as required"""
    app = request.app
    if not app.state.active_engine:
        raise HTTPException(status_code=400, detail="No model loaded.")
        
    engine = app.state.active_engine
    body = await request.json()
    
    # Delegate to Engine's unified generate implementation directly
    try:
        # Check task type compatibility to fail early?
        # That's handled inside the engine.
        result = await engine.generate(input_data=body, **body.get("generation_kwargs", {}))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



async def stream_response(
    engine, 
    prompt: str, 
    request: ChatRequest,
    rag_metadata: list = None
) -> AsyncGenerator[str, None]:
    """Stream tokens"""
    async for chunk in engine.generate_stream(
        input_data=prompt,
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
        
    if rag_metadata:
        meta_chunk = StreamChunk(
            id=f"chunk-meta",
            choices=[{
                "index": 0,
                "delta": {"rag_metadata": rag_metadata},
                "finish_reason": None
            }]
        )
        yield f"data: {json.dumps(meta_chunk.model_dump())}\n\n"
    
    yield "data: [DONE]\n\n"


def build_prompt(messages: list) -> str:
    """Build prompt from messages (fallback)"""
    prompt_parts = []
    
    for msg in messages:
        role = msg["role"] if isinstance(msg, dict) else msg.role
        content = msg["content"] if isinstance(msg, dict) else msg.content
        
        if role == "system":
            prompt_parts.append(f"System: {content}")
        elif role == "user":
            prompt_parts.append(f"User: {content}")
        elif role == "assistant":
            prompt_parts.append(f"Assistant: {content}")
    
    prompt_parts.append("Assistant: ")
    return "\n".join(prompt_parts)


@router.post("/mode/switch")
async def switch_mode(request: Request, mode: str):
    """Switch execution mode for current model"""
    app = request.app
    if not app.state.active_model:
        raise HTTPException(status_code=400, detail="No model loaded")
    
    try:
        # Use ModelManager's load_model to handle engine creation and path resolution
        result = await app.state.model_manager.load_model(
            model_id=app.state.active_model,
            mode=mode
        )
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))