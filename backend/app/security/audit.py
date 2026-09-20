"""Audit Logging"""
import asyncio
from datetime import datetime
from typing import Optional
import json

import sqlite3
from app.config import settings


class AuditLogger:
    """Log security-relevant events"""
    
    SEVERITY_INFO = "info"
    SEVERITY_WARNING = "warning"
    SEVERITY_ERROR = "error"
    SEVERITY_CRITICAL = "critical"
    
    def __init__(self):
        self._db_path = str(settings.workspace_dir / "database" / "sovereign.db")
    
    def _run_sync(self, fn):
        """Run a synchronous DB call in a thread."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            return fn(conn)
        finally:
            conn.close()
    
    async def log(
        self,
        event_type: str,
        details: Optional[dict] = None,
        severity: str = SEVERITY_INFO
    ):
        """Log audit event"""
        def _write(conn):
            conn.execute(
                """
                INSERT INTO audit_log (timestamp, event_type, details, severity)
                VALUES (?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(),
                    event_type,
                    json.dumps(details) if details else None,
                    severity
                )
            )
            conn.commit()
        await asyncio.to_thread(self._run_sync, _write)
    
    async def get_logs(
        self,
        limit: int = 100,
        severity: Optional[str] = None
    ) -> list:
        """Get audit logs"""
        def _read(conn):
            if severity:
                cursor = conn.execute(
                    """
                    SELECT * FROM audit_log 
                    WHERE severity = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (severity, limit)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM audit_log 
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (limit,)
                )
            return [dict(row) for row in cursor.fetchall()]
        return await asyncio.to_thread(self._run_sync, _read)


# Global instance
audit_logger = AuditLogger()