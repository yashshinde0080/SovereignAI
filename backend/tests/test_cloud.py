"""Cloud-mode tests: provider registry (encrypted keys) + API translation.

No network: translation functions are pure, and the engine is exercised
against a fake aiohttp session returning canned provider responses.
"""

import asyncio
import json
import sqlite3

import pytest
from fastapi import HTTPException

from app.engines.cloud import providers
from app.engines.cloud.registry import CloudProviderRegistry
from app.engines.cloud.engine import CloudAPIEngine
from app.security.encryption import ModelEncryption


# ── registry ──

def test_undecryptable_key_degrades_gracefully(tmp_path):
    """Regression: a key encrypted under an older/unavailable encryption key
    used to raise InvalidToken and 500 every /v1/cloud/* endpoint. It must
    degrade to a masked/empty key instead (user re-saves the key)."""
    db = tmp_path / "settings.db"
    reg = CloudProviderRegistry(str(db))
    p = reg.add_provider(name="Old", provider_type="openai", api_key="sk-old-key-1234567890")

    # Simulate the key becoming undecryptable (machine-key scheme change).
    conn = sqlite3.connect(str(db))
    conn.execute("UPDATE cloud_providers SET api_key_encrypted = 'gAAAAABbogusbogusbogus' WHERE id = ?", (p["id"],))
    conn.commit()
    conn.close()

    # list_providers: no raise, masked value for the dead key
    listed = reg.list_providers()
    assert listed[0]["api_key_masked"] == "****"
    # server-side paths: no raise, unusable key surfaced as empty
    assert reg.get_provider(p["id"])["api_key"] == ""
    assert reg.get_enabled_providers()[0]["api_key"] == ""


def test_persisted_key_is_stable_across_instances():
    """Regression: the old machine key (hostname + MAC) changed whenever the
    active network adapter changed, orphaning every stored API key. The key
    now persists in workspace/database/.secret_key, so instances share it."""
    e1, e2 = ModelEncryption(), ModelEncryption()
    token = e1.fernet.encrypt(b"sovereign")
    assert e2.fernet.decrypt(token) == b"sovereign"


def test_registry_crud_and_encryption(tmp_path):
    db = tmp_path / "settings.db"
    reg = CloudProviderRegistry(str(db))
    p = reg.add_provider(name="OpenAI", provider_type="openai", api_key="sk-secret-key-1234567890")
    assert p["id"].startswith("prov_")

    # key is never stored in plaintext
    assert b"sk-secret-key-1234567890" not in db.read_bytes()

    # list returns masked key only, never the raw value
    listed = reg.list_providers()
    assert len(listed) == 1
    assert listed[0]["api_key_masked"] == "sk-s…7890"
    assert "api_key" not in listed[0]

    # get_provider decrypts for server-side use
    got = reg.get_provider(p["id"])
    assert got["api_key"] == "sk-secret-key-1234567890"

    # update (partial patch + key rotation)
    upd = reg.update_provider(p["id"], {"is_enabled": False, "api_key": "sk-new-key-9876543210"})
    assert upd["is_enabled"] is False
    assert reg.get_provider(p["id"])["api_key"] == "sk-new-key-9876543210"

    # enabled-only view respects the flag
    assert reg.get_enabled_providers() == []
    reg.update_provider(p["id"], {"is_enabled": True})
    assert len(reg.get_enabled_providers()) == 1

    # delete
    assert reg.delete_provider(p["id"]) is True
    assert reg.get_provider(p["id"]) is None
    assert reg.delete_provider(p["id"]) is False
    reg.close()


def test_registry_update_unknown_provider(tmp_path):
    reg = CloudProviderRegistry(str(tmp_path / "settings.db"))
    assert reg.update_provider("prov_missing", {"name": "x"}) is None
    reg.close()


# ── request translation ──

def test_openai_request_translation():
    url, headers, payload = providers.build_chat_request(
        "openai",
        messages=[{"role": "user", "content": "hi"}],
        model="gpt-4o",
        max_tokens=100, temperature=0.5, top_p=0.9, stream=False,
        base="https://api.openai.com/v1", api_key="sk-test",
    )
    assert url == "https://api.openai.com/v1/chat/completions"
    assert headers["Authorization"] == "Bearer sk-test"
    assert payload["model"] == "gpt-4o"
    assert payload["messages"] == [{"role": "user", "content": "hi"}]
    assert payload["stream"] is False
    assert payload["max_tokens"] == 100


def test_anthropic_request_translation():
    url, headers, payload = providers.build_chat_request(
        "anthropic",
        messages=[
            {"role": "system", "content": "Be brief."},
            {"role": "user", "content": "hi"},
            {"role": "user", "content": "again"},
        ],
        model="claude-3-5-sonnet",
        max_tokens=200, temperature=0.7, top_p=1.0, stream=False,
        base="https://api.anthropic.com", api_key="sk-ant",
    )
    assert url == "https://api.anthropic.com/v1/messages"
    assert headers["x-api-key"] == "sk-ant"
    assert payload["system"] == "Be brief."
    # consecutive same-role turns merged
    assert payload["messages"] == [{"role": "user", "content": "hi\n\nagain"}]
    assert payload["max_tokens"] == 200


def test_google_request_translation():
    url, headers, payload = providers.build_chat_request(
        "google",
        messages=[
            {"role": "system", "content": "Be brief."},
            {"role": "user", "content": "hi"},
        ],
        model="gemini-2.5-flash",
        max_tokens=100, temperature=0.7, top_p=0.9, stream=False,
        base="https://generativelanguage.googleapis.com", api_key="AIza",
    )
    assert url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    assert headers["x-goog-api-key"] == "AIza"
    assert payload["contents"] == [{"role": "user", "parts": [{"text": "hi"}]}]
    assert payload["systemInstruction"] == {"parts": [{"text": "Be brief."}]}


def test_custom_provider_requires_base_url():
    with pytest.raises(ValueError):
        providers.base_url("custom", "")


# ── response parsing ──

def test_parse_chat_responses():
    r = providers.parse_chat_response("openai", {
        "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
    })
    assert r["output"] == "hello"
    assert r["total_tokens"] == 5

    r = providers.parse_chat_response("anthropic", {
        "content": [{"type": "text", "text": "hi there"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 4, "output_tokens": 6},
    })
    assert r["output"] == "hi there"
    assert r["completion_tokens"] == 6
    assert r["finish_reason"] == "stop"

    r = providers.parse_chat_response("anthropic", {
        "content": [{"type": "text", "text": "x"}], "stop_reason": "max_tokens",
    })
    assert r["finish_reason"] == "length"

    r = providers.parse_chat_response("google", {
        "candidates": [{"content": {"parts": [{"text": "hey"}]}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 2},
    })
    assert r["output"] == "hey"
    assert r["prompt_tokens"] == 1


def test_parse_stream_events():
    assert providers.parse_stream_event("openai", {
        "choices": [{"delta": {"content": "tok"}, "finish_reason": None}],
    }) == ("tok", None)
    assert providers.parse_stream_event("openai", {
        "choices": [{"delta": {}, "finish_reason": "stop"}],
    }) == ("", "stop")

    assert providers.parse_stream_event("anthropic", {
        "type": "content_block_delta", "delta": {"type": "text_delta", "text": "tok"},
    }) == ("tok", None)
    assert providers.parse_stream_event("anthropic", {
        "type": "message_delta", "delta": {"stop_reason": "end_turn"},
    }) == ("", "stop")

    assert providers.parse_stream_event("google", {
        "candidates": [{"content": {"parts": [{"text": "tok"}]}}],
    }) == ("tok", None)
    assert providers.parse_stream_event("google", {
        "candidates": [{"content": {"parts": [{"text": ""}]}, "finishReason": "STOP"}],
    }) == ("", "stop")


# ── engine against a fake session ──

class _FakeResponse:
    def __init__(self, status=200, json_data=None, sse_lines=None):
        self.status = status
        self._json = json_data
        self.content = _FakeContent(sse_lines or [])

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self):
        return self._json

    async def text(self):
        return json.dumps(self._json or {})


class _FakeContent:
    def __init__(self, lines):
        self._lines = lines

    def __aiter__(self):
        self._it = iter(self._lines)
        return self

    async def __anext__(self):
        try:
            return next(self._it).encode()
        except StopIteration:
            raise StopAsyncIteration


class _FakeSession:
    """Mimics aiohttp: post() returns a context manager (not a coroutine)."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.posts = []

    def post(self, url, headers=None, json=None, **kwargs):
        self.posts.append({"url": url, "headers": headers, "json": json})
        return self._responses.pop(0)


def _engine(provider=None):
    return CloudAPIEngine(
        model_path="openai/gpt-4o",
        hardware={},
        memory_manager=None,
        provider=provider or {
            "name": "OpenAI",
            "provider_type": "openai",
            "api_key": "sk-test",
            "base_url": None,
        },
        model_id="gpt-4o",
    )


def test_engine_generate_non_stream():
    eng = _engine()
    eng.loaded = True
    eng._http = _FakeSession([_FakeResponse(200, json_data={
        "choices": [{"message": {"content": "Hello!"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
    })])
    result = asyncio.run(eng.generate([{"role": "user", "content": "hi"}], max_tokens=100))
    assert result["output"] == "Hello!"
    assert result["finish_reason"] == "stop"
    assert result["total_tokens"] == 6
    assert eng._http.posts[0]["json"]["model"] == "gpt-4o"
    assert eng._http.posts[0]["json"]["max_tokens"] == 100
    assert eng._http.posts[0]["json"]["stream"] is False


def test_engine_generate_stream():
    eng = _engine()
    eng.loaded = True
    lines = [
        'data: {"choices": [{"delta": {"content": "Hel"}, "finish_reason": null}]}',
        'data: {"choices": [{"delta": {"content": "lo!"}, "finish_reason": null}]}',
        'data: {"choices": [{"delta": {}, "finish_reason": "stop"}]}',
        "data: [DONE]",
    ]
    eng._http = _FakeSession([_FakeResponse(200, sse_lines=lines)])

    async def _collect():
        chunks = []
        async for chunk in eng.generate_stream([{"role": "user", "content": "hi"}]):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_collect())
    assert "".join(c["token"] for c in chunks) == "Hello!"
    finishes = [c["finish_reason"] for c in chunks if c["finish_reason"]]
    assert finishes == ["stop"]  # exactly one finish, no double stop
    assert eng._http.posts[0]["json"]["stream"] is True


def test_engine_error_mapping():
    eng = _engine()
    eng.loaded = True
    eng._http = _FakeSession([_FakeResponse(
        401, json_data={"error": {"message": "Invalid API key"}},
    )])
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(eng.generate("hi"))
    assert excinfo.value.status_code == 401
    assert "API key rejected" in str(excinfo.value.detail)


def test_engine_load_requires_key():
    eng = CloudAPIEngine(
        "openai/gpt-4o", {}, None,
        provider={"name": "OpenAI", "provider_type": "openai", "api_key": ""},
        model_id="gpt-4o",
    )
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(eng.load())
    assert excinfo.value.status_code == 400


def test_engine_memory_usage_is_zero():
    assert _engine().get_memory_usage()["ram_used_gb"] == 0


# ── factory cloud branch ──

def test_factory_cloud_branch(tmp_path, monkeypatch):
    from app.core.engine_factory import EngineFactory
    from app.engines.cloud import registry as cloud_registry_module

    reg = CloudProviderRegistry(str(tmp_path / "settings.db"))
    p = reg.add_provider(name="OpenAI", provider_type="openai", api_key="sk-test-1234567890")
    reg.close()

    # Point the factory's default registry at the tmp DB (it constructs one
    # from the real workspace path otherwise).
    monkeypatch.setattr(cloud_registry_module, "CloudProviderRegistry", lambda: reg)

    factory = EngineFactory({"ram_total_gb": 16})
    engine = asyncio.run(factory.create_engine(f"{p['id']}/gpt-4o", mode="cloud"))
    assert isinstance(engine, CloudAPIEngine)
    assert engine.mode == "cloud"
    assert engine.model_id == "gpt-4o"


def test_factory_cloud_unknown_provider(tmp_path):
    from app.core.engine_factory import EngineFactory

    factory = EngineFactory({"ram_total_gb": 16})
    with pytest.raises(ValueError) as excinfo:
        asyncio.run(factory.create_engine("prov_missing/gpt-4o", mode="cloud"))
    assert "not found" in str(excinfo.value)


def test_factory_cloud_requires_slash():
    from app.core.engine_factory import EngineFactory

    factory = EngineFactory({"ram_total_gb": 16})
    with pytest.raises(ValueError):
        asyncio.run(factory.create_engine("gpt-4o", mode="cloud"))


# ── online services: benchmark runs against any engine (incl. cloud) ──

def test_legacy_benchmark_runs_against_cloud_engine():
    """_legacy_benchmark must pass input_data (not a stray prompt kwarg) so it
    works with every engine — cloud included (no local RAM/engine needed)."""
    from app.api.benchmark import _legacy_benchmark
    from app.schemas.benchmark import BenchmarkRequest

    calls = []

    class _FakeEngine:
        async def generate(self, input_data, **kwargs):
            calls.append((input_data, kwargs.get("max_tokens")))
            return {"completion_tokens": 7}

        def get_memory_usage(self):
            return {"peak_ram_gb": 0}

    class _App:
        state = type("S", (), {
            "active_engine": _FakeEngine(),
            "active_model": "prov_abc/gpt-4o",
            "active_mode": "cloud",
        })()

    result = asyncio.run(_legacy_benchmark(
        _App(), BenchmarkRequest(iterations=2, max_tokens=32)
    ))
    assert result.model == "prov_abc/gpt-4o"
    assert result.mode == "cloud"
    assert len(result.runs) == 2
    assert result.runs[0]["tokens"] == 7
    # prompt is passed positionally as input_data, and max_tokens survives
    assert all(isinstance(p, str) and p for p, _ in calls)
    assert all(mt == 32 for _, mt in calls)