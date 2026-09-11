"""EngineFactory mode resolution + LAN auth middleware (fast, no model files).

Two previously-untested paths:

- ``EngineFactory.create_engine`` — auto-mode resolution (memory-manager
  suggestion, non-generative fallback to fullram, insufficient-memory raise),
  unknown-mode raise, and the cloud branch (provider lookup + CloudAPIEngine,
  malformed/unknown provider rejects). TaskResolver and the MemoryManager are
  stubbed; engine constructors are lightweight so nothing loads weights.
- ``security.middleware.lan_auth_middleware`` — opt-in Bearer enforcement when
  bound beyond localhost, auth-free loopback, case-insensitive scheme.
"""
import asyncio
import types

import pytest
from fastapi import HTTPException

import app.core.engine_factory as engine_factory_mod
from app.core.engine_factory import EngineFactory
from app.security.middleware import lan_auth_middleware


# ── fakes ──

class _FakeMM:
    """Records suggest_mode calls; returns a canned suggestion."""

    def __init__(self, suggestion):
        self.suggestion = suggestion
        self.calls = []

    def suggest_mode(self, model_size_bytes, model_metadata=None):
        self.calls.append({"size": model_size_bytes, "metadata": model_metadata})
        return self.suggestion


class _FakeRegistry:
    """Stands in for CloudProviderRegistry inside the factory's cloud branch."""

    providers = {}

    def __init__(self, *args, **kwargs):
        pass

    def get_provider(self, provider_id):
        return self.providers.get(provider_id)


def _make_factory(monkeypatch, suggestion):
    mm = _FakeMM(suggestion)
    monkeypatch.setattr(engine_factory_mod.EngineFactory, "_shared_memory_manager", mm)
    # Deterministic task resolution — the real TaskResolver needs a full HF
    # config (architectures/model_type) to classify as generative.
    from app.core.task_resolver import TaskResolver
    monkeypatch.setattr(
        TaskResolver, "resolve",
        staticmethod(lambda path: {"task_type": "causal_lm", "is_generative": True}),
    )
    factory = EngineFactory(hardware_profile={"ram_gb": 16})
    return factory, mm


def _model_dir(tmp_path):
    """Minimal HF-style dir: config.json present, no weights needed."""
    d = tmp_path / "model"
    d.mkdir(exist_ok=True)
    (d / "config.json").write_text("{}")
    return d


# ── engine factory: auto mode ──

def test_auto_mode_uses_memory_manager_suggestion(monkeypatch, tmp_path):
    factory, mm = _make_factory(monkeypatch, "layerstream")
    metadata = {"size_gb": 0.5}

    engine = asyncio.run(factory.create_engine(
        str(tmp_path / "model"), mode="auto", model_metadata=metadata,
    ))

    assert engine.mode == "layerstream"
    assert mm.calls == [{"size": int(0.5 * 1024**3), "metadata": metadata}]


def test_auto_mode_forces_fullram_for_non_generative(monkeypatch, tmp_path):
    """LayerStream only supports generative tasks; anything else → fullram."""
    factory, _ = _make_factory(monkeypatch, "layerstream")

    from app.core.task_resolver import TaskResolver
    monkeypatch.setattr(
        TaskResolver, "resolve",
        staticmethod(lambda path: {"task_type": "masked_lm", "is_generative": False}),
    )

    engine = asyncio.run(factory.create_engine(str(tmp_path / "model"), mode="auto"))

    assert engine.mode == "fullram"


def test_auto_mode_insufficient_raises(monkeypatch, tmp_path):
    factory, _ = _make_factory(monkeypatch, "insufficient")

    with pytest.raises(RuntimeError, match="Insufficient memory"):
        asyncio.run(factory.create_engine(str(tmp_path / "model"), mode="auto"))


def test_unknown_mode_raises(monkeypatch, tmp_path):
    factory, _ = _make_factory(monkeypatch, "fullram")

    with pytest.raises(ValueError, match="Unknown mode"):
        asyncio.run(factory.create_engine(str(tmp_path / "model"), mode="bogus"))


# ── engine factory: cloud branch ──

_PROVIDER = {
    "id": "prov_abc",
    "name": "Test Provider",
    "provider_type": "openai",
    "api_key": "sk-test",
    "base_url": "",
}


@pytest.fixture(autouse=True)
def _fake_cloud_registry(monkeypatch):
    from app.engines.cloud import registry as cloud_registry
    monkeypatch.setattr(cloud_registry, "CloudProviderRegistry", _FakeRegistry)
    _FakeRegistry.providers = {"prov_abc": dict(_PROVIDER)}


def test_cloud_mode_builds_cloud_engine():
    factory = EngineFactory(hardware_profile={})

    engine = asyncio.run(factory.create_engine("prov_abc/gpt-mini", mode="cloud"))

    assert type(engine).__name__ == "CloudAPIEngine"
    assert engine.mode == "cloud"
    assert engine.model_id == "gpt-mini"
    assert engine.provider["id"] == "prov_abc"


def test_cloud_mode_rejects_malformed_model_path():
    factory = EngineFactory(hardware_profile={})

    with pytest.raises(ValueError, match="Cloud model must be"):
        asyncio.run(factory.create_engine("just-a-model-id", mode="cloud"))


def test_cloud_mode_rejects_unknown_provider():
    factory = EngineFactory(hardware_profile={})

    with pytest.raises(ValueError, match="Provider 'prov_missing' not found"):
        asyncio.run(factory.create_engine("prov_missing/gpt-mini", mode="cloud"))


# ── LAN auth middleware ──

def _request(sec=None, auth_header=None):
    settings = None
    if sec is not None:
        settings = types.SimpleNamespace(get_security=lambda: sec)
    headers = {}
    if auth_header is not None:
        headers["authorization"] = auth_header
    return types.SimpleNamespace(
        app=types.SimpleNamespace(state=types.SimpleNamespace(settings_service=settings)),
        headers=headers,
    )


def _run_middleware(request):
    calls = []

    async def call_next(req):
        calls.append(req)
        return "ok"

    result = asyncio.run(lan_auth_middleware(request, call_next))
    return result, calls


def test_auth_localhost_stays_open():
    result, calls = _run_middleware(_request(sec={"bind_localhost_only": True, "api_token": "t"}))
    assert result == "ok" and len(calls) == 1


def test_auth_open_but_no_token_configured():
    result, calls = _run_middleware(_request(sec={"bind_localhost_only": False, "api_token": ""}))
    assert result == "ok" and len(calls) == 1


def test_auth_lan_requires_token():
    with pytest.raises(HTTPException) as exc:
        _run_middleware(_request(sec={"bind_localhost_only": False, "api_token": "s3cret"}))
    assert exc.value.status_code == 401


def test_auth_lan_wrong_token_rejected():
    with pytest.raises(HTTPException) as exc:
        _run_middleware(_request(sec={"bind_localhost_only": False, "api_token": "s3cret"},
                                 auth_header="Bearer wrong"))
    assert exc.value.status_code == 401


def test_auth_lan_correct_bearer_passes():
    result, calls = _run_middleware(_request(sec={"bind_localhost_only": False, "api_token": "s3cret"},
                                             auth_header="Bearer s3cret"))
    assert result == "ok" and len(calls) == 1


def test_auth_scheme_is_case_insensitive():
    """RFC 7235: the auth scheme is case-insensitive."""
    result, calls = _run_middleware(_request(sec={"bind_localhost_only": False, "api_token": "s3cret"},
                                             auth_header="bearer s3cret"))
    assert result == "ok" and len(calls) == 1


def test_auth_settings_failure_fails_open():
    """Opt-in design: a broken settings service must not lock out localhost."""
    app = types.SimpleNamespace(state=types.SimpleNamespace(
        settings_service=types.SimpleNamespace(
            get_security=lambda: (_ for _ in ()).throw(RuntimeError("db closed"))
        )
    ))
    request = types.SimpleNamespace(app=app, headers={})
    result, calls = _run_middleware(request)
    assert result == "ok" and len(calls) == 1
