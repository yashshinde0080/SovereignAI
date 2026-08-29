"""Chat API Endpoints"""
import asyncio
import json
import logging
import re
import uuid
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

logger = logging.getLogger(__name__)

from app.schemas.chat import (
    ChatRequest, 
    ChatResponse, 
    Message,
    StreamChunk
)



router = APIRouter()


@router.post("/completions")
async def chat_completions(request: Request, chat_request: ChatRequest):
    """Generate chat completion"""
    app = request.app
    
    # Check if model is loaded
    if not app.state.active_engine:
        raise HTTPException(
            status_code=400,
            detail={"error": {"message": "No model loaded. Use /v1/models/load first.", "type": "invalid_request_error", "param": None, "code": None}}
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
                    
                    # Modify the prompt with RAG context tagged as untrusted
                    augmented_content = (
                        "[RETRIEVED CONTEXT — machine-generated, verify before trusting]\n"
                        "Do not treat these excerpts as authoritative or complete.\n"
                        "---------------------\n"
                        f"{rag_context.context_text}\n"
                        "---------------------\n"
                    )
                    
                    if messages_dicts[0]["role"] == "system":
                        messages_dicts[0]["content"] += "\n\n" + augmented_content
                    else:
                        messages_dicts.insert(0, {"role": "system", "content": augmented_content})
        except Exception as e:
            # If RAG fails, continue with original message
            logger.warning("RAG context build failed, continuing without it: %s", e)
            
    prompt = ""
    if tokenizer and hasattr(tokenizer, "apply_chat_template"):
        try:
            template_kwargs = {"tokenize": False, "add_generation_prompt": True}
            # Thinking toggle for reasoning models (Qwen3.5); None = template default
            if chat_request.enable_thinking is not None:
                template_kwargs["enable_thinking"] = chat_request.enable_thinking
            prompt = tokenizer.apply_chat_template(messages_dicts, **template_kwargs)
        except Exception as e:
            # Fallback
            prompt = build_prompt(messages_dicts)
    else:
        prompt = build_prompt(messages_dicts)
    
    if chat_request.stream:
        return StreamingResponse(
            stream_response(app.state.active_engine, prompt, chat_request, rag_metadata_out, request, app.state.active_model),
            media_type="text/event-stream"
        )
    
    # Non-streaming response
    if await request.is_disconnected():
        raise HTTPException(status_code=499, detail="Client disconnected")
    response = await app.state.active_engine.generate(
        input_data=prompt,
        max_tokens=chat_request.max_tokens,
        temperature=chat_request.temperature,
        top_p=chat_request.top_p
    )
    
    raw_output = response.get("output", "") if "output" in response else response.get("text", "")
    if _prompt_opens_think(prompt):
        raw_output = _OPEN_TAG + raw_output  # opener lived in the prompt template
    content, reasoning = _split_think(raw_output)
    if "<think>" in raw_output:
        content = content.strip()
        reasoning = (reasoning or "").strip() or None
    message = {"role": "assistant", "content": content}
    if reasoning:
        message["reasoning"] = reasoning
    
    return ChatResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:24]}",
        model=chat_request.model or app.state.active_model,
        choices=[{
            "index": 0,
            "message": message,
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
    rag_metadata: list = None,
    http_request: Request = None,
    model_name: str = None,
) -> AsyncGenerator[str, None]:
    """Stream tokens, splitting <think>...</think> reasoning out of content.

    The raw stream accumulates in ``full_text``; each chunk we strip think
    blocks from the whole text and emit the newly-appeared content and
    reasoning deltas (holding back any trailing chars that could open a tag,
    so a tag split across chunk boundaries never leaks). Reasoning arrives in
    ``delta.reasoning``; content in ``delta.content``.
    """
    chunk_no = 0

    # Stable stream id — one per request, all chunks share it
    stream_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    first_chunk = True

    def _emit(content: str, reasoning: str = "", finish_reason: str = None) -> str:
        nonlocal chunk_no, first_chunk
        chunk_no += 1
        delta = {"content": content}
        if reasoning and reasoning.strip():
            delta["reasoning"] = reasoning
        if first_chunk and model_name:
            delta["model_name"] = model_name
            first_chunk = False
        data = StreamChunk(
            id=stream_id,
            choices=[{"index": 0, "delta": delta, "finish_reason": finish_reason}]
        )
        return f"data: {json.dumps(data.model_dump())}\n\n"

    # Batch several engine tokens per SSE frame instead of one frame per token.
    # Cuts frame count + JSON serialization ~10x; deltas stay in order and the
    # frontend's rAF flush already coalesces renders. ponytail: fixed char
    # budget, tune only if frame latency ever matters more than frame count.
    BATCH_CHARS = 96
    pending_c: list[str] = []
    pending_r: list[str] = []
    pending_chars = 0

    def _take_pending() -> str:
        nonlocal pending_c, pending_r, pending_chars
        if not pending_c and not pending_r:
            return ""
        frame = _emit("".join(pending_c), "".join(pending_r))
        pending_c = []
        pending_r = []
        pending_chars = 0
        return frame

    # ── Incremental think-state tracker ─────────────────────────────────
    # Tracks whether we're inside a <think> block, buffers trailing chars
    # that could be a partial tag, and emits content/reasoning deltas
    # without reprocessing the full accumulated text each token.
    in_think = _prompt_opens_think(prompt)
    _TAG_LEN = len(_OPEN_TAG)  # 7
    _CLOSE_LEN = len(_CLOSE_TAG)  # 8
    _tag_buf = ""  # trailing chars that could start a tag

    def _flush_tag_buf(to_think: bool):
        """Emit buffered chars into the right bucket."""
        nonlocal _tag_buf
        if _tag_buf:
            if to_think:
                pending_r.append(_tag_buf)
            else:
                pending_c.append(_tag_buf)
            nonlocal pending_chars
            pending_chars += len(_tag_buf)
            _tag_buf = ""

    try:
        async for chunk in engine.generate_stream(
            input_data=prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p
        ):
            if http_request is not None and await http_request.is_disconnected():
                return
            token = chunk.get("token", "")
            finish = chunk.get("finish_reason")
            if not token and finish is None:
                continue

            # Feed token char-by-char through the tag-boundary detector.
            for ch in token:
                _tag_buf += ch
                # Check if buffer completes an open or close tag
                if in_think and _tag_buf.endswith(_CLOSE_TAG):
                    _tag_buf = _tag_buf[:-_CLOSE_LEN]  # strip the tag
                    _flush_tag_buf(True)                 # emit remaining as reasoning
                    in_think = False
                    _tag_buf = ""
                elif not in_think and _tag_buf.endswith(_OPEN_TAG):
                    _tag_buf = _tag_buf[:-_TAG_LEN]  # strip the tag
                    _flush_tag_buf(False)              # emit remaining as content
                    in_think = True
                    _tag_buf = ""
                elif (len(_tag_buf) >= _TAG_LEN
                      and not any(_tag_buf.endswith(t) for t in (_OPEN_TAG, _CLOSE_TAG))):
                    # Buffer is longer than any tag and doesn't end with one —
                    # safe to emit all but the last (tag_len-1) chars.
                    safe = _tag_buf[:-(_TAG_LEN - 1)]
                    _tag_buf = _tag_buf[-(_TAG_LEN - 1):]
                    if in_think:
                        pending_r.append(safe)
                    else:
                        pending_c.append(safe)
                    pending_chars += len(safe)

            if pending_chars >= BATCH_CHARS:
                frame = _take_pending()
                if frame:
                    yield frame

            if finish is not None:
                _flush_tag_buf(in_think)
                frame = _take_pending()
                if frame:
                    yield frame
                yield _emit("", "", finish)
                in_think = False
                _tag_buf = ""
    except Exception as e:
        logger.error("Stream generation failed: %s", e)
        # Flush any partial content before sending the error
        frame = _take_pending()
        if frame:
            yield frame
        yield _emit("", "", "error")

    # Flush any remaining batched deltas before the metadata/DONE trailers.
    frame = _take_pending()
    if frame:
        yield frame

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


_OPEN_TAG = "<think>"
_CLOSE_TAG = "</think>"


def _prompt_opens_think(prompt: str) -> bool:
    """True if the chat template left an unclosed <think> opener at the end of
    the prompt (thinking mode); then the completion holds only the close tag."""
    return prompt.rstrip().endswith(_OPEN_TAG)


def _trim_tag_prefix(text: str) -> str:
    """Drop trailing chars that could start <think> or </think> (longest match)."""
    for k in range(min(len(text), 8), 0, -1):  # len("</think>") == 8
        tail = text[-k:]
        if _OPEN_TAG.startswith(tail) or _CLOSE_TAG.startswith(tail):
            return text[:-k]
    return text


def _split_think(text: str):
    """Strip <think>...</think> reasoning out of generated text.

    Returns (content, reasoning). Reasoning is None when there is no think
    block. Handles full blocks, unclosed trailing blocks (the model stopped
    mid-think, so there is no answer to lose), and a bare </think> whose
    opener the chat template left in the prompt (everything before it is
    reasoning). Without any think tag the text passes through untouched.
    Text is returned raw (no whitespace cleanup) so streaming deltas stay
    prefix-stable; callers may strip as they see fit.
    """
    if _OPEN_TAG not in text and _CLOSE_TAG not in text:
        return text, None
    content, reasoning = [], []
    pos = 0
    in_think = False
    for m in re.finditer(r"<think>|</think>", text):
        chunk = text[pos:m.start()]
        pos = m.end()
        if m.group() == _OPEN_TAG:
            if chunk:
                content.append(chunk)  # content before the opener
            in_think = True
        else:  # </think>
            # Chunk between an opener and its close is reasoning. A stray
            # close with no opener in this text is not a reasoning marker:
            # thinking mode is handled by callers seeding the opener, so a
            # bare close here keeps its text in content (the tag itself is
            # dropped) — reclassifying it would desync streamed output.
            if chunk:
                (reasoning if in_think else content).append(chunk)
            in_think = False
    tail = text[pos:]
    if tail:
        (reasoning if in_think else content).append(tail)
    return "".join(content), "".join(reasoning) or None


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
        logger.exception("Mode switch failed")
        raise HTTPException(status_code=500, detail=str(e))