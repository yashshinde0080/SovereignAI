"""Custom-agent tests (fast): per-request agent resolution, prompt isolation,
sampling precedence, preferred-model loading, and save-time validation.

Two layers, mirroring the existing suites:
- HTTP: POST /v1/chat/completions through the real stack with a fake engine
  (TestClient WITHOUT a context manager, so no lifespan — see
  test_chat_api_http.py).
- Direct: settings router functions with a hand-built Request, like
  test_settings_behavior.py.
"""
import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api.chat import _resolve_agent, _resolve_sampling
from app.schemas.chat import ChatRequest
from app.settings.schemas import AgentConfig, AgentRole
from app.settings.service import SettingsService
from app.main import app


# ── helpers ──

def _make_request(app_state):
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/settings/agents",
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


class _ModelManager:
    def __init__(self, installed=(), fail=False):
        self.installed = list(installed)
        self.fail = fail
        self.loads = []

    async def list_models(self):
        return [{"name": n} for n in self.installed]

    async def load_model(self, model_id, mode="auto"):
        self.loads.append((model_id, mode))
        if self.fail:
            raise RuntimeError("no such weights")
        return {"status": "loaded"}


class _Registry:
    def __init__(self, ids=()):
        self.ids = set(ids)

    def get_provider(self, provider_id):
        return {"id": provider_id} if provider_id in self.ids else None


class _AppState:
    def __init__(self, engine=None, models=None, providers=()):
        self.active_engine = engine
        self.active_model = "fake-model" if engine else None
        self.active_mode = "fullram" if engine else None
        self.model_manager = models if models is not None else _ModelManager()
        self.cloud_provider_registry = _Registry(providers)


class _FakeEngine:
    """`mode` != 'cloud' so chat.py renders a prompt string the test can read."""

    mode = "fullram"
    tokenizer = None

    def __init__(self):
        self.calls = []

    async def generate(self, input_data, **kwargs):
        self.calls.append((input_data, kwargs))
        return {"output": "ok", "finish_reason": "stop"}

    async def generate_stream(self, input_data, **kwargs):
        self.calls.append((input_data, kwargs))
        yield {"token": "ok", "finish_reason": "stop"}


# ── shipped examples exist and are editable configs, not hardcoded replies ──

def test_example_agents_are_seeded(tmp_path):
    svc = SettingsService(str(tmp_path / "s.db"))
    agents = {a["id"]: a for a in svc.get_all_agents()}
    for agent_id, role, title in (
        ("agent_ceo", "ceo", "Chief Executive Officer"),
        ("agent_cto", "cto", "Chief Technology Officer"),
        ("agent_senior_engineer", "software_engineer", "Senior Software Engineer"),
        ("agent_ml_engineer", "ml_engineer", "AI / Machine Learning Engineer"),
        ("agent_research_analyst", "research_analyst", "Research Analyst"),
    ):
        assert agent_id in agents, f"{agent_id} missing from seeded agents"
        assert agents[agent_id]["role"] == role
        assert agents[agent_id]["job_title"] == title
        assert agents[agent_id]["system_instruction"].strip()
        assert agents[agent_id]["responsibilities"].strip()
        assert agents[agent_id]["welcome_message"].strip()
    svc.db.close()


def test_deleted_example_does_not_come_back(tmp_path):
    """Seeding is once-per-install: deleting a shipped example must stick."""
    path = str(tmp_path / "s.db")
    svc = SettingsService(path)
    assert svc.delete_agent("agent_ceo") is True
    svc.db.close()

    again = SettingsService(path)  # simulated restart
    assert again.get_agent("agent_ceo") is None
    assert again.get_agent("agent_cto") is not None
    again.db.close()


def test_agent_config_roundtrip_persists_new_fields(tmp_path):
    path = str(tmp_path / "s.db")
    svc = SettingsService(path)
    agent = AgentConfig(
        id="agent_custom1",
        name="Packaging Lead",
        role=AgentRole.CUSTOM,
        job_title="Head of Packaging",
        description="Packaging decisions.",
        system_instruction="You are the packaging lead.",
        responsibilities="- Own carton specs",
        preferred_model="",
        welcome_message="What are we shipping?",
        tool_permissions=["read_project_files", "system_info"],
        temperature=0.2,
        max_tokens=1234,
        enabled=True,
    )
    assert svc.create_agent(agent) is True
    svc.db.close()

    again = SettingsService(path)
    stored = again.get_agent("agent_custom1")
    assert stored["job_title"] == "Head of Packaging"
    assert stored["responsibilities"] == "- Own carton specs"
    assert stored["welcome_message"] == "What are we shipping?"
    assert stored["tool_permissions"] == ["read_project_files", "system_info"]
    assert stored["temperature"] == 0.2
    assert stored["max_tokens"] == 1234
    again.db.close()


# ── schema validation ──

def test_unknown_tool_permission_rejected():
    with pytest.raises(Exception):
        AgentConfig(id="a", name="A", role=AgentRole.CUSTOM, tool_permissions=["rm_rf"])


def test_tool_permissions_deduped():
    a = AgentConfig(
        id="a", name="A", role=AgentRole.CUSTOM,
        tool_permissions=["system_info", "system_info", "analyze_code"],
    )
    assert a.tool_permissions == ["system_info", "analyze_code"]


def test_agent_id_and_name_validated():
    with pytest.raises(Exception):
        AgentConfig(id="bad id!", name="A", role=AgentRole.CUSTOM)
    with pytest.raises(Exception):
        AgentConfig(id="a", name="", role=AgentRole.CUSTOM)
    with pytest.raises(Exception):
        AgentConfig(id="a", name="A", role=AgentRole.CUSTOM, temperature=3.0)
    with pytest.raises(Exception):
        AgentConfig(id="a", name="A", role=AgentRole.CUSTOM, max_tokens=10)


def test_unknown_role_rejected():
    with pytest.raises(Exception):
        AgentConfig(id="a", name="A", role="wizard")


# ── chat: agent resolution ──

def test_resolve_agent_rejects_unknown_disabled_and_unavailable(tmp_path):
    svc = SettingsService(str(tmp_path / "s.db"))
    with pytest.raises(Exception) as exc:
        _resolve_agent(svc, "agent_ghost")
    assert exc.value.status_code == 404

    agent = svc.get_agent("agent_ceo")
    agent["enabled"] = False
    svc.db.update_agent("agent_ceo", AgentConfig(**agent))
    with pytest.raises(Exception) as exc:
        _resolve_agent(svc, "agent_ceo")
    assert exc.value.status_code == 409

    with pytest.raises(Exception) as exc:
        _resolve_agent(None, "agent_ceo")
    assert exc.value.status_code == 400

    # No agent named -> plain assistant, no error.
    assert _resolve_agent(None, None) is None
    assert _resolve_agent(svc, "") is None
    svc.db.close()


def test_system_prompt_is_isolated_per_agent(tmp_path):
    svc = SettingsService(str(tmp_path / "s.db"))
    ceo = svc.build_system_prompt(svc.get_agent("agent_ceo"))
    cto = svc.build_system_prompt(svc.get_agent("agent_cto"))
    assert "Chief Executive Officer" in ceo
    assert "Chief Technology Officer" in cto
    assert "Chief Technology Officer" not in ceo
    assert "Chief Executive Officer" not in cto
    svc.db.close()


# ── chat: sampling precedence ──

def test_agent_sampling_beats_saved_general():
    svc = type("S", (), {"get_general": staticmethod(
        lambda: {"temperature": 0.7, "top_p": 0.5, "max_tokens": 512})})()
    agent = {"temperature": 0.2, "max_tokens": 3072}
    req = ChatRequest(messages=[{"role": "user", "content": "hi"}])
    out = _resolve_sampling(req, svc, agent)
    assert out["temperature"] == 0.2      # agent wins over saved general
    assert out["max_tokens"] == 3072
    assert out["top_p"] == 0.5            # agent didn't set it -> saved general


def test_explicit_request_beats_agent():
    svc = type("S", (), {"get_general": staticmethod(lambda: {"temperature": 0.7})})()
    agent = {"temperature": 0.2, "max_tokens": 3072}
    req = ChatRequest(messages=[{"role": "user", "content": "hi"}], temperature=1.5)
    assert _resolve_sampling(req, svc, agent)["temperature"] == 1.5


def test_agent_sampling_without_settings_service():
    agent = {"temperature": 0.2, "max_tokens": 3072}
    req = ChatRequest(messages=[{"role": "user", "content": "hi"}])
    out = _resolve_sampling(req, None, agent)
    assert out == {"temperature": 0.2, "top_p": 0.9, "max_tokens": 3072}


def test_request_max_tokens_may_exceed_old_4096_cap():
    """Regression: GeneralSettings allows 32768 but ChatRequest capped 4096, so a
    valid saved config made every chat request fail with HTTP 422."""
    req = ChatRequest(messages=[{"role": "user", "content": "hi"}], max_tokens=32768)
    assert req.max_tokens == 32768


# ── chat HTTP: the selected agent actually reaches the model ──

@pytest.fixture()
def client():
    return TestClient(app)  # no `with`: no lifespan, no workspace side effects


@pytest.fixture()
def wired(tmp_path):
    """Real SettingsService + fake engine on the real app.state."""
    svc = SettingsService(str(tmp_path / "s.db"))
    engine = _FakeEngine()
    app.state.active_engine = engine
    app.state.active_model = "fake-model"
    app.state.active_mode = "fullram"
    app.state.settings_service = svc
    app.state.vector_store = None
    app.state.model_manager = _ModelManager(installed=["fake-model"])
    yield svc, engine
    app.state.active_engine = None
    app.state.active_model = None
    app.state.settings_service = None
    app.state.model_manager = None
    svc.db.close()


def test_chat_uses_selected_agent_instructions(client, wired):
    _, engine = wired
    r = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "What should we prioritize in our next release?"}],
        "agent_id": "agent_ceo",
    })
    assert r.status_code == 200
    prompt, kwargs = engine.calls[0]
    assert "Chief Executive Officer" in prompt
    assert "Chief Technology Officer" not in prompt
    assert "What should we prioritize in our next release?" in prompt
    assert kwargs["temperature"] == 0.4    # CEO config, not the 0.7 default
    assert kwargs["max_tokens"] == 3072


def test_switching_agent_switches_instructions(client, wired):
    _, engine = wired
    for agent_id, expect, not_expect in (
        ("agent_ceo", "Chief Executive Officer", "Chief Technology Officer"),
        ("agent_cto", "Chief Technology Officer", "Chief Executive Officer"),
    ):
        r = client.post("/v1/chat/completions", json={
            "messages": [{"role": "user", "content": "hello"}],
            "agent_id": agent_id,
        })
        assert r.status_code == 200
        prompt, _ = engine.calls[-1]
        assert expect in prompt
        assert not_expect not in prompt


def test_chat_unknown_agent_is_404(client, wired):
    r = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "hi"}],
        "agent_id": "agent_ghost",
    })
    assert r.status_code == 404


def test_chat_disabled_agent_is_409(client, wired):
    svc, _ = wired
    agent = svc.get_agent("agent_cto")
    agent["enabled"] = False
    svc.update_agent("agent_cto", AgentConfig(**agent))
    r = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "hi"}],
        "agent_id": "agent_cto",
    })
    assert r.status_code == 409


def test_chat_without_model_and_without_agent_preference_explains_what_to_do(client, wired):
    _, engine = wired
    app.state.active_engine = None
    app.state.active_model = None
    r = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert r.status_code == 400
    assert "No model loaded" in r.json()["error"]["message"]
    assert "Agents" in r.json()["error"]["message"]
    assert engine.calls == []


def test_chat_loads_agent_preferred_model_when_none_loaded(client, wired):
    svc, _ = wired
    agent = svc.get_agent("agent_ceo")
    agent["preferred_model"] = "fake-model"
    svc.update_agent("agent_ceo", AgentConfig(**agent))

    app.state.active_engine = None
    app.state.active_model = None
    loaded = _FakeEngine()

    class _MM(_ModelManager):
        async def load_model(self, model_id, mode="auto"):
            self.loads.append((model_id, mode))
            app.state.active_engine = loaded
            app.state.active_model = model_id
            app.state.active_mode = "fullram"
            return {"status": "loaded"}

    app.state.model_manager = _MM()
    r = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "hi"}],
        "agent_id": "agent_ceo",
    })
    assert r.status_code == 200
    assert app.state.model_manager.loads == [("fake-model", "auto")]
    assert "Chief Executive Officer" in loaded.calls[0][0]


def test_chat_reports_agent_preferred_model_load_failure(client, wired):
    svc, _ = wired
    agent = svc.get_agent("agent_ceo")
    agent["preferred_model"] = "missing-model"
    svc.update_agent("agent_ceo", AgentConfig(**agent))

    app.state.active_engine = None
    app.state.active_model = None
    app.state.model_manager = _ModelManager(fail=True)
    r = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "hi"}],
        "agent_id": "agent_ceo",
    })
    assert r.status_code == 400
    assert "missing-model" in r.json()["error"]["message"]


def test_active_agent_used_when_no_agent_id_given(client, wired):
    """Existing behaviour: the is_active flag still drives the default prompt."""
    svc, engine = wired
    svc.activate_agent("agent_cto")
    r = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert r.status_code == 200
    prompt, _ = engine.calls[0]
    assert "Chief Technology Officer" in prompt


# ── settings router: save-time validation ──

def _patch_service(monkeypatch, tmp_path):
    from app.settings import router as settings_router
    svc = SettingsService(str(tmp_path / "s.db"))
    monkeypatch.setattr(settings_router, "service", svc)
    return settings_router, svc


def test_create_agent_rejects_duplicate_name(monkeypatch, tmp_path):
    router, _ = _patch_service(monkeypatch, tmp_path)
    state = _AppState()
    dup = AgentConfig(id="agent_dupe", name="CEO Agent", role=AgentRole.CEO)
    with pytest.raises(Exception) as exc:
        _run(router.create_agent(_make_request(state), dup))
    assert exc.value.status_code == 409
    # Same name with different case is still a duplicate.
    dup2 = AgentConfig(id="agent_dupe", name="ceo agent", role=AgentRole.CEO)
    with pytest.raises(Exception) as exc:
        _run(router.create_agent(_make_request(state), dup2))
    assert exc.value.status_code == 409


def test_update_agent_rejects_duplicate_name_but_allows_itself(monkeypatch, tmp_path):
    router, svc = _patch_service(monkeypatch, tmp_path)
    state = _AppState()
    own = AgentConfig(**{**svc.get_agent("agent_cto"), "name": "CTO Agent"})
    resp = _run(router.update_agent(_make_request(state), "agent_cto", own))
    assert resp.success is True

    clash = AgentConfig(**{**svc.get_agent("agent_cto"), "name": "CEO Agent"})
    with pytest.raises(Exception) as exc:
        _run(router.update_agent(_make_request(state), "agent_cto", clash))
    assert exc.value.status_code == 409


def test_update_agent_missing_is_404(monkeypatch, tmp_path):
    router, _ = _patch_service(monkeypatch, tmp_path)
    state = _AppState()
    ghost = AgentConfig(id="agent_ghost", name="Ghost", role=AgentRole.CUSTOM)
    with pytest.raises(Exception) as exc:
        _run(router.update_agent(_make_request(state), "agent_ghost", ghost))
    assert exc.value.status_code == 404


def test_create_agent_rejects_uninstalled_preferred_model(monkeypatch, tmp_path):
    router, _ = _patch_service(monkeypatch, tmp_path)
    state = _AppState(models=_ModelManager(installed=["llama3:8b"]))
    agent = AgentConfig(
        id="agent_x", name="X", role=AgentRole.CUSTOM, preferred_model="not-installed"
    )
    with pytest.raises(Exception) as exc:
        _run(router.create_agent(_make_request(state), agent))
    assert exc.value.status_code == 422

    ok = AgentConfig(
        id="agent_x", name="X", role=AgentRole.CUSTOM, preferred_model="llama3:8b"
    )
    assert _run(router.create_agent(_make_request(state), ok)).success is True


def test_create_agent_rejects_unconfigured_cloud_provider(monkeypatch, tmp_path):
    router, _ = _patch_service(monkeypatch, tmp_path)
    state = _AppState(models=_ModelManager(), providers=["prov_ok"])
    bad = AgentConfig(
        id="agent_y", name="Y", role=AgentRole.CUSTOM, preferred_model="prov_bad/gpt-4o"
    )
    with pytest.raises(Exception) as exc:
        _run(router.create_agent(_make_request(state), bad))
    assert exc.value.status_code == 422

    good = AgentConfig(
        id="agent_y", name="Y", role=AgentRole.CUSTOM, preferred_model="prov_ok/gpt-4o"
    )
    assert _run(router.create_agent(_make_request(state), good)).success is True


def test_create_agent_allows_preferred_model_when_nothing_installed(monkeypatch, tmp_path):
    router, _ = _patch_service(monkeypatch, tmp_path)
    state = _AppState(models=_ModelManager(installed=[]))
    agent = AgentConfig(
        id="agent_z", name="Z", role=AgentRole.CUSTOM, preferred_model="future-model"
    )
    assert _run(router.create_agent(_make_request(state), agent)).success is True


def test_duplicate_agent_copies_config_under_new_id(monkeypatch, tmp_path):
    router, svc = _patch_service(monkeypatch, tmp_path)
    state = _AppState()
    resp = _run(router.duplicate_agent(_make_request(state), "agent_ceo"))
    assert resp.success is True

    copies = [a for a in svc.get_all_agents() if a["name"] == "CEO Agent (copy)"]
    assert len(copies) == 1
    assert copies[0]["id"] != "agent_ceo"
    assert copies[0]["job_title"] == "Chief Executive Officer"
    assert copies[0]["is_active"] is False

    with pytest.raises(Exception) as exc:
        _run(router.duplicate_agent(_make_request(state), "agent_ceo"))
    assert exc.value.status_code == 409  # name already taken


def test_duplicate_agent_missing_is_404(monkeypatch, tmp_path):
    router, _ = _patch_service(monkeypatch, tmp_path)
    with pytest.raises(Exception) as exc:
        _run(router.duplicate_agent(_make_request(_AppState()), "agent_ghost"))
    assert exc.value.status_code == 404
