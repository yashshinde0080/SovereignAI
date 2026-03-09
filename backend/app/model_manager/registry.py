"""
SQLite-based model registry.
Tracks all downloaded models, their status, metadata.
Single source of truth.
"""

import sqlite3
import uuid
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional
from contextlib import contextmanager

from .config import REGISTRY_DB, ModelStatus, ModelTaskType, MODELS_DIR
from .schemas import ModelInfo


class ModelRegistry:
    """
    Thread-safe SQLite registry for model management.
    Tracks downloads, status, metadata, usage statistics.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern - one registry instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._db_path = str(REGISTRY_DB)
        self._local_lock = threading.Lock()
        self._init_db()
    
    @contextmanager
    def _get_conn(self):
        """Thread-safe connection context manager."""
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        """Create tables if they don't exist."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS models (
                    id TEXT PRIMARY KEY,
                    repo_id TEXT NOT NULL,
                    local_name TEXT NOT NULL UNIQUE,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'downloading',
                    size_bytes INTEGER DEFAULT 0,
                    architectures TEXT,
                    revision TEXT,
                    config_json TEXT,
                    trust_remote_code INTEGER DEFAULT 0,
                    local_path TEXT NOT NULL,
                    downloaded_at TEXT NOT NULL,
                    last_loaded_at TEXT,
                    load_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                
                CREATE INDEX IF NOT EXISTS idx_models_repo 
                    ON models(repo_id);
                CREATE INDEX IF NOT EXISTS idx_models_status 
                    ON models(status);
                CREATE INDEX IF NOT EXISTS idx_models_local_name 
                    ON models(local_name);
                
                CREATE TABLE IF NOT EXISTS model_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                    details TEXT,
                    FOREIGN KEY (model_id) REFERENCES models(id)
                );
            """)
    
    def _generate_local_name(self, repo_id: str) -> str:
        """
        Generate Docker-style local name from repo_id.
        'meta-llama/Llama-3-8B' → 'meta-llama--llama-3-8b'
        """
        name = repo_id.lower().replace("/", "--").replace(" ", "-")
        # Remove special chars
        safe = "".join(
            c if c.isalnum() or c in "-_." else "-" 
            for c in name
        )
        return safe
    
    def _format_size(self, size_bytes: int) -> str:
        """Human-readable file size."""
        if size_bytes == 0:
            return "0B"
        units = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)
        while size >= 1024 and i < len(units) - 1:
            size /= 1024
            i += 1
        return f"{size:.1f}{units[i]}"
    
    def register_model(
        self,
        repo_id: str,
        task_type: ModelTaskType,
        revision: Optional[str] = None,
        architectures: Optional[list[str]] = None,
        trust_remote_code: bool = False,
    ) -> str:
        """
        Register a new model in the registry.
        Returns the model ID.
        """
        model_id = str(uuid.uuid4())[:12]
        local_name = self._generate_local_name(repo_id)
        local_path = str(MODELS_DIR / local_name)
        
        with self._local_lock:
            with self._get_conn() as conn:
                # Check if already exists
                existing = conn.execute(
                    "SELECT id FROM models WHERE repo_id = ? AND revision IS ?",
                    (repo_id, revision)
                ).fetchone()
                
                if existing:
                    return existing["id"]
                
                conn.execute("""
                    INSERT INTO models 
                    (id, repo_id, local_name, task_type, status, 
                     architectures, revision, trust_remote_code,
                     local_path, downloaded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    model_id,
                    repo_id,
                    local_name,
                    task_type.value,
                    ModelStatus.DOWNLOADING.value,
                    json.dumps(architectures) if architectures else None,
                    revision,
                    int(trust_remote_code),
                    local_path,
                    datetime.utcnow().isoformat(),
                ))
                
                self._log_usage(conn, model_id, "registered")
        
        return model_id
    
    def update_status(
        self, 
        model_id: str, 
        status: ModelStatus,
        error_message: Optional[str] = None
    ):
        """Update model status."""
        with self._local_lock:
            with self._get_conn() as conn:
                conn.execute("""
                    UPDATE models 
                    SET status = ?, error_message = ?, 
                        updated_at = datetime('now')
                    WHERE id = ?
                """, (status.value, error_message, model_id))
                self._log_usage(conn, model_id, f"status:{status.value}")
    
    def update_size(self, model_id: str, size_bytes: int):
        """Update model size after download."""
        with self._local_lock:
            with self._get_conn() as conn:
                conn.execute("""
                    UPDATE models 
                    SET size_bytes = ?, updated_at = datetime('now')
                    WHERE id = ?
                """, (size_bytes, model_id))
    
    def update_config(self, model_id: str, config: dict):
        """Store model config.json data."""
        with self._local_lock:
            with self._get_conn() as conn:
                conn.execute("""
                    UPDATE models 
                    SET config_json = ?, updated_at = datetime('now')
                    WHERE id = ?
                """, (json.dumps(config), model_id))
    
    def mark_loaded(self, model_id: str):
        """Mark model as loaded, increment load count."""
        with self._local_lock:
            with self._get_conn() as conn:
                conn.execute("""
                    UPDATE models 
                    SET status = ?, last_loaded_at = datetime('now'),
                        load_count = load_count + 1,
                        updated_at = datetime('now')
                    WHERE id = ?
                """, (ModelStatus.LOADED.value, model_id))
                
                # Ensure no other model is marked loaded
                conn.execute("""
                    UPDATE models 
                    SET status = ?
                    WHERE id != ? AND status = ?
                """, (
                    ModelStatus.READY.value, 
                    model_id, 
                    ModelStatus.LOADED.value
                ))
                
                self._log_usage(conn, model_id, "loaded")
    
    def mark_unloaded(self, model_id: str):
        """Mark model as ready (unloaded)."""
        with self._local_lock:
            with self._get_conn() as conn:
                conn.execute("""
                    UPDATE models 
                    SET status = ?, updated_at = datetime('now')
                    WHERE id = ? AND status = ?
                """, (
                    ModelStatus.READY.value, 
                    model_id, 
                    ModelStatus.LOADED.value
                ))
                self._log_usage(conn, model_id, "unloaded")
    
    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """Get model by ID."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM models WHERE id = ?", (model_id,)
            ).fetchone()
            
            if not row:
                return None
            return self._row_to_info(row)
    
    def get_model_by_name(self, local_name: str) -> Optional[ModelInfo]:
        """Get model by local name."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM models WHERE local_name = ?", 
                (local_name,)
            ).fetchone()
            
            if not row:
                return None
            return self._row_to_info(row)
    
    def get_model_by_repo(
        self, 
        repo_id: str, 
        revision: Optional[str] = None
    ) -> Optional[ModelInfo]:
        """Get model by repo ID."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM models WHERE repo_id = ? AND revision IS ?",
                (repo_id, revision)
            ).fetchone()
            
            if not row:
                return None
            return self._row_to_info(row)
    
    def list_models(
        self, 
        status: Optional[ModelStatus] = None
    ) -> list[ModelInfo]:
        """List all models, optionally filtered by status."""
        with self._get_conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM models WHERE status = ? "
                    "ORDER BY downloaded_at DESC",
                    (status.value,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM models ORDER BY downloaded_at DESC"
                ).fetchall()
            
            return [self._row_to_info(r) for r in rows]
    
    def get_loaded_model(self) -> Optional[ModelInfo]:
        """Get currently loaded model (only one at a time)."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM models WHERE status = ?",
                (ModelStatus.LOADED.value,)
            ).fetchone()
            
            if not row:
                return None
            return self._row_to_info(row)
    
    def remove_model(self, model_id: str) -> bool:
        """Remove model from registry."""
        with self._local_lock:
            with self._get_conn() as conn:
                model = conn.execute(
                    "SELECT * FROM models WHERE id = ?", (model_id,)
                ).fetchone()
                
                if not model:
                    return False
                
                if model["status"] == ModelStatus.LOADED.value:
                    raise RuntimeError(
                        "Cannot remove loaded model. Unload first."
                    )
                
                conn.execute(
                    "DELETE FROM model_usage WHERE model_id = ?", 
                    (model_id,)
                )
                conn.execute(
                    "DELETE FROM models WHERE id = ?", 
                    (model_id,)
                )
                return True
    
    def get_total_storage_used(self) -> int:
        """Total bytes used by all models."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(size_bytes), 0) as total "
                "FROM models WHERE status != ?",
                (ModelStatus.FAILED.value,)
            ).fetchone()
            return row["total"]
    
    def get_model_config(self, model_id: str) -> Optional[dict]:
        """Get stored config.json for a model."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT config_json FROM models WHERE id = ?",
                (model_id,)
            ).fetchone()
            
            if row and row["config_json"]:
                return json.loads(row["config_json"])
            return None
    
    def _row_to_info(self, row: sqlite3.Row) -> ModelInfo:
        """Convert database row to ModelInfo schema."""
        return ModelInfo(
            id=row["id"],
            repo_id=row["repo_id"],
            local_name=row["local_name"],
            task_type=row["task_type"],
            status=row["status"],
            size_bytes=row["size_bytes"],
            size_human=self._format_size(row["size_bytes"]),
            architectures=row["architectures"],
            revision=row["revision"],
            downloaded_at=row["downloaded_at"],
            last_loaded_at=row["last_loaded_at"],
            load_count=row["load_count"],
            local_path=row["local_path"],
        )
    
    def _log_usage(
        self, 
        conn: sqlite3.Connection, 
        model_id: str, 
        action: str,
        details: Optional[str] = None
    ):
        """Log model usage event."""
        conn.execute(
            "INSERT INTO model_usage (model_id, action, details) "
            "VALUES (?, ?, ?)",
            (model_id, action, details)
        )