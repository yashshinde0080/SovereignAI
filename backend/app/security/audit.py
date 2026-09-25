"""Audit logging facade.

Security-relevant events land in ``sovereign.db:audit_log``. That table has
exactly one writer — ``app.database.audit_table.AuditTable`` — and this module
is a thin async wrapper over it so request handlers can await without blocking
the event loop.

The table schema is ``(id, timestamp, event_type, severity, source, message,
metadata_json)``. This module previously carried its own INSERT naming a
``details`` column that does not exist, so every call would have raised
``sqlite3.OperationalError: no such column: details``. Delegating keeps the
schema in one place instead of two.

Call ``bind(db)`` once at startup with the ``DatabaseManager``. Unbound (tests,
imports) logging is a no-op rather than an error: audit must never be the
reason a request fails.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("sovereign.security.audit")


class AuditLogger:
    """Async facade over ``DatabaseManager.audit`` (``AuditTable``)."""

    SEVERITY_INFO = "info"
    SEVERITY_WARNING = "warning"
    SEVERITY_ERROR = "error"
    SEVERITY_CRITICAL = "critical"

    def __init__(self):
        self._table = None

    def bind(self, db) -> None:
        """Attach the canonical audit writer. Idempotent."""
        self._table = getattr(db, "audit", None)

    @property
    def bound(self) -> bool:
        return self._table is not None

    async def log(
        self,
        event_type: str,
        details: Optional[Dict[str, Any]] = None,
        severity: str = SEVERITY_INFO,
        message: Optional[str] = None,
        source: str = "security",
    ) -> None:
        """Record an audit event. Never raises.

        ``details`` is stored as ``metadata_json``; ``message`` defaults to a
        short summary of the event so the column is never blank.
        """
        if self._table is None:
            logger.debug("audit logger unbound; dropping %s event", event_type)
            return

        text = message or (f"{event_type}: {details}" if details else event_type)
        try:
            await asyncio.to_thread(
                self._table.log,
                event_type=event_type,
                message=text,
                severity=severity,
                source=source,
                metadata=details,
            )
        except Exception as e:  # pragma: no cover - AuditTable already swallows
            logger.error("Audit log write failed: %s", e)

    async def get_logs(
        self,
        limit: int = 100,
        severity: Optional[str] = None,
    ) -> List[Any]:
        """Most recent audit records, optionally filtered by severity."""
        if self._table is None:
            return []
        if severity:
            return await asyncio.to_thread(self._table.get_by_severity, severity, limit)
        return await asyncio.to_thread(self._table.get_recent, limit)


# Global instance — bind() at startup, use anywhere.
audit_logger = AuditLogger()
