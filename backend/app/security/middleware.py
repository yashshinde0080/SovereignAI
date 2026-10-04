"""Auth + request-logging middleware."""
import logging
import secrets
import time
from fastapi import Request, HTTPException

logger = logging.getLogger("sovereign.api_requests")


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

    # enable_cors=False (default): strip CORS headers FastAPI's CORSMiddleware
    # always added. Cheap, and keeps the "Enable CORS" switch honest without
    # re-architecting middleware registration.
    cors_on = sec.get("enable_cors")
    if cors_on is False and response is not None:
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
