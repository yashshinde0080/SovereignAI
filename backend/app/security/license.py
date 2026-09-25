"""License enforcement.

**Nothing here is enforced.** SovereignAI Edge ships under MIT with no tiers,
no activation keys and no remote validation — see ``LICENSE`` and the
``enterprise_repo`` provider if you need gated model distribution.

This module is an explicit placeholder rather than a zero-byte file so the
absence of enforcement is deliberate and visible. If a licence tier is ever
added, implement it *here* and call it from the startup path; do not add a
``check_license()`` that returns ``True`` unconditionally — a security-shaped
function that always passes is worse than no function, because it invites
callers to depend on it.
"""


class LicenseManager:
    """Reserved for future licence tiers. Not implemented."""

    def __init__(self):
        self._raise()

    @staticmethod
    def _raise():
        raise NotImplementedError(
            "No licence enforcement exists in this build (MIT, no tiers). "
            "Implement it in app/security/license.py before calling this."
        )

    def is_valid(self) -> bool:  # pragma: no cover - unreachable by design
        self._raise()
