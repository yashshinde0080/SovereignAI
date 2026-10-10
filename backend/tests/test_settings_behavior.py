"""Settings behavior tests (fast): sampling fallback, persistence, default_mode
validation, settings-changed broadcast, startup-model reload guard.

Uses a temp SettingsDatabase + SettingsService; router endpoints are called
directly (TestClient broken in this venv — starlette/httpx mismatch, see
test_openai_compat.py docstring).
"""
import asyncio
import json

import pytest
from starlette.requests import Request

from app.settings.database import SettingsDatabase
from app.settings.service import SettingsService
from app.settings.schemas import GeneralSettings, SecuritySettings, ParentalControlsSettings, DataControlsSettings
from app.api.chat import _resolve_sampling, _trim_history, _parental_block
from app.schemas.chat import ChatRequest


# ── helpers ──

def _make_request(app_state=None):
    """Real starlette Request with a fake app, like test_openai_compat.py."""
    scope = {
        "type": "http",
        "method": "POST",
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


class _FakeEngine:
    mode = "fullram"
    tokenizer = None
    is_generating = False

    def __init__(self):
        self.calls = []

    async def generate(self, input_data=None, **kwargs):
        self.calls.append(kwargs)
        return {"output": "ok", "finish_reason": "stop"}

    async def generate_stream(self, input_data=None, **kwargs):
        self.calls.append(kwargs)
        yield {"token": "ok", "finish_reason": "stop"}

    def get_memory_usage(self):
        return {}


# ── _resolve_sampling: request > saved settings > schema default ──

def test_sampling_request_wins_over_saved():
    svc = type("S", (), {"get_general": staticmethod(
        lambda: {"temperature": 0.2, "top_p": 0.5, "max_tokens": 999})},)()
    req = ChatRequest(messages=[{"role": "user", "content": "hi"}], temperature=1.5)
    out = _resolve_sampling(req, svc)
    assert out["temperature"] == 1.5
    assert out["top_p"] == 0.5      # omitted -> saved
    assert out["max_tokens"] == 999  # omitted -> saved


def test_sampling_saved_used_when_omitted():
    svc = type("S", (), {"get_general": staticmethod(
        lambda: {"temperature": 0.2, "top_p": 0.5, "max_tokens": 999})},)()
    req = ChatRequest(messages=[{"role": "user", "content": "hi"}])
    out = _resolve_sampling(req, svc)
    assert out == {"temperature": 0.2, "top_p": 0.5, "max_tokens": 999}


def test_sampling_schema_default_when_no_settings_service():
    req = ChatRequest(messages=[{"role": "user", "content": "hi"}])
    out = _resolve_sampling(req, None)
    assert out == {"temperature": 0.7, "top_p": 0.9, "max_tokens": 512}


def test_sampling_survives_broken_settings_service():
    def boom():
        raise RuntimeError("db closed")

    svc = type("S", (), {"get_general": staticmethod(boom)})()
    req = ChatRequest(messages=[{"role": "user", "content": "hi"}])
    out = _resolve_sampling(req, svc)
    assert out == {"temperature": 0.7, "top_p": 0.9, "max_tokens": 512}


# ── schema validation ──

def test_default_mode_literal_rejects_invalid():
    with pytest.raises(Exception):
        GeneralSettings(default_mode="layerstream_legacy")


def test_default_mode_accepts_valid():
    for mode in ("auto", "fullram", "layerstream", "cloud"):
        assert GeneralSettings(default_mode=mode).default_mode == mode


def test_generation_bounds_reject():
    with pytest.raises(Exception):
        GeneralSettings(temperature=2.5)
    with pytest.raises(Exception):
        GeneralSettings(top_p=1.5)
    with pytest.raises(Exception):
        GeneralSettings(max_tokens=0)


# ── persistence across service instances (restart simulation) ──

def test_settings_persist_across_restart(tmp_path):
    db1 = SettingsDatabase(str(tmp_path / "s.db"))
    svc1 = SettingsService(str(tmp_path / "s.db"))
    svc1.update_general(GeneralSettings(temperature=1.23, max_tokens=777))
    db1.close()

    svc2 = SettingsService(str(tmp_path / "s.db"))  # fresh instance = "restart"
    general = svc2.get_general()
    assert general["temperature"] == 1.23
    assert general["max_tokens"] == 777


def test_corrupt_section_falls_back_to_defaults(tmp_path):
    db = SettingsDatabase(str(tmp_path / "s.db"))
    # Corrupt the general section's JSON blob directly
    conn = db._get_connection()
    conn.execute("UPDATE settings SET data = '{not json' WHERE section = 'general'")
    conn.commit()

    svc = SettingsService(str(tmp_path / "s.db"))
    general = svc.get_general()
    assert general == GeneralSettings().model_dump()
    db.close()


# ── settings router: update_general (reload guard + broadcast) ──

class _ModelManager:
    def __init__(self):
        self.loads = []

    async def load_model(self, model_id, mode="auto"):
        self.loads.append((model_id, mode))
        return {"status": "loaded"}


class _AppState:
    def __init__(self, active_model=None, active_mode=None, engine=None):
        self.active_model = active_model
        self.active_mode = active_mode
        self.active_engine = engine
        self.model_manager = _ModelManager()


def _run(coro):
    return asyncio.run(coro)


def test_update_general_triggers_reload_when_target_differs(tmp_path, monkeypatch):
    from app.settings import router as settings_router

    monkeypatch.setattr(settings_router, "service", SettingsService(str(tmp_path / "s.db")))

    app_state = _AppState(active_model="old-model", active_mode="fullram")
    request = _make_request(app_state)
    body = GeneralSettings(startup_model="new-model", default_mode="layerstream")

    resp = _run(settings_router.update_general_settings(request, body))

    assert resp.success is True
    assert app_state.model_manager.loads == [("new-model", "layerstream")]


def test_update_general_no_reload_when_same_model_and_mode(tmp_path, monkeypatch):
    from app.settings import router as settings_router

    monkeypatch.setattr(settings_router, "service", SettingsService(str(tmp_path / "s.db")))

    app_state = _AppState(active_model="same-model", active_mode="fullram")
    request = _make_request(app_state)
    body = GeneralSettings(startup_model="same-model", default_mode="fullram")

    resp = _run(settings_router.update_general_settings(request, body))

    assert resp.success is True
    assert app_state.model_manager.loads == []


def test_update_general_reload_blocked_while_generating(tmp_path, monkeypatch):
    from app.settings import router as settings_router

    monkeypatch.setattr(settings_router, "service", SettingsService(str(tmp_path / "s.db")))

    engine = _FakeEngine()
    engine.is_generating = True
    app_state = _AppState(active_model="old-model", active_mode="fullram", engine=engine)
    request = _make_request(app_state)
    body = GeneralSettings(startup_model="new-model", default_mode="auto")

    with pytest.raises(Exception) as exc:
        _run(settings_router.update_general_settings(request, body))
    assert getattr(exc.value, "status_code", None) == 409
    assert app_state.model_manager.loads == []


def test_update_general_validates_default_mode(tmp_path, monkeypatch):
    from app.settings import router as settings_router
    from fastapi import HTTPException

    monkeypatch.setattr(settings_router, "service", SettingsService(str(tmp_path / "s.db")))

    request = _make_request(_AppState())
    with pytest.raises(Exception):
        _run(settings_router.update_general_settings(
            request, GeneralSettings(default_mode="bogus")))  # type: ignore[arg-type]


# ── broadcast ──

def test_broadcast_settings_changed_no_listener_is_safe():
    from app.settings.router import _broadcast_settings_changed

    # No websocket clients connected — must not raise
    _run(_broadcast_settings_changed("general"))


# ── context trimming (max_context_length) ──

def test_trim_history_keeps_system_and_recent():
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "a" * 100},
        {"role": "assistant", "content": "b" * 100},
        {"role": "user", "content": "c" * 20},
    ]
    out = _trim_history(msgs, 50)  # 50 * 4 = 200 char budget
    assert out[0]["role"] == "system"
    assert out[-1] == msgs[-1]
    assert sum(len(m["content"]) for m in out[1:]) <= 200


def test_trim_history_never_drops_last_message():
    msgs = [
        {"role": "user", "content": "x" * 5000},
    ]
    out = _trim_history(msgs, 1)
    assert out == msgs  # single message always kept


def test_trim_history_bad_setting_is_noop():
    msgs = [{"role": "user", "content": "hi"}]
    assert _trim_history(msgs, None) == msgs
    assert _trim_history(msgs, "bogus") == msgs


# ── parental content gate ──

def test_parental_block_off_when_disabled():
    pc = {"enabled": False, "restrict_topics": ["guns"], "block_explicit_content": True}
    assert _parental_block(pc, "tell me about guns") is None


def test_parental_block_topic():
    pc = {"enabled": True, "restrict_topics": ["Guns"], "block_explicit_content": False}
    assert _parental_block(pc, "how to build guns") is not None
    assert _parental_block(pc, "harmless question") is None


def test_parental_block_explicit():
    pc = {"enabled": True, "restrict_topics": [], "block_explicit_content": True}
    assert _parental_block(pc, "some xxx thing") is not None
    assert _parental_block(pc, "a class trip") is None


def test_parental_none_passthrough():
    assert _parental_block(None, "anything") is None


# ── retention map + audit gating ──

def test_retention_seconds_map():
    from app.lib.retention import RETENTION_SECONDS

    assert RETENTION_SECONDS["1_day"] == 86400
    assert RETENTION_SECONDS["90_days"] == 90 * 86400


def test_log_audit_gated_by_audit_logging(tmp_path):
    svc = SettingsService(str(tmp_path / "s.db"))
    # default audit_logging=True → logged
    svc.log_audit("chat_request", "chat", "{}")
    assert len(svc.get_audit_log()) == 1
    # turn audit_logging off (this update itself lands as an audit row)
    svc.update_security(SecuritySettings(audit_logging=False))
    assert len(svc.get_audit_log()) == 2
    svc.log_audit("chat_request", "chat", "{}")
    assert len(svc.get_audit_log()) == 2  # gated: unchanged
    # update events always logged
    svc.log_audit("update", "general", "{}")
    assert len(svc.get_audit_log()) == 3


# ── model manager: allowed_models + encrypt_models wiring ──

async def test_model_manager_allowed_models_block(tmp_path):
    from app.services.model_manager import ModelManager

    svc = SettingsService(str(tmp_path / "s.db"))
    svc.update_parental_controls(
        ParentalControlsSettings(enabled=True, allowed_models=["Qwen2-0.5B"])
    )
    mm = ModelManager(settings_service=svc)
    with pytest.raises(PermissionError):
        mm._check_allowed_models("llama3:8b")
    mm._check_allowed_models("qwen2-0.5b")  # normalized match passes


async def test_encrypt_models_flag_off_disables_helper(tmp_path):
    from app.services.model_manager import ModelManager

    svc = SettingsService(str(tmp_path / "s.db"))
    svc.update_security(SecuritySettings(encrypt_models=False))
    mm = ModelManager(settings_service=svc)
    assert mm._encrypt_models_enabled() is False


# ── middleware: log_api_requests + enable_cors strip ──

async def test_middleware_cors_strip(tmp_path):
    from app.security.middleware import lan_auth_middleware
    from starlette.responses import JSONResponse

    svc = SettingsService(str(tmp_path / "s.db"))
    svc.update_security(SecuritySettings(enable_cors=False))

    async def call_next(request):
        resp = JSONResponse({"ok": True})
        resp.headers["access-control-allow-origin"] = "*"
        resp.headers["access-control-allow-methods"] = "GET, POST"
        return resp

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/v1/system/status",
        "headers": [],
        "query_string": b"",
        "server": ("t", 80),
        "client": ("127.0.0.1", 1),
        "scheme": "http",
        "app": type("App", (), {"state": type("S", (), {"settings_service": svc})()})(),
    }
    req = Request(scope, lambda: None)
    resp = await lan_auth_middleware(req, call_next)
    assert "access-control-allow-origin" not in resp.headers
    assert "access-control-allow-methods" not in resp.headers


async def test_middleware_cors_kept_when_enabled(tmp_path):
    from app.security.middleware import lan_auth_middleware
    from starlette.responses import JSONResponse

    svc = SettingsService(str(tmp_path / "s.db"))
    svc.update_security(SecuritySettings(enable_cors=True))

    async def call_next(request):
        resp = JSONResponse({"ok": True})
        resp.headers["access-control-allow-origin"] = "*"
        return resp

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/v1/system/status",
        "headers": [],
        "query_string": b"",
        "server": ("t", 80),
        "client": ("127.0.0.1", 1),
        "scheme": "http",
        "app": type("App", (), {"state": type("S", (), {"settings_service": svc})()})(),
    }
    req = Request(scope, lambda: None)
    resp = await lan_auth_middleware(req, call_next)
    assert resp.headers["access-control-allow-origin"] == "*"
