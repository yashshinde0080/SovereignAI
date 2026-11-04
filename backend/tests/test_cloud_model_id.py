"""Cloud model-id resolution (``ModelManager._resolve_cloud_model_id``).

The load endpoint takes "<provider_id>/<model_id>", but callers routinely pass
a bare provider-side id ("oc/big-pickle"), whose own prefix looks like a
provider id but isn't one. The resolver must qualify it against the enabled
providers' live model lists, and fail loudly (not with a bare 404) when the id
is unknown or offered by several providers.
"""
import asyncio
import types

import pytest

from app.engines.cloud import providers, registry as cloud_registry
from app.services.model_manager import ModelManager

# oc/big-pickle is offered by prov_a only; oc/shared-model by both.
_LISTED = {
    "prov_a": ["oc/big-pickle", "nvidia/nemotron-3-ultra-550b-a55b", "oc/shared-model"],
    "prov_b": ["oc/shared-model"],
}


@pytest.fixture
def fake_cloud(monkeypatch):
    """Two enabled providers; model lists served without network."""
    class _Reg:
        def __init__(self, *args, **kwargs):
            pass

        def get_provider(self, provider_id):
            return {"id": provider_id} if provider_id in _LISTED else None

        def get_enabled_providers(self):
            return [{"id": pid, "name": pid} for pid in _LISTED]

    async def _fetch(provider, session):
        return [{"id": m} for m in _LISTED[provider["id"]]]

    monkeypatch.setattr(cloud_registry, "CloudProviderRegistry", _Reg)
    monkeypatch.setattr(providers, "fetch_models", _fetch)


def test_qualified_id_skips_network(monkeypatch, fake_cloud):
    async def _boom(*a, **k):
        raise AssertionError("qualified id must not hit the provider")

    monkeypatch.setattr(providers, "fetch_models", _boom)
    resolved = asyncio.run(ModelManager()._resolve_cloud_model_id("prov_a/anything"))
    assert resolved == "prov_a/anything"


def test_bare_id_is_qualified(fake_cloud):
    resolved = asyncio.run(ModelManager()._resolve_cloud_model_id("oc/big-pickle"))
    assert resolved == "prov_a/oc/big-pickle"


def test_bare_id_offered_by_two_providers_is_ambiguous(fake_cloud):
    with pytest.raises(ValueError, match="more than one provider"):
        asyncio.run(ModelManager()._resolve_cloud_model_id("oc/shared-model"))


def test_unknown_model_reports_not_found(fake_cloud):
    # "not found" is what the API maps to 404; the message stays explanatory.
    with pytest.raises(ValueError, match="not found in any configured provider"):
        asyncio.run(ModelManager()._resolve_cloud_model_id("oc/does-not-exist"))


def test_no_providers_configured(monkeypatch):
    class _Empty:
        def __init__(self, *args, **kwargs):
            pass

        def get_provider(self, provider_id):
            return None

        def get_enabled_providers(self):
            return []

    monkeypatch.setattr(cloud_registry, "CloudProviderRegistry", _Empty)
    with pytest.raises(ValueError, match="No cloud providers configured"):
        asyncio.run(ModelManager()._resolve_cloud_model_id("oc/big-pickle"))


def test_auto_mode_routes_qualified_id_to_cloud(monkeypatch, fake_cloud):
    """A "<provider_id>/…" id must never fall through to the local registry."""
    manager = ModelManager()
    manager.app = types.SimpleNamespace(state=types.SimpleNamespace())
    calls = {}

    async def _fake_locked(_self, model_id, mode, model, resolved_id, all_models):
        calls.update(model=model_id, mode=mode, all_models=all_models)
        return {"status": "loaded"}

    monkeypatch.setattr(ModelManager, "_load_model_locked", _fake_locked)
    asyncio.run(manager.load_model("prov_a/oc/big-pickle", mode="auto"))

    assert calls["mode"] == "cloud"
    assert calls["model"] == "prov_a/oc/big-pickle"
    assert calls["all_models"] == []
