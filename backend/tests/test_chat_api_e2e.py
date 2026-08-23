"""End-to-end chat API test with a real tiny model (@slow).

Drives POST /v1/chat/completions through the real FullRAMEngine — not a mock —
covering both streaming and non-streaming paths.  This is the integration layer
where engine output meets the OpenAI-compat response shaping, and the only
place to catch bugs like the rotary_emb crash pattern that
test_layerstream_roundtrip.py exposed.

Uses the same tiny synthesized Llama as test_fullram_executor.py.
"""
import asyncio
import json
from pathlib import Path

import pytest
from starlette.requests import Request
from tokenizers import Tokenizer, models, pre_tokenizers
from transformers import AutoModelForCausalLM, LlamaConfig, PreTrainedTokenizerFast

from app.api.chat import chat_completions, stream_response
from app.engines.fullram.executor import FullRAMEngine
from app.schemas.chat import ChatRequest


def _make_tiny_model(source_dir: Path) -> None:
    words = [
        "<unk>", "<s>", "</s>", "<pad>", "the", "quick", "brown", "fox",
        "jumps", "over", "lazy", "dog", "hello", "world", "sovereign",
        "engine", "stream", "test", ".", ",", "!", "a", "and", "of", "to",
    ]
    vocab = {w: i for i, w in enumerate(words)}
    tok = Tokenizer(models.WordLevel(vocab=vocab, unk_token="<unk>"))
    tok.pre_tokenizer = pre_tokenizers.Whitespace()
    fast = PreTrainedTokenizerFast(
        tokenizer_object=tok, unk_token="<unk>", bos_token="<s>",
        eos_token="</s>", pad_token="<pad>",
    )
    fast.save_pretrained(source_dir)

    config = LlamaConfig(
        vocab_size=len(vocab), hidden_size=32, intermediate_size=64,
        num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2,
        max_position_embeddings=128, rope_theta=10000.0,
    )
    AutoModelForCausalLM.from_config(config).save_pretrained(
        source_dir, safe_serialization=True,
    )


class _AppState:
    """Mimics app.state with a real loaded engine."""
    def __init__(self, engine: FullRAMEngine, model_name: str = "tiny-llama"):
        self.active_engine = engine
        self.active_model = model_name
        self.active_mode = "fullram"
        self.settings_service = None
        self.vector_store = None


def _make_request(app_state):
    scope = {
        "type": "http", "method": "POST",
        "path": "/v1/chat/completions",
        "headers": [(b"content-type", b"application/json")],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 1234),
        "scheme": "http",
        "app": type("App", (), {"state": app_state})(),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


def _run(coro):
    return asyncio.run(coro)


async def _collect(agen):
    out = ""
    async for frame in agen:
        out += frame
    return out


@pytest.fixture(scope="module")
def engine_and_state(tmp_path_factory):
    """Module-scoped: load the tiny model once for all tests."""
    source = tmp_path_factory.mktemp("tiny") / "model"
    source.mkdir()
    _make_tiny_model(source)

    engine = FullRAMEngine(str(source), {}, None)

    async def _setup():
        await engine.load()
        return engine

    _run(_setup())
    state = _AppState(engine)
    yield engine, state

    async def _teardown():
        await engine.unload()

    _run(_teardown())


@pytest.mark.slow
def test_chat_non_streaming_e2e(engine_and_state):
    """Real model through non-streaming /v1/chat/completions."""
    engine, state = engine_and_state
    resp = _run(chat_completions(_make_request(state), ChatRequest(
        messages=[{"role": "user", "content": "say hello"}],
        stream=False, max_tokens=8, temperature=0.0,
    )))
    body = resp.model_dump()

    assert body["object"] == "chat.completion"
    assert body["id"].startswith("chatcmpl-")
    assert isinstance(body["created"], int)
    assert body["model"] == "tiny-llama"

    choice = body["choices"][0]
    assert choice["index"] == 0
    assert choice["message"]["role"] == "assistant"
    assert isinstance(choice["message"]["content"], str)  # may be empty for random model
    assert choice["finish_reason"] in ("stop", "length")

    # usage counters exist (may be 0 — FullRAMEngine returns tokens in
    # metadata, not top-level; the chat endpoint falls back to 0).
    usage = body["usage"]
    assert "prompt_tokens" in usage
    assert "completion_tokens" in usage
    assert "total_tokens" in usage


@pytest.mark.slow
def test_chat_streaming_e2e(engine_and_state):
    """Real model through streaming /v1/chat/completions."""
    engine, state = engine_and_state
    collected = _run(_collect(stream_response(
        engine, "say hello",
        ChatRequest(
            messages=[{"role": "user", "content": "say hello"}],
            stream=True, max_tokens=8, temperature=0.0,
        ),
        rag_metadata=None,
        http_request=_make_request(state),
    )))

    lines = [l for l in collected.splitlines() if l.startswith("data: ")]
    payloads = [l[len("data: "):] for l in lines]

    # Ends with [DONE]
    assert payloads[-1] == "[DONE]"

    data_chunks = [json.loads(p) for p in payloads[:-1]]
    for chunk in data_chunks:
        assert chunk["object"] == "chat.completion.chunk"
        assert chunk["id"].startswith("chatcmpl-")
        assert isinstance(chunk["created"], int)

    # All chunks share one id
    ids = {c["id"] for c in data_chunks}
    assert len(ids) == 1

    # Content reassembles to something non-empty
    content = "".join(
        c["choices"][0]["delta"].get("content", "") for c in data_chunks
    )
    assert content.strip()

    # finish_reason on the last chunk
    assert data_chunks[-1]["choices"][0].get("finish_reason") in ("stop", "length")
