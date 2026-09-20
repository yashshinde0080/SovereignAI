"""Model Registry Service"""
import aiosqlite
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class ModelRegistry:
    """SQLite-based model registry"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db: Optional[aiosqlite.Connection] = None

    async def _conn(self) -> aiosqlite.Connection:
        """Reuse a single aiosqlite connection across all operations."""
        if self._db is None:
            self._db = await aiosqlite.connect(self.db_path)
            self._db.row_factory = aiosqlite.Row
        return self._db

    async def close(self):
        """Close the persistent connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def initialize(self):
        """Initialize database"""
        db = await self._conn()
        # Drop corrupted models table if created by manager.py schemas
        try:
            cursor = await db.execute("PRAGMA table_info(models)")
            cols = [row[1] for row in await cursor.fetchall()]
            if 'size_label' in cols:
                await db.execute("DROP TABLE models")
        except Exception:
            pass
            
        await db.execute("""
            CREATE TABLE IF NOT EXISTS models (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                family TEXT,
                parameters TEXT,
                quant TEXT,
                size_gb REAL,
                path TEXT,
                checksum TEXT,
                downloaded INTEGER DEFAULT 1,
                modes_supported TEXT,
                created_at TEXT
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                model_id TEXT,
                mode TEXT,
                started_at TEXT,
                ended_at TEXT,
                tokens_generated INTEGER DEFAULT 0,
                FOREIGN KEY (model_id) REFERENCES models(id)
            )
        """)
        
        # Migrate older schema versions
        columns = [
            ("parameters", "TEXT"),
            ("modes_supported", "TEXT"),
            ("size_gb", "REAL"),
            ("quant", "TEXT"),
            ("family", "TEXT"),
            ("path", "TEXT"),
            ("checksum", "TEXT"),
            ("downloaded", "INTEGER DEFAULT 1"),
            ("created_at", "TEXT")
        ]
        for col, dtype in columns:
            try:
                await db.execute(f"ALTER TABLE models ADD COLUMN {col} {dtype}")
            except Exception:
                pass
        
        await db.commit()
    
    async def add_model(self, metadata: Dict[str, Any]):
        """Add model to registry"""
        db = await self._conn()
        await db.execute("""
            INSERT OR REPLACE INTO models 
            (id, name, family, parameters, quant, size_gb, path, checksum, downloaded, modes_supported, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metadata["id"],
            metadata["name"],
            metadata.get("family"),
            metadata.get("parameters"),
            metadata.get("quant"),
            metadata.get("size_gb"),
            metadata.get("path"),
            metadata.get("checksum"),
            1 if metadata.get("downloaded", True) else 0,
            ",".join(metadata.get("modes_supported", [])),
            metadata.get("created_at", datetime.now().isoformat())
        ))
        await db.commit()

    async def bulk_upsert(self, models: List[Dict[str, Any]]):
        """Insert or replace multiple models in a single transaction."""
        if not models:
            return
        db = await self._conn()
        await db.executemany("""
            INSERT OR REPLACE INTO models
            (id, name, family, parameters, quant, size_gb, path, checksum, downloaded, modes_supported, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                m["id"],
                m["name"],
                m.get("family"),
                m.get("parameters"),
                m.get("quant"),
                m.get("size_gb"),
                m.get("path"),
                m.get("checksum"),
                1 if m.get("downloaded", True) else 0,
                ",".join(m.get("modes_supported", [])),
                m.get("created_at", datetime.now().isoformat())
            )
            for m in models
        ])
        await db.commit()
    
    async def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get model by ID"""
        db = await self._conn()
        async with db.execute(
            "SELECT * FROM models WHERE id = ?",
            (model_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_dict(row)
        return None
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """List all models"""
        db = await self._conn()
        async with db.execute("SELECT * FROM models ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]
    
    async def delete_model(self, model_id: str):
        """Delete model from registry"""
        db = await self._conn()
        await db.execute("DELETE FROM models WHERE id = ?", (model_id,))
        await db.commit()
    
    def _row_to_dict(self, row: aiosqlite.Row) -> Dict[str, Any]:
        """Convert row to dictionary"""
        return {
            "id": row["id"],
            "name": row["name"],
            "family": row["family"],
            "parameters": row["parameters"],
            "quant": row["quant"],
            "size_gb": row["size_gb"],
            "path": row["path"],
            "checksum": row["checksum"],
            "downloaded": bool(row["downloaded"]),
            "modes_supported": row["modes_supported"].split(",") if row["modes_supported"] else [],
            "created_at": row["created_at"]
        }