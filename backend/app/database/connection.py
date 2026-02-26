"""Database Connection Management"""
import aiosqlite
from pathlib import Path
from typing import Optional

from app.config import settings


_db_connection: Optional[aiosqlite.Connection] = None


async def get_database() -> aiosqlite.Connection:
    """Get database connection"""
    global _db_connection
    
    if _db_connection is None:
        _db_connection = await aiosqlite.connect(settings.database_path)
        _db_connection.row_factory = aiosqlite.Row
    
    return _db_connection


async def init_database():
    """Initialize database with schema"""
    db = await get_database()
    
    # Create tables
    await db.executescript("""
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
        );
        
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            model_id TEXT,
            mode TEXT,
            started_at TEXT,
            ended_at TEXT,
            tokens_generated INTEGER DEFAULT 0
        );
        
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            details TEXT,
            severity TEXT DEFAULT 'info'
        );
        
        CREATE TABLE IF NOT EXISTS hardware_profiles (
            id TEXT PRIMARY KEY,
            cpu_name TEXT,
            cpu_cores INTEGER,
            ram_gb REAL,
            gpu_name TEXT,
            gpu_vram_gb REAL,
            disk_type TEXT,
            created_at TEXT
        );
    """)
    
    await db.commit()


async def close_database():
    """Close database connection"""
    global _db_connection
    
    if _db_connection:
        await _db_connection.close()
        _db_connection = None