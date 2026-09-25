"""Regression tests for the inference gate, audit facade and download guard.

Covers three fixes:

1. ``security/audit.py`` used to INSERT into an ``audit_log.details`` column
   that does not exist, so every call raised. It now delegates to
   ``AuditTable``, and these tests pin the write to the real schema.
2. ``core/scheduler.py`` replaced a 100 Hz ``sleep(0.01)`` poll loop with a
   semaphore gate; the gate must actually serialize and must release on error.
3. ``services/downloader.py`` rejected unsafe filenames after a path-traversal
   hole.
"""

import asyncio
from types import SimpleNamespace

import pytest

from app.core.scheduler import InferenceScheduler
from app.database.audit_table import AuditTable
from app.database.connection import ConnectionPool
from app.security.audit import AuditLogger
from app.services.downloader import _safe_filename

# Verbatim from database/migrations.py version 2 — the real audit_log schema.
# Note there is no `details` column; that mismatch was the bug.
_AUDIT_SCHEMA = """
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (datetime('now')),
    event_type TEXT NOT NULL,
    severity TEXT DEFAULT 'info',
    source TEXT DEFAULT '',
    message TEXT DEFAULT '',
    metadata_json TEXT
)
"""


@pytest.fixture
def audit_table(tmp_path):
    pool = ConnectionPool(db_path=str(tmp_path / "sovereign.db"))
    pool.execute(_AUDIT_SCHEMA)
    pool.commit()
    yield pool, AuditTable(pool)
    pool.close_all()


async def test_audit_writes_through_canonical_schema(audit_table):
    """The audit row must land, with details stored as metadata_json."""
    pool, table = audit_table
    logger = AuditLogger()
    logger.bind(SimpleNamespace(audit=table))

    await logger.log(
        event_type="auth_rejected",
        details={"path": "/v1/chat/completions"},
        severity=AuditLogger.SEVERITY_WARNING,
        message="Rejected POST /v1/chat/completions",
        source="auth_middleware",
    )

    rows = pool.execute("SELECT * FROM audit_log").fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert row["event_type"] == "auth_rejected"
    assert row["severity"] == "warning"
    assert row["source"] == "auth_middleware"
    assert row["message"] == "Rejected POST /v1/chat/completions"
    assert '"path"' in row["metadata_json"]


async def test_audit_schema_has_no_details_column(audit_table):
    """Guard the regression directly: the column the old code wrote never existed."""
    pool, _ = audit_table
    cols = {r[1] for r in pool.execute("PRAGMA table_info(audit_log)").fetchall()}
    assert "details" not in cols
    assert {"event_type", "severity", "source", "message", "metadata_json"} <= cols


async def test_audit_unbound_is_noop_not_error():
    """Logging before bind() must not raise — audit is never fatal."""
    logger = AuditLogger()
    assert not logger.bound
    await logger.log(event_type="anything", details={"a": 1})
    assert await logger.get_logs() == []


async def test_scheduler_serializes_overlapping_calls():
    """Two holders must never overlap, and the second must queue."""
    sched = InferenceScheduler()
    overlaps = []
    inside = 0

    async def worker():
        nonlocal inside
        async with sched.slot():
            inside += 1
            overlaps.append(inside)
            await asyncio.sleep(0.05)
            inside -= 1

    await asyncio.gather(worker(), worker(), worker())
    assert max(overlaps) == 1, "inference gate admitted concurrent holders"
    assert sched.get_active_count() == 0
    assert sched.get_queue_size() == 0


async def test_scheduler_releases_slot_on_exception():
    """A raising engine must not wedge the gate forever."""
    sched = InferenceScheduler()

    with pytest.raises(RuntimeError):
        async with sched.slot():
            raise RuntimeError("engine blew up")

    assert sched.get_active_count() == 0
    async with sched.slot():
        assert sched.get_active_count() == 1


def test_scheduler_rejects_bad_concurrency():
    with pytest.raises(ValueError):
        InferenceScheduler(max_concurrent=0)


@pytest.mark.parametrize(
    "bad",
    ["../../.env", "..\\..\\secrets", "/etc/passwd", "C:\\Windows\\system32\\x", "", "   ", "a/b"],
)
def test_download_filename_rejects_traversal(bad):
    with pytest.raises(ValueError):
        _safe_filename(bad)


@pytest.mark.parametrize("good", ["model.gguf", "Qwen2.5-0.5B-Instruct.Q4_K_M.gguf", "a b c.bin"])
def test_download_filename_allows_bare_names(good):
    assert _safe_filename(good) == good
