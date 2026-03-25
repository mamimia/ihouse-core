"""
Phase 868 — Act As: Backend Foundation
========================================

Admin-only capability for entering a scoped acting session with a target
role's effective permissions. The admin performs real mutations through the
role's operational flows.

Endpoints:
    POST /auth/act-as/start   — Start an acting session → returns scoped JWT
    POST /auth/act-as/end     — End an active acting session
    GET  /auth/act-as/status  — Check current session status

Rules (from admin-preview-and-act-as.md §3):
    1. Admin's real identity is ALWAYS preserved (never replaced)
    2. Scoped act_as JWT issued with token_type="act_as"
    3. Hard TTL: default 1 hour, max 4 hours
    4. Dual attribution on every mutation: real_admin_id + effective_role
    5. Full audit logging

Environment gate:
    Act As is ONLY available when IHOUSE_ENV != 'production'.
    Production requests get 404 — the capability is architecturally absent.
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import jwt as pyjwt
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.auth import jwt_identity
from api.envelope import ok, err

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

_ALGORITHM = "HS256"
_DEFAULT_TTL_SECONDS = 3600     # 1 hour
_MAX_TTL_SECONDS = 14400        # 4 hours

# Roles that can be acted as
_ACTABLE_ROLES = frozenset({
    "manager", "owner", "worker", "cleaner",
    "checkin", "checkout", "checkin_checkout", "maintenance",
})


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Environment gate
# ---------------------------------------------------------------------------

def _is_production() -> bool:
    """Act As is architecturally absent in production."""
    env = os.environ.get("IHOUSE_ENV", "development").lower().strip()
    return env == "production"


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class StartActAsRequest(BaseModel):
    target_role: str = Field(..., min_length=1, max_length=50,
                             description="The role to act as")
    ttl_seconds: int = Field(default=_DEFAULT_TTL_SECONDS, ge=60, le=_MAX_TTL_SECONDS,
                             description="Session TTL in seconds (60-14400)")
    context: Optional[dict] = Field(default=None,
                                    description="Optional scope narrowing (property_id, etc.)")


class EndActAsRequest(BaseModel):
    session_id: str = Field(..., min_length=1, description="The acting session ID to end")


# ---------------------------------------------------------------------------
# POST /auth/act-as/start
# ---------------------------------------------------------------------------

@router.post(
    "/auth/act-as/start",
    summary="Start an Act As session (admin only, non-production)",
    responses={
        200: {"description": "Acting session started, scoped JWT returned"},
        403: {"description": "Not admin or production environment"},
        404: {"description": "Act As not available in production"},
    },
)
async def start_act_as(
    body: StartActAsRequest,
    identity: dict = Depends(jwt_identity),
) -> JSONResponse:
    """
    Start an acting session. Only admins in non-production environments.

    Returns a scoped act_as JWT that carries:
      - sub = admin UUID (real identity preserved)
      - role = target_role (effective permissions)
      - token_type = "act_as"
      - acting_session_id = session UUID
      - real_admin_id = admin UUID (explicit redundancy)
    """
    # Gate: production → 404 (architecturally absent)
    if _is_production():
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    # Gate: admin only
    # Check original role — in preview mode, identity["role"] is overridden
    # but is_preview flag is set. Act As requires a real admin, not a previewing admin.
    real_role = identity.get("role", "")
    is_preview = identity.get("is_preview", False)

    if is_preview:
        return err("PREVIEW_MODE", "Cannot start Act As while in Preview mode", status=403)

    if real_role != "admin":
        return err("ADMIN_REQUIRED", "Only admin users can use Act As", status=403)

    # Validate target role
    if body.target_role not in _ACTABLE_ROLES:
        return err(
            "INVALID_ROLE",
            f"Cannot act as '{body.target_role}'. Valid roles: {sorted(_ACTABLE_ROLES)}",
            status=422,
        )

    # Cannot act as admin (that's just being admin)
    if body.target_role == "admin":
        return err("INVALID_ROLE", "Cannot act as admin — you already are admin", status=422)

    admin_user_id = identity.get("user_id", "")
    admin_email = identity.get("email", "")
    tenant_id = identity.get("tenant_id", "")

    if not admin_user_id or not tenant_id:
        return err("INVALID_IDENTITY", "Missing user_id or tenant_id in JWT", status=403)

    # Phase 866 (Model B): 409 single-session check removed.
    # An admin may open multiple concurrent Act As sessions. Each is independently
    # tracked via its unique session_id and independently isolated in browser tabs.
    
    # Create session record
    session_id = str(uuid.uuid4())
    now_utc = datetime.now(timezone.utc)
    expires_at = now_utc + timedelta(seconds=body.ttl_seconds)

    try:
        db = _get_supabase_client()
        db.table("acting_sessions").insert({
            "id": session_id,
            "real_admin_user_id": admin_user_id,
            "real_admin_email": admin_email,
            "acting_as_role": body.target_role,
            "acting_as_context": body.context or {},
            "tenant_id": tenant_id,
            "expires_at": expires_at.isoformat(),
        }).execute()
    except Exception as exc:
        logger.exception("act-as/start: session creation failed: %s", exc)
        return err("SESSION_CREATION_FAILED", f"Failed to create session: {exc}", status=500)

    # Issue scoped act_as JWT
    jwt_secret = os.environ.get("IHOUSE_JWT_SECRET", "")
    if not jwt_secret:
        return err("AUTH_NOT_CONFIGURED", "IHOUSE_JWT_SECRET not set", status=503)

    now_ts = int(time.time())
    jwt_payload = {
        "sub": admin_user_id,               # Real identity — NEVER changes
        "tenant_id": tenant_id,
        "role": body.target_role,            # Effective permissions
        "token_type": "act_as",              # Canonical signal
        "acting_session_id": session_id,     # Links to session record
        "real_admin_id": admin_user_id,      # Explicit redundancy for safety
        "real_admin_email": admin_email,
        "auth_method": "act_as",
        "iat": now_ts,
        "exp": now_ts + body.ttl_seconds,
    }
    act_as_token = pyjwt.encode(jwt_payload, jwt_secret, algorithm=_ALGORITHM)

    # Audit event
    try:
        from services.audit_writer import write_audit_event
        write_audit_event(
            tenant_id=tenant_id,
            actor_id=admin_user_id,
            action="ACT_AS_STARTED",
            entity_type="acting_session",
            entity_id=session_id,
            payload={
                "acting_as_role": body.target_role,
                "ttl_seconds": body.ttl_seconds,
                "context": body.context or {},
                "real_admin_email": admin_email,
            },
        )
    except Exception as exc:
        logger.warning("act-as/start: audit event failed: %s", exc)

    logger.info(
        "Act As session started: admin=%s (%s) acting_as=%s session=%s ttl=%ds",
        admin_user_id, admin_email, body.target_role, session_id, body.ttl_seconds,
    )

    return ok({
        "session_id": session_id,
        "acting_as_role": body.target_role,
        "token": act_as_token,
        "expires_at": expires_at.isoformat(),
        "ttl_seconds": body.ttl_seconds,
        "real_admin_id": admin_user_id,
        "real_admin_email": admin_email,
    })


# ---------------------------------------------------------------------------
# POST /auth/act-as/end
# ---------------------------------------------------------------------------

@router.post(
    "/auth/act-as/end",
    summary="End an acting session",
    responses={
        200: {"description": "Session ended"},
        404: {"description": "Session not found or already ended"},
    },
)
async def end_act_as(
    body: EndActAsRequest,
    identity: dict = Depends(jwt_identity),
) -> JSONResponse:
    """End an active acting session. Returns to normal admin context."""
    if _is_production():
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    user_id = identity.get("user_id", identity.get("sub", ""))
    # Accept ending from either the act_as token or the original admin token
    real_admin_id = identity.get("real_admin_id", user_id)
    tenant_id = identity.get("tenant_id", "")

    try:
        db = _get_supabase_client()

        # Verify session exists, belongs to this admin, and is still active
        result = (
            db.table("acting_sessions")
            .select("*")
            .eq("id", body.session_id)
            .eq("real_admin_user_id", real_admin_id)
            .is_("ended_at", "null")
            .execute()
        )
        rows = result.data or []
        if not rows:
            return err("SESSION_NOT_FOUND", "No active session found with this ID", status=404)

        session = rows[0]
        now_utc = datetime.now(timezone.utc).isoformat()

        # Mark session as ended
        db.table("acting_sessions").update({
            "ended_at": now_utc,
            "end_reason": "manual_exit",
        }).eq("id", body.session_id).execute()

        # Audit event
        try:
            from services.audit_writer import write_audit_event
            write_audit_event(
                tenant_id=tenant_id,
                actor_id=real_admin_id,
                action="ACT_AS_ENDED",
                entity_type="acting_session",
                entity_id=body.session_id,
                payload={
                    "acting_as_role": session.get("acting_as_role", ""),
                    "end_reason": "manual_exit",
                    "real_admin_email": session.get("real_admin_email", ""),
                },
            )
        except Exception as exc:
            logger.warning("act-as/end: audit event failed: %s", exc)

        logger.info(
            "Act As session ended: session=%s admin=%s role=%s reason=manual_exit",
            body.session_id, real_admin_id, session.get("acting_as_role"),
        )

        return ok({
            "session_id": body.session_id,
            "ended_at": now_utc,
            "end_reason": "manual_exit",
        })

    except Exception as exc:
        logger.exception("act-as/end: error: %s", exc)
        return err("END_FAILED", f"Failed to end session: {exc}", status=500)


# ---------------------------------------------------------------------------
# GET /auth/act-as/status
# ---------------------------------------------------------------------------

@router.get(
    "/auth/act-as/status",
    summary="Check current acting session status",
    responses={
        200: {"description": "Current session status (or null if none active)"},
    },
)
async def act_as_status(
    identity: dict = Depends(jwt_identity),
) -> JSONResponse:
    """Return the current acting session for this admin, if any."""
    if _is_production():
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    user_id = identity.get("user_id", identity.get("sub", ""))
    real_admin_id = identity.get("real_admin_id", user_id)
    tenant_id = identity.get("tenant_id", "")

    # Phase 866: Under Model B, a single admin can have multiple active sessions.
    # We must explicitly check the status of the caller's specific session.
    acting_session_id = identity.get("acting_session_id")

    try:
        db = _get_supabase_client()
        query = (
            db.table("acting_sessions")
            .select("id,acting_as_role,acting_as_context,created_at,expires_at,ended_at,end_reason")
            .eq("real_admin_user_id", real_admin_id)
            .eq("tenant_id", tenant_id)
            .is_("ended_at", "null")
        )
        
        # If calling from within an Act As tab, validate that specific session.
        # If calling from Admin tab (no acting_session_id), fall back to most recent 
        # (though Admin tabs no longer call this in Phase 865+).
        if acting_session_id:
            query = query.eq("id", acting_session_id)
        else:
            query = query.order("created_at", desc=True).limit(1)
            
        result = query.execute()
        rows = result.data or []
        if not rows:
            return ok({"active_session": None})

        session = rows[0]
        expires_at = datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00"))
        now_utc = datetime.now(timezone.utc)

        if expires_at <= now_utc:
            # Session expired — mark it
            try:
                db.table("acting_sessions").update({
                    "ended_at": now_utc.isoformat(),
                    "end_reason": "expired",
                }).eq("id", session["id"]).execute()
            except Exception:
                pass
            return ok({"active_session": None, "expired_session_id": session["id"]})

        remaining_seconds = int((expires_at - now_utc).total_seconds())

        return ok({
            "active_session": {
                "session_id": session["id"],
                "acting_as_role": session["acting_as_role"],
                "context": session.get("acting_as_context", {}),
                "created_at": session["created_at"],
                "expires_at": session["expires_at"],
                "remaining_seconds": remaining_seconds,
            },
        })

    except Exception as exc:
        logger.exception("act-as/status: error: %s", exc)
        return err("STATUS_FAILED", f"Failed to check status: {exc}", status=500)
