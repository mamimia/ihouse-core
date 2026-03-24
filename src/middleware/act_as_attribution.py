"""
Phase 869 — Act As: Mutation Attribution Middleware
=====================================================

Catches every mutation (POST/PUT/PATCH/DELETE) performed during an Act As
session and writes a structured audit event with dual attribution:

    real_admin_id      — the actual admin who performed the action
    acting_session_id  — which session this belongs to
    effective_role     — the permission lens applied
    real_admin_email   — for human-readable audit reports

Architecture:
    This middleware runs AFTER the request is processed (via call_next).
    It reads the identity from ``request.state.identity``, which is set
    by the ``jwt_identity`` FastAPI dependency during route handling.

    It does NOT decode the JWT independently — it reuses the exact same
    identity context that the route handler used.

    Audit events are best-effort: failures are logged but never interfere
    with the response already sent.

Audit event shape:
    entity_type = "acting_session"
    entity_id   = <acting_session_id>
    action      = "ACT_AS_MUTATION"
    payload     = {
        "method": "POST",
        "path": "/booking/123/checkin",
        "effective_role": "checkin",
        "real_admin_id": "<admin-uuid>",
        "real_admin_email": "admin@example.com",
        "response_status": 200,
    }
"""
from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)

# HTTP methods that constitute mutations
_MUTATION_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class ActAsAttributionMiddleware(BaseHTTPMiddleware):
    """
    Phase 869 — Writes dual-attribution audit events for every mutation
    performed during an Act As session.

    Runs after the request is fully handled. Only fires when:
      1. The identity has ``is_acting == True``
      2. The request method is a mutation (POST/PUT/PATCH/DELETE)
      3. The response was successful (2xx or 3xx — not error responses)
    """

    async def dispatch(self, request: Request, call_next):
        # Let the request proceed normally
        response = await call_next(request)

        # Only interested in mutations
        if request.method.upper() not in _MUTATION_METHODS:
            return response

        # Check if identity was set and is an acting session
        identity = getattr(request.state, "identity", None)
        if not identity or not identity.get("is_acting"):
            return response

        # Only log successful mutations (2xx/3xx)
        if response.status_code >= 400:
            return response

        # Extract attribution fields
        real_admin_id = identity.get("real_admin_id", "")
        acting_session_id = identity.get("acting_session_id", "")
        effective_role = identity.get("role", "")
        real_admin_email = identity.get("real_admin_email", "")
        tenant_id = identity.get("tenant_id", "")
        path = request.url.path

        # Best-effort audit event (never fails the request)
        try:
            from services.audit_writer import write_audit_event
            write_audit_event(
                tenant_id=tenant_id,
                actor_id=real_admin_id,
                action="ACT_AS_MUTATION",
                entity_type="acting_session",
                entity_id=acting_session_id,
                payload={
                    "method": request.method.upper(),
                    "path": path,
                    "effective_role": effective_role,
                    "real_admin_id": real_admin_id,
                    "real_admin_email": real_admin_email,
                    "response_status": response.status_code,
                },
            )
            logger.info(
                "Act As mutation recorded: %s %s by admin=%s as=%s session=%s → %d",
                request.method,
                path,
                real_admin_id,
                effective_role,
                acting_session_id,
                response.status_code,
            )
        except Exception as exc:
            logger.warning(
                "Act As attribution audit failed (best-effort): %s %s session=%s: %s",
                request.method, path, acting_session_id, exc,
            )

        return response
