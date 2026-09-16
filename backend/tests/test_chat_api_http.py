"""HTTP-layer chat e2e with a fake engine wired into app.state (fast, no model).

Complements test_chat_api_e2e.py (@slow, real tiny model, endpoint functions
called directly). This file drives POST /v1/chat/completions through the real
HTTP stack — routing, body parsing, StreamingResponse framing, error paths —
with a fake engine, so it runs in the fast loop.

NOTE: TestClient is used WITHOUT a context manager on purpose (no lifespan —
see test_app_smoke.py). app.state attributes are wired explicitly instead.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app


class _FakeEngine:
    """Records generate() calls; emits a fixed token sequence when streaming."""

    mode = None  # not "cloud" -> chat.py passes a rendered prompt string

    def __init__(self, stream_tokens=("Hello", " world", "!")):
        self.stream_tokens = stream_tokens
        self.calls = []

    async def generate(self, input_data, **kwargs):
        self.calls.append((input_data, kwargs))
        return {
            "output": "Hello world!",
            "finish_reason": "stop",
            "prompt_tokens": 3,
            "completion_tokens": 3,
            "total_tokens": 6,
        }

    async def generate_stream(self, input_data, **kwargs):
        self.calls.append((input_data, kwargs))
        for tok in self.stream_tokens:
            yield {"token": tok, "finish_reason": None}
        yield {"token": "", "finish_reason": "stop"}


@pytest.fixture()
def client():
    # No `with` — no lifespan, no workspace side effects.
    return TestClient(app)


@pytest.fixture()
def wire_engine():
    """Wire a fake engine into the real app.state, clean up after."""

    def _wire(engine, model_name="fake-model"):
        app.state.active_engine = engine
        app.state.active_model = model_name
        app.state.active_mode = "fullram"
        app.state.settings_service = None
        app.state.vector_store = None
        return engine

    yield _wire
    app.state.active_engine = None
    app.state.active_model = None


def test_chat_without_engine_is_400(client):
    app.state.active_engine = None
    r = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert r.status_code == 400
    assert "No model loaded" in r.json()["error"]["message"]


def test_chat_non_streaming_openai_shape(client, wire_engine):
    engine = wire_engine(_FakeEngine())
    r = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "say hi"}],
        "stream": False,
    })
    assert r.status_code == 200
    body = r.json()

    assert body["object"] == "chat.completion"
    assert body["id"].startswith("chatcmpl-")
    assert body["model"] == "fake-model"
    choice = body["choices"][0]
    assert choice["message"] == {"role": "assistant", "content": "Hello world!"}
    assert choice["finish_reason"] == "stop"
    assert body["usage"] == {"prompt_tokens": 3, "completion_tokens": 3, "total_tokens": 6}

    # Local engines receive the rendered prompt string, not raw messages
    input_data, kwargs = engine.calls[0]
    assert "User: say hi" in input_data
    assert kwargs["max_tokens"] == 512  # ChatRequest default flowed through


def test_chat_streaming_sse_frames(client, wire_engine):
    engine = wire_engine(_FakeEngine())
    r = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "say hi"}],
        "stream": True,
    })
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")

    payloads = [
        line[len("data: "):] for line in r.text.splitlines()
        if line.startswith("data: ")
    ]
    assert payloads[-1] == "[DONE]"

    chunks = [json.loads(p) for p in payloads[:-1]]
    # One stable stream id across all chunks
    assert len({c["id"] for c in chunks}) == 1
    content = "".join(
        c["choices"][0]["delta"].get("content", "") for c in chunks
    )
    assert content == "Hello world!"
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"


def test_chat_injects_system_prompt_from_settings(client, wire_engine):
    engine = wire_engine(_FakeEngine())
    app.state.settings_service = type(
        "S", (), {"get_system_prompt": staticmethod(lambda: "You are terse.")}
    )()
    client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "hi"}],
    })
    input_data, _ = engine.calls[0]
    assert "You are terse." in input_data
    assert "User: hi" in input_data


def test_chat_stream_engine_error_still_emits_done(client, wire_engine):
    class _Boom(_FakeEngine):
        async def generate_stream(self, input_data, **kwargs):
            raise RuntimeError("engine exploded")
            yield  # pragma: no cover — makes this an async generator

    wire_engine(_Boom())
    r = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "hi"}],
        "stream": True,
    })
    assert r.status_code == 200  # stream started before the engine blew up
    payloads = [
        line[len("data: "):] for line in r.text.splitlines()
        if line.startswith("data: ")
    ]
    assert payloads[-1] == "[DONE]"
    chunks = [json.loads(p) for p in payloads[:-1]]
    assert chunks[-1]["choices"][0]["finish_reason"] == "error"
