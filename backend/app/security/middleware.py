"""Auth middleware: token required when bound beyond localhost."""
import secrets
from fastapi import Request, HTTPException


def _security(request: Request) -> dict:
    svc = getattr(request.app.state, "settings_service", None)
    if svc is None:
        return {}
    try:
        return svc.get_security() or {}
    except Exception:
        return {}


async def lan_auth_middleware(request: Request, call_next):
    """Require a Bearer token when the API is exposed beyond localhost.

    Localhost / loopback stays auth-free (Electron + CLI talk to it directly).
    Driven by the settings DB: when ``bind_localhost_only`` is false the server
    is reachable from the LAN, and any configured ``api_token`` is enforced on
    every request. No token configured = no enforcement (opt-in).
    """
    sec = _security(request)
    if not sec.get("bind_localhost_only", True):
        token = sec.get("api_token") or ""
        if token:
            # Scheme is case-insensitive per RFC 7235; only the credential is
            # compared with compare_digest (timing-safe).
            scheme, _, credential = request.headers.get("authorization", "").partition(" ")
            if scheme.lower() != "bearer" or not secrets.compare_digest(credential, token):
                raise HTTPException(status_code=401, detail="Invalid or missing API token")
    return await call_next(request)
