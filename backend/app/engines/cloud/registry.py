"""Cloud provider registry — CRUD + encrypted API key storage.

Stores providers in the ``cloud_providers`` table of ``sovereign_settings.db``
(same file as settings/agents; separate table). API keys are Fernet-encrypted
at rest with the machine key (same as model encryption, app/security/
encryption.py) — callers only ever see a masked preview via list_providers();
get_provider() decrypts for server-side use and must never be returned to
clients.
"""

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.config import settings
from app.security.encryption import ModelEncryption


class CloudProviderRegistry:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(settings.workspace_dir / "database" / "sovereign_settings.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._encryption = ModelEncryption()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def _init_db(self):
        conn = self._get_connection()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS cloud_providers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                provider_type TEXT NOT NULL,
                api_key_encrypted TEXT,
                base_url TEXT,
                is_enabled INTEGER DEFAULT 1,
                rate_limit_rpm INTEGER DEFAULT 60,
                created_at TEXT,
                updated_at TEXT
            );
        """)
        conn.commit()

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ── key helpers ──

    def _encrypt(self, api_key: str) -> str:
        return self._encryption.fernet.encrypt(api_key.encode()).decode()

    def _decrypt(self, encrypted: str) -> str:
        return self._encryption.fernet.decrypt(encrypted.encode()).decode()

    @staticmethod
    def _mask(api_key: str) -> str:
        if len(api_key) <= 8:
            return "****"
        return f"{api_key[:4]}…{api_key[-4:]}"

    def _row_to_dict(self, row: sqlite3.Row, with_key: bool) -> dict:
        out = {
            "id": row["id"],
            "name": row["name"],
            "provider_type": row["provider_type"],
            "base_url": row["base_url"],
            "is_enabled": bool(row["is_enabled"]),
            "rate_limit_rpm": row["rate_limit_rpm"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        encrypted = row["api_key_encrypted"]
        if with_key:
            out["api_key"] = self._decrypt(encrypted) if encrypted else ""
        else:
            out["api_key_masked"] = self._mask(self._decrypt(encrypted)) if encrypted else ""
        return out

    # ── CRUD ──

    def add_provider(
        self,
        name: str,
        provider_type: str,
        api_key: str = "",
        base_url: Optional[str] = None,
        is_enabled: bool = True,
        rate_limit_rpm: int = 60,
    ) -> dict:
        provider_id = f"prov_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_connection()
        conn.execute(
            """INSERT INTO cloud_providers
               (id, name, provider_type, api_key_encrypted, base_url, is_enabled, rate_limit_rpm, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                provider_id, name, provider_type,
                self._encrypt(api_key) if api_key else None,
                base_url or None,
                int(bool(is_enabled)), rate_limit_rpm, now, now,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM cloud_providers WHERE id = ?", (provider_id,)
        ).fetchone()
        return self._row_to_dict(row, with_key=False)

    def update_provider(self, provider_id: str, updates: dict) -> Optional[dict]:
        conn = self._get_connection()
        row = conn.execute("SELECT * FROM cloud_providers WHERE id = ?", (provider_id,)).fetchone()
        if row is None:
            return None
        current = dict(row)
        if "name" in updates and updates["name"] is not None:
            current["name"] = updates["name"]
        if "base_url" in updates:
            current["base_url"] = updates["base_url"] or None
        if "is_enabled" in updates and updates["is_enabled"] is not None:
            current["is_enabled"] = int(bool(updates["is_enabled"]))
        if "rate_limit_rpm" in updates and updates["rate_limit_rpm"] is not None:
            current["rate_limit_rpm"] = int(updates["rate_limit_rpm"])
        if updates.get("api_key"):
            current["api_key_encrypted"] = self._encrypt(updates["api_key"])
        conn.execute(
            """UPDATE cloud_providers
               SET name=?, provider_type=?, api_key_encrypted=?, base_url=?,
                   is_enabled=?, rate_limit_rpm=?, updated_at=?
               WHERE id=?""",
            (
                current["name"], current["provider_type"], current["api_key_encrypted"],
                current["base_url"], current["is_enabled"], current["rate_limit_rpm"],
                datetime.now(timezone.utc).isoformat(), provider_id,
            ),
        )
        conn.commit()
        return self.get_provider(provider_id)

    def delete_provider(self, provider_id: str) -> bool:
        conn = self._get_connection()
        cursor = conn.execute("DELETE FROM cloud_providers WHERE id = ?", (provider_id,))
        conn.commit()
        return cursor.rowcount > 0

    def get_provider(self, provider_id: str) -> Optional[dict]:
        """Full provider incl. decrypted api_key — server-side use only."""
        row = self._get_connection().execute(
            "SELECT * FROM cloud_providers WHERE id = ?", (provider_id,)
        ).fetchone()
        return self._row_to_dict(row, with_key=True) if row else None

    def list_providers(self) -> list[dict]:
        """All providers with masked keys — safe to return to clients."""
        rows = self._get_connection().execute(
            "SELECT * FROM cloud_providers ORDER BY name"
        ).fetchall()
        return [self._row_to_dict(r, with_key=False) for r in rows]

    def get_enabled_providers(self) -> list[dict]:
        """Enabled providers with decrypted keys — for server-side fetches."""
        rows = self._get_connection().execute(
            "SELECT * FROM cloud_providers WHERE is_enabled = 1 ORDER BY name"
        ).fetchall()
        return [self._row_to_dict(r, with_key=True) for r in rows]