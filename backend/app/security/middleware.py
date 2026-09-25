"""Auth middleware: token required when bound beyond localhost."""
import secrets
from fastapi import Request, HTTPException

from app.security.audit import audit_logger


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
                # Best-effort and attribute-tolerant: the audit call must never
                # be the reason a request 500s instead of 401s.
                method = getattr(request, "method", "")
                path = getattr(getattr(request, "url", None), "path", "")
                client = getattr(request, "client", None)
                await audit_logger.log(
                    event_type="auth_rejected",
                    severity=audit_logger.SEVERITY_WARNING,
                    source="auth_middleware",
                    message=f"Rejected {method} {path}".strip(),
                    details={
                        "method": method,
                        "path": path,
                        "client": getattr(client, "host", None),
                    },
                )
                raise HTTPException(status_code=401, detail="Invalid or missing API token")
    return await call_next(request)
