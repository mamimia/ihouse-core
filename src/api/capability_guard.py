"""
Phase 862 P37 — Capability Enforcement Dependency
===================================================

FastAPI dependency factory that gates manager-facing endpoints
by checking delegated capabilities from tenant_permissions.

Usage:
    from api.capability_guard import require_capability

    @router.get("/financial/report")
    async def report(
        identity: dict = Depends(jwt_identity),
        _cap: None = Depends(require_capability("financial")),
    ):
        ...

Access rules:
    - admin role     → always allowed (all capabilities implied)
    - ops role       → allowed for capabilities listed in _ROLE_CAPABILITY_ALLOWLIST
                       Currently: bookings (read access for Operational Manager surface)
    - manager role   → allowed only if the specific capability is delegated
                       via tenant_permissions
    - other roles    → denied (HTTP 403)

ops role rationale (Issue 17):
    ops is an Operational Manager role — above field workers, below admin/manager.
    The frontend middleware (Phase 397) explicitly grants ops access to /bookings
    and /calendar. The Phase 862 guard originally used a binary admin/manager model
    that blocked ops unconditionally. This was a coherence gap: the middleware grant
    was intentional (ops needs booking visibility to coordinate operations) and the
    guard simply did not account for the ops role. The fix adds ops to the
    _ROLE_CAPABILITY_ALLOWLIST for the bookings capability only.
    ops does NOT get financial, staffing, or other sensitive capabilities —
    those remain admin/manager-delegated only.

The guard fetches `tenant_permissions.permissions` from the DB,
extracts the `capabilities` map, and checks the requested capability.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Role-level capability allowlist (Issue 17)
# ---------------------------------------------------------------------------
# Non-admin, non-manager roles listed here get unconditional pass-through
# for the named capability — WITHOUT going through the DB delegation check.
#
# This is intentional and deliberate. Adding a role here is a product decision,
# not a security relaxation — the capability guard still blocks that role for
# any capability NOT listed in this map.
#
# ops + bookings:
#   ops (Operational Manager) needs booking visibility to coordinate workers.
#   The frontend middleware (Phase 397) explicitly grants ops /bookings and
#   /calendar. The calendar calls GET /bookings exclusively. Blocking ops at
#   the capability guard while allowing frontend navigation produced broken pages.
# ---------------------------------------------------------------------------
_ROLE_CAPABILITY_ALLOWLIST: dict[str, set[str]] = {
    "ops": {"bookings"},
}


def _get_db() -> Any:
    """Get Supabase client with service_role key."""
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return None
    return create_client(url, key)


def require_capability(capability: str) -> Callable:
    """
    Return a FastAPI dependency that enforces a specific delegated capability.

    Args:
        capability: Name of the capability to require (e.g., "financial", "staffing").

    Returns:
        A Depends-compatible async function that raises HTTP 403 if the caller
        doesn't have the required capability.
    """
    # ── Dev/test mode bypass ──────────────────────────────────────────
    #
    # When IHOUSE_DEV_MODE=true, return a no-op guard with NO dependencies.
    #
    # WHY: require_capability() is evaluated at import time (module-level
    #      Depends(require_capability("x")) in router files). The real guard
    #      depends on jwt_identity, which requires a full JWT infrastructure.
    #      Tests that mock only jwt_auth (the simpler dependency) cannot
    #      resolve jwt_identity, causing FastAPI to return 422.
    #
    # SAFETY:
    #   1. IHOUSE_DEV_MODE=true is blocked in production by env_validator.py
    #      (lines 66-72: "IHOUSE_DEV_MODE=true with IHOUSE_ENV=production"
    #      triggers a fatal error and sys.exit(1)).
    #   2. Production deployments MUST set IHOUSE_ENV=production.
    #   3. The _noop function has zero parameters — FastAPI treats it as a
    #      dependency with no inputs, resolving cleanly without side effects.
    #   4. The real guard (_guard below) is the ONLY code path in production.
    #
    # SCOPE: This bypass ONLY affects require_capability(). All other auth
    #        checks (jwt_auth, jwt_identity, role checks) have their own
    #        independent dev-mode handling in api/auth.py.
    # ─────────────────────────────────────────────────────────────────
    if os.environ.get("IHOUSE_DEV_MODE", "").lower() in ("true", "1", "yes"):
        async def _noop() -> None:
            return None
        return _noop

    from api.auth import jwt_identity

    async def _guard(
        request: Request,
        identity: dict = Depends(jwt_identity),
    ) -> None:

        role = identity.get("role", "")
        user_id = identity.get("user_id", "")
        tenant_id = identity.get("tenant_id", "")

        # Admin always has all capabilities
        if role == "admin":
            return None

        # Role-level capability allowlist (e.g., ops → bookings)
        # These roles get unconditional pass-through for specific capabilities
        # without going through the manager delegation DB check.
        # See _ROLE_CAPABILITY_ALLOWLIST at the top of this module.
        if capability in _ROLE_CAPABILITY_ALLOWLIST.get(role, set()):
            logger.debug(
                "capability_guard: role=%s allowed for capability=%s via allowlist user=%s",
                role, capability, user_id,
            )
            return None

        # Only managers can have delegated capabilities
        if role != "manager":
            logger.warning(
                "capability_guard: role=%s denied for capability=%s user=%s",
                role, capability, user_id,
            )
            raise HTTPException(
                status_code=403,
                detail=f"CAPABILITY_DENIED: role '{role}' does not have '{capability}' capability.",
            )

        # Check the DB for delegated capabilities
        db = _get_db()
        if not db:
            logger.error("capability_guard: DB not available, denying access")
            raise HTTPException(
                status_code=503,
                detail="Capability check unavailable — database not configured.",
            )

        try:
            result = (
                db.table("tenant_permissions")
                .select("permissions")
                .eq("tenant_id", tenant_id)
                .eq("user_id", user_id)
                .eq("role", "manager")
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            rows = result.data or []
            if not rows:
                logger.warning(
                    "capability_guard: no active manager membership for user=%s tenant=%s",
                    user_id, tenant_id,
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"CAPABILITY_DENIED: no active manager membership found.",
                )

            permissions = rows[0].get("permissions") or {}
            from services.delegated_capabilities import has_capability
            if not has_capability(permissions, capability):
                logger.info(
                    "capability_guard: user=%s denied capability=%s (caps=%s)",
                    user_id, capability, permissions.get("capabilities", {}),
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"CAPABILITY_DENIED: '{capability}' capability not delegated to this manager.",
                )

            # Allowed
            return None

        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("capability_guard: DB check failed: %s", exc)
            raise HTTPException(
                status_code=503,
                detail=f"Capability check failed: {exc}",
            )

    return _guard
