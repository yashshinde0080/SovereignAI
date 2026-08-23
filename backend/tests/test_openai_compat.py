"""OpenAI-compatible contract test for POST /v1/chat/completions.

Pins the wire shapes any OpenAI SDK / client depends on:
- non-streaming: ``choices[0].message.{content,reasoning}``, ``finish_reason``, ``usage``
- streaming: SSE ``data:`` frames with ``choices[0].delta.{content,reasoning}``,
  ending in ``data: [DONE]``
- error responses: ``{"error": {"message", "type", "param", "code"}}``

``delta.reasoning`` is a SovereignAI extension (thinking-mode output) — a
standard OpenAI client ignores unknown delta keys, so this stays compatible.
Supported request params: messages, model, max_tokens, temperature, top_p,
stream, use_rag, enable_thinking.

Note: calls the endpoint function directly — fastapi's TestClient is broken in
this venv (starlette 0.35.1 passes ``app=`` to httpx.Client, which httpx 0.28
removed). Pin httpx<0.28 or upgrade starlette to restore TestClient.
"""
import asyncio
import json
import re

import pytest
from starlette.requests import Request

from app.api.chat import chat_completions, stream_response
from app.schemas.chat import ChatRequest


class _FakeEngine:
    """Minimal engine: returns canned output for generate/generate_stream."""

    mode = "fullram"
    loaded = True
    tokenizer = None

    async def generate(self, input_data=None, **kwargs):
        return {
            "output": "Hello from the fake engine.",
            "finish_reason": "stop",
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }

    async def generate_stream(self, input_data=None, **kwargs):
        for token in ["Hello ", "from ", "the ", "fake ", "engine."]:
            yield {"token": token, "finish_reason": None}
        yield {"token": "", "finish_reason": "stop"}

    def get_memory_usage(self):
        return {"ram_used_gb": 1.0}


class _AppState:
    """Fake app.state: only the fields chat_completions touches."""

    def __init__(self):
        self.active_engine = _FakeEngine()
        self.active_model = "fake-model"
        self.settings_service = None
        self.vector_store = None


def _make_request(app_state=None):
    """Build a real starlette Request with a fake app + connected client."""
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/chat/completions",
        "headers": [(b"content-type", b"application/json")],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 1234),
        "scheme": "http",
        "app": type("App", (), {"state": app_state or _AppState()})(),
    }

    # A connected client: every read yields an empty request-body event and
    # never disconnects — the endpoint's is_disconnected() probe must not see
    # a disconnect or every request would be treated as abandoned (499).
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


def _run(coro):
    return asyncio.run(coro)


def test_non_streaming_shape():
    resp = _run(chat_completions(_make_request(), ChatRequest(
        messages=[{"role": "user", "content": "hi"}],
        stream=False,
    )))
    # The endpoint returns a pydantic ChatResponse model (FastAPI serializes it)
    body = resp.model_dump()

    # OpenAI contract fields
    assert body["object"] == "chat.completion"
    assert body["model"] == "fake-model"
    assert isinstance(body["id"], str)
    assert body["id"].startswith("chatcmpl-")
    assert isinstance(body["created"], int)
    assert body["created"] > 0

    choice = body["choices"][0]
    assert choice["index"] == 0
    assert choice["message"]["role"] == "assistant"
    assert choice["message"]["content"] == "Hello from the fake engine."
    assert choice["finish_reason"] == "stop"

    # usage is always present with all three counters
    usage = body["usage"]
    assert set(usage) >= {"prompt_tokens", "completion_tokens", "total_tokens"}


def test_streaming_shape_and_done_sentinel():
    app_state = _AppState()
    # stream_response is an async generator — collect its frames
    collected = "".join(_run(_collect(stream_response(
        app_state.active_engine,
        "hi",
        ChatRequest(messages=[{"role": "user", "content": "hi"}], stream=True),
        rag_metadata=None,
        http_request=_make_request(app_state),
    ))))

    lines = [l for l in collected.splitlines() if l.startswith("data: ")]
    payloads = [l[len("data: "):] for l in lines]

    # Last frame must be the OpenAI done sentinel
    assert payloads[-1] == "[DONE]"

    data_chunks = [json.loads(p) for p in payloads[:-1]]
    for chunk in data_chunks:
        assert chunk["object"] == "chat.completion.chunk"
        assert chunk["choices"][0]["index"] == 0
        assert isinstance(chunk["created"], int)
        assert chunk["created"] > 0
        assert re.match(r"^chatcmpl-", chunk["id"])

    # All streaming chunks share the same id
    ids = {c["id"] for c in data_chunks}
    assert len(ids) == 1, f"expected one stream id, got {ids}"

    deltas = [c["choices"][0]["delta"] for c in data_chunks]
    # Content tokens reassemble the full reply
    assert "".join(d.get("content", "") for d in deltas) == "Hello from the fake engine."
    # finish_reason arrives on the final choice (before [DONE]) — per OpenAI
    # spec it sits on the choice object, not inside delta
    assert data_chunks[-1]["choices"][0].get("finish_reason") == "stop"


async def _collect(agen):
    out = ""
    async for frame in agen:
        out += frame
    return out


def test_reasoning_delta_is_an_extension_not_a_breaking_key():
    """Thinking-mode emits delta.reasoning alongside content — extra keys must
    not break the OpenAI shape (clients ignore unknown delta keys)."""
    from app.api.chat import StreamChunk

    chunk = StreamChunk(
        id="chunk-1",
        choices=[{"index": 0, "delta": {"content": "", "reasoning": "let me think"}}],
    )
    data = json.loads(chunk.model_dump_json())
    delta = data["choices"][0]["delta"]
    assert delta["reasoning"] == "let me think"
    assert set(delta) >= {"content", "reasoning"}


def test_no_model_loaded_is_400():
    app_state = _AppState()
    app_state.active_engine = None
    with pytest.raises(Exception) as excinfo:
        _run(chat_completions(_make_request(app_state), ChatRequest(
            messages=[{"role": "user", "content": "hi"}],
        )))
    # FastAPI raises HTTPException(400) — the client would see a 400 status
    assert getattr(excinfo.value, "status_code", None) == 400
    # Error detail follows OpenAI shape
    detail = excinfo.value.detail
    assert isinstance(detail, dict)
    assert "error" in detail
    assert "message" in detail["error"]
    assert "type" in detail["error"]
