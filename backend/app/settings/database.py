import sqlite3
import json
import os
from typing import Optional
from .schemas import FullSettings, AgentConfig
from .defaults import DEFAULT_AGENTS
from app.config import settings


class SettingsDatabase:
    def __init__(self, db_path: Optional[str] = None):
        # Project-relative (portable USB): <project>/workspace/database/sovereign_settings.db
        self.db_path = db_path or str(settings.workspace_dir / "database" / "sovereign_settings.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Reuse a single connection across all operations."""
        if self._conn is None:
            # check_same_thread=False: one shared connection is used from the
            # event loop thread, the hourly retention sweep, and (in tests) the
            # TestClient's worker thread. CPython's sqlite3 is compiled
            # serialized, and no cursor is ever held across calls, so sharing
            # is safe — leaving the default raised ProgrammingError instead.
            # timeout + busy_timeout: the audit write on shutdown can land
            # while a second process is still finishing a write (a stale
            # backend the launcher has not adopted yet). Without the wait it
            # fails immediately with "database is locked".
            self._conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=DELETE")
            self._conn.execute("PRAGMA synchronous=FULL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA busy_timeout=10000")
        return self._conn

    def close(self):
        """Close the persistent connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _init_db(self):
        conn = self._get_connection()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS settings (
                section TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                description TEXT DEFAULT '',
                system_instruction TEXT DEFAULT '',
                job_title TEXT DEFAULT '',
                responsibilities TEXT DEFAULT '',
                preferred_model TEXT DEFAULT '',
                welcome_message TEXT DEFAULT '',
                tool_permissions TEXT DEFAULT '[]',
                is_active INTEGER DEFAULT 0,
                icon TEXT DEFAULT 'bot',
                temperature REAL DEFAULT 0.7,
                max_tokens INTEGER DEFAULT 2048,
                enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                section TEXT NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Ensure all sections exist — single batched query instead of 6 separate SELECTs
        defaults = FullSettings()
        all_sections = ["general", "personalization", "data_controls", "security", "parental_controls", "project"]
        placeholders = ','.join('?' * len(all_sections))
        existing = {
            row["section"] for row in
            conn.execute(f"SELECT section FROM settings WHERE section IN ({placeholders})", all_sections).fetchall()
        }
        for section in all_sections:
            if section not in existing:
                data = getattr(defaults, section).model_dump_json()
                conn.execute(
                    "INSERT INTO settings (section, data) VALUES (?, ?)",
                    (section, data)
                )

        # Databases created before the per-agent extras existed need the
        # columns added in place (idempotent, no migration framework here).
        self._migrate_agent_columns(conn)

        # Insert default agents if not exist
        self._seed_default_agents(conn)

        conn.commit()

    # ── Agent row helpers (one serializer/parser for all agent CRUD) ──

    AGENT_COLUMNS = (
        "id", "name", "role", "description", "system_instruction",
        "job_title", "responsibilities", "preferred_model", "welcome_message",
        "tool_permissions", "is_active", "icon", "temperature", "max_tokens",
        "enabled",
    )

    @staticmethod
    def _agent_values(agent: AgentConfig) -> tuple:
        return (
            agent.id, agent.name, agent.role.value, agent.description,
            agent.system_instruction, agent.job_title, agent.responsibilities,
            agent.preferred_model, agent.welcome_message,
            json.dumps(agent.tool_permissions),
            int(agent.is_active), agent.icon,
            agent.temperature, agent.max_tokens, int(agent.enabled),
        )

    @staticmethod
    def _agent_row(row) -> dict:
        """Row -> agent dict. Tolerates pre-migration rows (missing columns)."""
        def col(name, default=""):
            try:
                return row[name]
            except (IndexError, KeyError):
                return default

        try:
            tools = json.loads(col("tool_permissions", "[]") or "[]")
        except (ValueError, TypeError):
            tools = []
        return {
            "id": row["id"],
            "name": row["name"],
            "role": row["role"],
            "description": col("description"),
            "system_instruction": col("system_instruction"),
            "job_title": col("job_title"),
            "responsibilities": col("responsibilities"),
            "preferred_model": col("preferred_model"),
            "welcome_message": col("welcome_message"),
            "tool_permissions": [t for t in tools if isinstance(t, str)],
            "is_active": bool(row["is_active"]),
            "icon": col("icon", "bot"),
            "temperature": row["temperature"],
            "max_tokens": row["max_tokens"],
            "enabled": bool(row["enabled"]),
        }

    def _insert_agent(self, conn, agent: AgentConfig) -> None:
        cols = ", ".join(self.AGENT_COLUMNS)
        marks = ", ".join("?" * len(self.AGENT_COLUMNS))
        conn.execute(
            f"INSERT INTO agents ({cols}) VALUES ({marks})",
            self._agent_values(agent),
        )

    def _migrate_agent_columns(self, conn) -> None:
        have = {row["name"] for row in conn.execute("PRAGMA table_info(agents)")}
        for column, ddl in (
            ("job_title", "TEXT DEFAULT ''"),
            ("responsibilities", "TEXT DEFAULT ''"),
            ("preferred_model", "TEXT DEFAULT ''"),
            ("welcome_message", "TEXT DEFAULT ''"),
            ("tool_permissions", "TEXT DEFAULT '[]'"),
        ):
            if column not in have:
                conn.execute(f"ALTER TABLE agents ADD COLUMN {column} {ddl}")

    def _seed_default_agents(self, conn) -> None:
        """Seed shipped examples once each; a deleted example stays deleted.

        Fresh DB (and Reset All) seeds the whole catalog. On an upgrade only
        examples this install has never recorded are added, tracked by the
        `agent_examples_seeded` settings row.
        """
        present = {row["id"] for row in conn.execute("SELECT id FROM agents")}
        seeded = set(self.get_section("agent_examples_seeded") or [])
        fresh = not present
        for agent in DEFAULT_AGENTS:
            if fresh or (agent.id not in present and agent.id not in seeded):
                self._insert_agent(conn, agent)
        recorded = seeded | {a.id for a in DEFAULT_AGENTS}
        if recorded != seeded:
            # Internal bookkeeping, not a user setting edit — write it without
            # the audit row update_section would add on every fresh install.
            conn.execute(
                """INSERT INTO settings (section, data, updated_at)
                   VALUES (?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(section) DO UPDATE SET data = excluded.data,
                   updated_at = CURRENT_TIMESTAMP""",
                ("agent_examples_seeded", json.dumps(sorted(recorded))),
            )

    # ── Settings CRUD ──

    def get_section(self, section: str) -> Optional[dict]:
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT data FROM settings WHERE section = ?", (section,)
        )
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row["data"])
            except (ValueError, TypeError):
                # Corrupt JSON blob (hand-edit, truncated write): degrade to
                # "missing" so callers fall back to schema defaults, not crash.
                return None
        return None

    def update_section(self, section: str, data: dict) -> bool:
        conn = self._get_connection()
        try:
            json_data = json.dumps(data)
            conn.execute(
                """INSERT INTO settings (section, data, updated_at) 
                   VALUES (?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(section) 
                   DO UPDATE SET data = excluded.data, updated_at = CURRENT_TIMESTAMP""",
                (section, json_data)
            )
            self.log_audit("update", section, json_data)
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False

    def log_audit(self, action: str, section: str, details: str) -> None:
        """Append one audit row. Best-effort: audit failures never block saves."""
        try:
            self._get_connection().execute(
                "INSERT INTO audit_log (action, section, details) VALUES (?, ?, ?)",
                (action, section, details),
            )
            self._get_connection().commit()
        except Exception:
            pass

    def get_all_settings(self) -> dict:
        conn = self._get_connection()
        cursor = conn.execute("SELECT section, data FROM settings")
        result = {}
        for row in cursor.fetchall():
            result[row["section"]] = json.loads(row["data"])
        return result

    def reset_section(self, section: str) -> bool:
        defaults = FullSettings()
        default_data = getattr(defaults, section, None)
        if default_data is None:
            return False
        return self.update_section(section, default_data.model_dump())

    def reset_all(self) -> bool:
        conn = self._get_connection()
        try:
            defaults = FullSettings()
            for section in ["general", "personalization", "data_controls", "security", "parental_controls", "project"]:
                data = getattr(defaults, section).model_dump_json()
                conn.execute(
                    """INSERT INTO settings (section, data, updated_at) 
                       VALUES (?, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT(section) 
                       DO UPDATE SET data = excluded.data, updated_at = CURRENT_TIMESTAMP""",
                    (section, data)
                )


            # Reset agents — deleting then re-seeding relinks every example.
            conn.execute("DELETE FROM agents")
            self._seed_default_agents(conn)

            conn.execute(
                "INSERT INTO audit_log (action, section, details) VALUES (?, ?, ?)",
                ("reset_all", "all", "Full settings reset to defaults")
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False

    # ── Agents CRUD ──

    def get_all_agents(self) -> list[dict]:
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM agents ORDER BY name")
        return [self._agent_row(row) for row in cursor.fetchall()]

    def get_agent(self, agent_id: str) -> Optional[dict]:
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        row = cursor.fetchone()
        return self._agent_row(row) if row else None

    def agent_name_taken(self, name: str, exclude_id: Optional[str] = None) -> bool:
        """Case-insensitive name lookup — the name is the user-facing handle."""
        wanted = (name or "").strip().lower()
        if not wanted:
            return False
        return any(
            a["id"] != exclude_id and a["name"].strip().lower() == wanted
            for a in self.get_all_agents()
        )

    def create_agent(self, agent: AgentConfig) -> bool:
        conn = self._get_connection()
        try:
            self._insert_agent(conn, agent)
            conn.execute(
                "INSERT INTO audit_log (action, section, details) VALUES (?, ?, ?)",
                ("create_agent", "agents", json.dumps({"agent_id": agent.id, "name": agent.name}))
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def update_agent(self, agent_id: str, agent: AgentConfig) -> bool:
        conn = self._get_connection()
        try:
            conn.execute(
                """UPDATE agents SET name=?, role=?, description=?, system_instruction=?,
                   job_title=?, responsibilities=?, preferred_model=?, welcome_message=?,
                   tool_permissions=?, is_active=?, icon=?, temperature=?, max_tokens=?,
                   enabled=?, updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (
                    agent.name, agent.role.value,
                    agent.description, agent.system_instruction,
                    agent.job_title, agent.responsibilities,
                    agent.preferred_model, agent.welcome_message,
                    json.dumps(agent.tool_permissions),
                    int(agent.is_active), agent.icon,
                    agent.temperature, agent.max_tokens,
                    int(agent.enabled), agent_id,
                )
            )
            conn.execute(
                "INSERT INTO audit_log (action, section, details) VALUES (?, ?, ?)",
                ("update_agent", "agents", json.dumps({"agent_id": agent_id}))
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False

    def delete_agent(self, agent_id: str) -> bool:
        conn = self._get_connection()
        try:
            conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
            conn.execute(
                "INSERT INTO audit_log (action, section, details) VALUES (?, ?, ?)",
                ("delete_agent", "agents", json.dumps({"agent_id": agent_id}))
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False

    def set_active_agent(self, agent_id: str) -> bool:
        conn = self._get_connection()
        try:
            conn.execute("UPDATE agents SET is_active = 0")
            conn.execute("UPDATE agents SET is_active = 1 WHERE id = ?", (agent_id,))
            conn.execute(
                "INSERT INTO audit_log (action, section, details) VALUES (?, ?, ?)",
                ("activate_agent", "agents", json.dumps({"agent_id": agent_id}))
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False

    def deactivate_all_agents(self) -> bool:
        conn = self._get_connection()
        try:
            conn.execute("UPDATE agents SET is_active = 0")
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False

    def get_active_agent(self) -> Optional[dict]:
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM agents WHERE is_active = 1 LIMIT 1")
        row = cursor.fetchone()
        if row:
            agent = self._agent_row(row)
            agent["is_active"] = True
            return agent
        return None

    # ── Audit ──

    def get_audit_log(self, limit: int = 100) -> list[dict]:
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]