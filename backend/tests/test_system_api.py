"""System API tests (fast).

Regression coverage for the System page reporting hardware as
"Unknown / 0 GB / None" while the WebSocket metrics kept streaming:

* CORS headers were deleted from every response while the "Enable CORS"
  setting was off (the default), so the packaged Electron renderer (origin
  ``app://-``) could not fetch /v1/system/hardware at all.
* /v1/system/resources divided psutil's cumulative bytes-since-boot counter by
  1024**2 and labelled it MB/s, so the dashboard showed ~48000 MB/s.

The CORS cases run a real ASGI app through TestClient instead of importing the
predicate, so they also catch middleware ordering / header-deletion mistakes.
"""
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.security.middleware import lan_auth_middleware


class _StubSettingsService:
    def __init__(self, security: dict):
        self._security = security

    def get_security(self) -> dict:
        return self._security

    def get_data_controls(self) -> dict:
        return {}


def _client(security: dict | None = None) -> TestClient:
    """Minimal app carrying the same middleware wiring as app.main.

    ``security=None`` leaves app.state.settings_service unset, which is how the
    middleware behaves before the settings service is attached (and mirrors the
    default `enable_cors: False`).
    """
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=".*",      # same wiring as app.main
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(lan_auth_middleware)
    if security is not None:
        app.state.settings_service = _StubSettingsService(security)

    @app.get("/probe")
    def probe():
        return {"ok": True}

    return TestClient(app)


# --------------------------------------------------------------------------- #
# CORS: the packaged renderer must be able to reach the API
# --------------------------------------------------------------------------- #

def test_packaged_app_origin_keeps_cors_headers():
    response = _client().get("/probe", headers={"Origin": "app://-"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "app://-"


def test_dev_server_origin_keeps_cors_headers():
    response = _client().get("/probe", headers={"Origin": "http://localhost:3000"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_packaged_app_preflight_is_answered():
    response = _client().options("/probe", headers={
        "Origin": "app://-",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.headers.get("access-control-allow-origin") == "app://-"


def test_unlisted_origin_is_denied_while_enable_cors_is_off():
    response = _client({"enable_cors": False}).get(
        "/probe", headers={"Origin": "https://evil.example"}
    )
    assert "access-control-allow-origin" not in response.headers


def test_enable_cors_allows_any_origin():
    response = _client({"enable_cors": True}).get(
        "/probe", headers={"Origin": "https://evil.example"}
    )
    assert response.headers.get("access-control-allow-origin") == "https://evil.example"


# --------------------------------------------------------------------------- #
# /v1/system/resources disk throughput
# --------------------------------------------------------------------------- #

def _io(read_mb: float, write_mb: float) -> SimpleNamespace:
    return SimpleNamespace(read_bytes=int(read_mb * 1024 ** 2),
                           write_bytes=int(write_mb * 1024 ** 2))


def test_disk_rates_are_deltas_not_cumulative_counters(monkeypatch):
    from app.api import system

    readings = [_io(50_000, 30_000), _io(50_020, 30_010)]
    monkeypatch.setattr(system.psutil, "disk_io_counters", lambda: readings.pop(0))
    monkeypatch.setattr(system, "_prev_disk_io", None)
    clock = iter([100.0, 102.0])
    monkeypatch.setattr(system.time, "monotonic", lambda: next(clock))

    assert system._disk_rates_mb_s() == (0.0, 0.0)     # cold call: no baseline yet
    assert system._disk_rates_mb_s() == (10.0, 5.0)    # 20 MB / 2 s, 10 MB / 2 s


def test_disk_rates_survive_missing_counters(monkeypatch):
    from app.api import system

    monkeypatch.setattr(system.psutil, "disk_io_counters", lambda: None)
    assert system._disk_rates_mb_s() == (0.0, 0.0)
