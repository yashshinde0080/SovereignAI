"""Smoke test: the FastAPI app imports and serves basic routes via TestClient.

The project docs claimed TestClient was broken by a starlette/httpx
incompatibility; this test proves otherwise (starlette + httpx 0.28 works,
with a deprecation warning only). If this fails, real e2e tests are blocked
again.

NOTE: TestClient is used WITHOUT a context manager on purpose — entering the
context runs the app lifespan, which touches real workspace/ state (DBs,
vector index) and pollutes the vectorstore tests. A plain TestClient(app)
serves routes without lifespan.
"""
from fastapi.testclient import TestClient

from app.main import app


def test_app_serves_root():
    client = TestClient(app)  # no `with` — no lifespan, no workspace side effects
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "running"
