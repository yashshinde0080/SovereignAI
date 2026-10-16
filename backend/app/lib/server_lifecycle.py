"""Single-instance startup for the backend: port preflight + a state file.

Both entry points use this (``backend/main.py`` in dev, ``backend/backend_entry.py``
in the packaged build), and the Electron shell reads the same JSON before it
spawns anything — so at most one backend per app instance ever runs.

Why a state file and not a process scan: on Windows a frozen backend survives a
force-killed parent, so "is 8000 busy?" is not enough to tell a stale
SovereignAI apart from an unrelated app. The file says which pid/port we last
started; the caller still has to prove health + identity over HTTP before it
reuses anything, and nothing here ever terminates another process.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

STATE_FILENAME = "backend.json"
DEFAULT_PORT = 8000
PORT_SCAN_LIMIT = 20

# Set by the loopback-only /v1/system/shutdown endpoint; the server entry point
# polls it and stops uvicorn the same way Ctrl+C would, so the lifespan
# teardown (DB commits, connection closes, background task cancels) really runs.
_exit_requested = threading.Event()


def request_shutdown() -> None:
    """Ask the running server to shut down gracefully."""
    _exit_requested.set()


def shutdown_requested() -> bool:
    return _exit_requested.is_set()


def port_is_free(host: str, port: int) -> bool:
    """True when a server could bind ``host:port`` right now.

    Binding is the test, not ``connect_ex``: on Windows a live listener makes
    bind fail with WSAEADDRINUSE even when the overlap is 0.0.0.0 vs 127.0.0.1,
    while connect_ex reports ECONNREFUSED for a socket that is listening but has
    not reached ``accept()`` yet.
    """
    if not 0 < int(port) < 65536:
        return False
    try:
        family, socktype, proto, _, addr = socket.getaddrinfo(
            host, int(port), type=socket.SOCK_STREAM
        )[0]
    except socket.gaierror:
        return False
    try:
        with socket.socket(family, socktype, proto) as sock:
            sock.bind(addr)
    except OSError:
        return False
    return True


def resolve_port(host: str, preferred: int, limit: int = PORT_SCAN_LIMIT) -> Optional[int]:
    """The preferred port when free, else the next free one, else None.

    Never inspects or kills whatever holds a port: it may be another
    application, or a SovereignAI the user is already using.
    """
    preferred = int(preferred)
    for port in [preferred] + [preferred + i for i in range(1, max(0, limit) + 1)]:
        if 0 < port < 65536 and port_is_free(host, port):
            return port
    return None


# ── state file ────────────────────────────────────────────────────────────

def state_path(workspace_dir) -> Path:
    return Path(workspace_dir) / STATE_FILENAME


def read_state(workspace_dir) -> Optional[dict]:
    """Last recorded backend address, or None (missing/corrupt = unknown)."""
    try:
        data = json.loads(state_path(workspace_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def write_state(workspace_dir, **fields) -> None:
    """Record where this backend listens. Best-effort: never blocks startup."""
    path = state_path(workspace_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(fields, indent=2), encoding="utf-8")
        os.replace(tmp, path)  # atomic: a reader never sees a half-written file
    except OSError as exc:
        logger.warning("Could not write backend state file %s: %s", path, exc)


def clear_state(workspace_dir, pid: Optional[int] = None) -> None:
    """Remove the state file — but only if this process wrote it."""
    path = state_path(workspace_dir)
    try:
        current = read_state(workspace_dir)
        if pid is not None and current and current.get("pid") not in (None, pid):
            return
        path.unlink()
    except OSError:
        pass
