"""Startup/shutdown lifecycle: one backend instance, nothing left open.

Reproduces the packaged-release failures in-process:

* a second backend on a busy port (``[Errno 10048]``) — the entry points must
  refuse and exit 3 instead of racing for the same SQLite file;
* SQLite left open at shutdown ("database is locked");
* background work surviving the event loop ("RuntimeError: Event loop is
  closed"), which covers the aiosqlite registry thread and the metrics poller.

All fixtures are inline (no conftest.py in this project) and the lifespan runs
against a temp data root, so repeated runs touch no repo state.
"""
import asyncio
import socket
import sqlite3

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.system import shutdown as shutdown_endpoint
from app.config import settings
from app.lib import server_lifecycle as lifecycle
from app.main import app
from app.vectorstore.config import VectorStoreConfig


def _listener():
    """A real listening socket — what "port already occupied" looks like."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    return srv, srv.getsockname()[1]


# ── port preflight ────────────────────────────────────────────────────────

def test_port_is_free_detects_a_live_listener():
    srv, port = _listener()
    try:
        assert lifecycle.port_is_free("127.0.0.1", port) is False
    finally:
        srv.close()
    assert lifecycle.port_is_free("127.0.0.1", port) is True


def test_resolve_port_moves_past_an_occupied_port():
    srv, port = _listener()
    try:
        picked = lifecycle.resolve_port("127.0.0.1", port, limit=5)
        assert picked is not None and picked != port
        assert lifecycle.port_is_free("127.0.0.1", picked)
    finally:
        srv.close()


def test_resolve_port_returns_none_rather_than_guessing():
    srv, port = _listener()
    try:
        # limit=0 -> only the preferred port is considered.
        assert lifecycle.resolve_port("127.0.0.1", port, limit=0) is None
    finally:
        srv.close()


# ── state file (how the launcher finds a backend it already started) ──────

def test_state_file_roundtrip_and_pid_guard(tmp_path):
    lifecycle.write_state(tmp_path, pid=1234, port=8123, app="SovereignAI Edge")
    assert lifecycle.read_state(tmp_path)["port"] == 8123
    lifecycle.clear_state(tmp_path, 9999)  # another process must not remove it
    assert lifecycle.read_state(tmp_path) is not None
    lifecycle.clear_state(tmp_path, 1234)
    assert lifecycle.read_state(tmp_path) is None


def test_state_file_tolerates_a_corrupt_file(tmp_path):
    (tmp_path / lifecycle.STATE_FILENAME).write_text("{not json", encoding="utf-8")
    assert lifecycle.read_state(tmp_path) is None


# ── identity + shutdown endpoint ──────────────────────────────────────────

def test_health_advertises_identity_for_the_launcher():
    body = TestClient(app).get("/health").json()
    assert body["status"] == "healthy"
    assert body["name"] == "SovereignAI Edge"  # what electron/runtime.js matches
    assert isinstance(body["pid"], int)


class _Request:
    def __init__(self, host):
        self.client = type("C", (), {"host": host})()


async def test_shutdown_endpoint_handles_loopback_and_refuses_others():
    lifecycle._exit_requested.clear()
    try:
        result = await shutdown_endpoint(_Request("127.0.0.1"))
        assert result["status"] == "shutting down"
        assert lifecycle.shutdown_requested() is True

        lifecycle._exit_requested.clear()
        with pytest.raises(HTTPException) as exc:
            await shutdown_endpoint(_Request("192.168.1.50"))
        assert exc.value.status_code == 403
        assert lifecycle.shutdown_requested() is False
    finally:
        lifecycle._exit_requested.clear()


# ── lifespan ──────────────────────────────────────────────────────────────

@pytest.fixture()
def temp_data_root(tmp_path, monkeypatch):
    """Point every writable path at a temp root for the whole lifespan."""
    workspace = tmp_path / "workspace"
    for attr, value in (
        ("workspace_dir", workspace),
        ("models_dir", workspace / "models"),
        ("plugins_dir", workspace / "plugins"),
        ("catalog_dir", workspace / "plugins" / "user" / "models"),
        ("database_path", workspace / "database" / "sovereign.db"),
    ):
        monkeypatch.setattr(settings, attr, value)
    # Captured at import time by the dataclass, so it is patched on the class.
    monkeypatch.setattr(VectorStoreConfig, "index_path", str(workspace / "data" / "vector_index"))
    return workspace


async def test_lifespan_closes_every_connection_and_background_task(temp_data_root):
    from app.websocket import metrics

    async with app.router.lifespan_context(app):
        manager = app.state.model_manager
        settings_service = app.state.settings_service
        cloud = app.state.cloud_provider_registry
        db = app.state.db

        # The WS poller only starts when a client connects; start it here so the
        # shutdown path for it is exercised too.
        await metrics._ensure_gpu_cache()
        assert metrics._gpu_cache_started is True

    # aiosqlite runs its own thread: left open it wakes up after the loop is
    # gone ("RuntimeError: Event loop is closed").
    assert manager.registry._db is None
    scan = getattr(manager, "_scan_task", None)
    assert scan is None or scan.done()
    # The two settings-DB sqlite3 connections.
    assert settings_service.db._conn is None
    assert cloud._conn is None
    # The shared connection pool.
    assert db.pool._all_conns == []
    # Fire-and-forget tasks must be gone, not merely cancelled.
    assert metrics._gpu_cache_task is None
    assert [t for t in asyncio.all_tasks() if t is not asyncio.current_task()] == []


async def test_two_start_stop_cycles_leave_clean_databases(temp_data_root):
    for _ in range(2):
        async with app.router.lifespan_context(app):
            assert app.state.settings_service.get_general()  # readable while up
            assert app.state.db.get_stats()["models_count"] >= 0

    for db_file in ("sovereign.db", "sovereign_settings.db"):
        path = temp_data_root / "database" / db_file
        assert path.exists(), f"{db_file} was created"
        conn = sqlite3.connect(path)
        try:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        finally:
            conn.close()
        # A clean close leaves no rollback journal behind (journal_mode=DELETE).
        assert not path.with_name(path.name + "-journal").exists()

    # Every startup recorded its audit row: the DB was really written, twice.
    conn = sqlite3.connect(temp_data_root / "database" / "sovereign_settings.db")
    try:
        rows = conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
    finally:
        conn.close()
    assert rows >= 6
