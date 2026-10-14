"""Auth + request-logging middleware."""
import logging
import secrets
import time
from typing import Optional
from fastapi import Request, HTTPException

logger = logging.getLogger("sovereign.api_requests")

# Origins the packaged app and the dev server legitimately use. The renderer of
# the Electron build runs on app://- and the browser UI on the Next.js dev
# server, so both are cross-origin to 127.0.0.1:8000 and need CORS headers even
# when the "Enable CORS" setting is off.
ALLOWED_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000", "app://-")


def cors_headers_allowed(origin: Optional[str], enable_cors: object) -> bool:
    """True when a cross-origin response keeps its Access-Control-* headers.

    Same-origin/CLI traffic sends no Origin and is never touched. "Enable CORS"
    on widens the boundary to any origin; off limits it to ALLOWED_ORIGINS.
    """
    if not origin:
        return True
    return bool(enable_cors) or origin in ALLOWED_ORIGINS


def _security(request: Request) -> dict:
    svc = getattr(request.app.state, "settings_service", None)
    if svc is None:
        return {}
    try:
        return svc.get_security() or {}
    except Exception:
        return {}


async def lan_auth_middleware(request: Request, call_next):
    """Auth boundary + optional request logging, driven by the settings DB.

    Auth: when ``bind_localhost_only`` is false the server is reachable from
    the LAN, and any configured ``api_token`` is enforced on every request
    (timing-safe compare). Localhost / loopback stays auth-free so Electron +
    CLI loopback keeps working. No token configured = no enforcement (opt-in).

    Logging: ``log_api_requests`` (data_controls) turns on one INFO line per
    request — method, path, status, duration. Off by default; never logs
    bodies.
    """
    sec = _security(request)

    started = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
    finally:
        dc = None
        svc = getattr(request.app.state, "settings_service", None)
        if svc is not None:
            try:
                dc = svc.get_data_controls() or {}
            except Exception:
                dc = None
        if dc and dc.get("log_api_requests"):
            ms = (time.perf_counter() - started) * 1000
            logger.info(
                "%s %s -> %s (%.0fms)",
                request.method,
                request.url.path,
                getattr(response, "status_code", "?"),
                ms,
            )

    if not sec.get("bind_localhost_only", True):
        token = sec.get("api_token") or ""
        if token:
            # Scheme is case-insensitive per RFC 7235; only the credential is
            # compared with compare_digest (timing-safe).
            scheme, _, credential = request.headers.get("authorization", "").partition(" ")
            if scheme.lower() != "bearer" or not secrets.compare_digest(credential, token):
                raise HTTPException(status_code=401, detail="Invalid or missing API token")

    # CORSMiddleware is registered wide-open so "Enable CORS" (and preflight)
    # keeps working; narrow it back to the built-in origins while that switch is
    # off. Previously this stripped the headers unconditionally, which blocked
    # every fetch from the packaged app:// renderer (hardware profile included)
    # while the non-CORS WebSocket metrics kept streaming.
    if response is not None and not cors_headers_allowed(request.headers.get("origin"), sec.get("enable_cors")):
        for h in (
            "access-control-allow-origin",
            "access-control-allow-methods",
            "access-control-allow-headers",
            "access-control-allow-credentials",
            "access-control-max-age",
            "access-control-expose-headers",
        ):
            try:
                del response.headers[h]
            except KeyError:
                pass
    return response
