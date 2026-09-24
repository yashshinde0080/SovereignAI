"""
Regression test for the models-table conflict.

History: app/services/registry.py used to DROP the `models` table whenever it
saw the migration schema (size_label column) — destroying registered model
rows and breaking DatabaseManager's ModelsTable stats queries.

Covers:
- legacy (migration-schema) rows are migrated in place, not dropped
- migration is idempotent (re-init keeps rows, legacy table retired)
- ModelsTable.count()/get_total_storage_bytes() degrade to 0 on the
  registry schema instead of raising OperationalError
"""

import asyncio
import sqlite3
from pathlib import Path

import pytest

from app.database.connection import ConnectionPool
from app.database.models_table import ModelsTable
from app.services.registry import ModelRegistry


LEGACY_TABLE_SQL = """
CREATE TABLE models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    family TEXT NOT NULL,
    size_label TEXT NOT NULL,
    quant TEXT NOT NULL,
    file_path TEXT NOT NULL UNIQUE,
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    checksum_sha256 TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'local',
    repo_id TEXT,
    status TEXT NOT NULL DEFAULT 'ready',
    engines_supported TEXT NOT NULL DEFAULT 'fullram,layerstream',
    context_length INTEGER DEFAULT 4096,
    hidden_size INTEGER DEFAULT 4096,
    num_layers INTEGER DEFAULT 32,
    ram_required_mb INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    last_used_at TEXT,
    use_count INTEGER DEFAULT 0
)
"""


@pytest.fixture
def legacy_db(tmp_path):
    """SQLite DB with the migration-schema models table and one row."""
    db_path = tmp_path / "test.db"
    pool = ConnectionPool(db_path=str(db_path), journal_mode="DELETE",
                          busy_timeout=1000, cache_size=-2000)
    pool.execute(LEGACY_TABLE_SQL)
    pool.execute(
        "INSERT INTO models (name, family, size_label, quant, file_path,"
        " file_size_bytes, checksum_sha256)"
        " VALUES ('qwen2-0.5b', 'qwen2', '0.5B', 'int4', '/models/qwen2-0.5b',"
        " 322122547, 'abc123')"
    )
    pool.commit()
    yield db_path
    pool.close_all()


def _cols(db_path):
    con = sqlite3.connect(db_path)
    try:
        return [r[1] for r in con.execute("PRAGMA table_info(models)")]
    finally:
        con.close()


async def test_legacy_models_table_migrated_not_dropped(legacy_db):
    registry = ModelRegistry(legacy_db)
    try:
        await registry.initialize()

        cols = _cols(legacy_db)
        assert "path" in cols and "checksum" in cols  # registry schema
        assert "size_label" not in cols               # legacy schema gone

        # Legacy row preserved through the migration
        rows = await registry.list_models()
        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == "qwen2-0.5b"
        assert row["quant"] == "int4"
        assert row["path"] == "/models/qwen2-0.5b"
        assert row["checksum"] == "abc123"
        assert row["downloaded"] is True  # status was 'ready'
    finally:
        await registry.close()


async def test_migration_idempotent(legacy_db):
    registry = ModelRegistry(legacy_db)
    try:
        await registry.initialize()
        await registry.initialize()  # re-run must not duplicate or crash

        rows = await registry.list_models()
        assert len(rows) == 1

        # Legacy backup table retired after successful copy
        con = sqlite3.connect(legacy_db)
        try:
            leftover = con.execute(
                "SELECT name FROM sqlite_master WHERE name='models_legacy_v0'"
            ).fetchone()
        finally:
            con.close()
        assert leftover is None
    finally:
        await registry.close()


async def test_modelstable_degrades_on_registry_schema(legacy_db):
    """ModelsTable stats must not crash when the registry owns the schema."""
    registry = ModelRegistry(legacy_db)
    try:
        await registry.initialize()
    finally:
        await registry.close()

    pool = ConnectionPool(db_path=str(legacy_db), journal_mode="DELETE",
                          busy_timeout=1000, cache_size=-2000)
    try:
        models = ModelsTable(pool)
        assert models.count() == 0
        assert models.get_total_storage_bytes() == 0
    finally:
        pool.close_all()
