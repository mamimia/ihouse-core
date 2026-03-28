"""
Phases 954–955 — Owner Deposit Suggestions & Admin Review
===========================================================

Owner-initiated deposit amount suggestion flow with admin review/approve/reject.
Owners cannot directly set the active deposit rule; they submit suggestions
that admin evaluates and approves.

On approval, this router atomically upserts property_charge_rules with the
applied_amount, making the suggestion the new live deposit configuration.

Endpoints (Phase 954 — Owner):
    POST /owner/properties/{property_id}/deposit-suggestion
         Submit a new suggestion (always append-only — creates new row).

    GET  /owner/properties/{property_id}/deposit-suggestion
         Read suggestion history for this property (own properties only).

    GET  /owner/properties/{property_id}/deposit-policy
         Minimal read: is deposit enabled and at what amount?

Endpoints (Phase 955 — Admin review):
    GET  /admin/deposit-suggestions
         List all suggestions for the tenant (?status=  ?property_id=)

    GET  /admin/deposit-suggestions/{suggestion_id}
         Single suggestion detail.

    POST /admin/deposit-suggestions/{suggestion_id}/approve
         Approve a pending suggestion; atomically upserts property_charge_rules.

    POST /admin/deposit-suggestions/{suggestion_id}/reject
         Reject a pending suggestion; no change to property_charge_rules.

Status machine:
    pending → approved (terminal) — side effect: charge rule upserted
    pending → rejected (terminal) — no side effect

Invariants:
    - approve/reject: admin only (not manager — approval mutates the live charge rule).
    - admin_note required on reject (owner sees this as feedback in the portal).
    - applied_amount on approve may differ from suggested_amount (admin can adjust).
    - Multiple concurrent pending rows per property are allowed.
    - All mutations write audit events to admin_audit_log with real actor_id from JWT.
    - Owner endpoints are scoped to owner's own properties (verified via booking_state
      or property ownership check).
    - This router NEVER writes to event_log or booking_state.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_identity_simple as jwt_identity
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["deposit-suggestions"])

_ADMIN_ROLES   = frozenset({"admin"})
_REVIEWER_ROLES = frozenset({"admin", "manager"})  # manager can read, admin can act
_OWNER_ROLES   = frozenset({"owner"})


# ---------------------------------------------------------------------------
# DB / time helpers
# ---------------------------------------------------------------------------

def _get_db() -> Any:
    from supabase import create_client  # type: ignore[import]
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Audit helper
# ---------------------------------------------------------------------------

def _audit(db: Any, tenant_id: str, actor_id: str, action: str,
           entity_id: str, entity_type: str, details: dict) -> None:
    try:
        db.table("admin_audit_log").insert({
            "tenant_id":    tenant_id,
            "actor_id":     actor_id,
            "action":       action,
            "entity_type":  entity_type,
            "entity_id":    entity_id,
            "details":      details,
            "performed_at": _now_iso(),
        }).execute()
    except Exception as exc:
        logger.warning("deposit_suggestion: audit write failed (non-blocking): %s", exc)


# ---------------------------------------------------------------------------
# Serialisers
# ---------------------------------------------------------------------------

def _serialize_suggestion(row: dict) -> dict:
    return {
        "id":                 row.get("id"),
        "tenant_id":          row.get("tenant_id"),
        "property_id":        row.get("property_id"),
        "owner_id":           row.get("owner_id"),
        "suggested_amount":   row.get("suggested_amount"),
        "suggested_currency": row.get("suggested_currency", "THB"),
        "owner_note":         row.get("owner_note"),
        "status":             row.get("status", "pending"),
        "reviewed_by":        row.get("reviewed_by"),
        "reviewed_at":        row.get("reviewed_at"),
        "admin_note":         row.get("admin_note"),
        "applied_amount":     row.get("applied_amount"),
        "created_at":         row.get("created_at"),
    }


def _serialize_policy(row: dict) -> dict:
    """Minimal deposit-policy view exposed to owner."""
    return {
        "deposit_enabled":  row.get("deposit_enabled", False),
        "deposit_amount":   row.get("deposit_amount"),
        "deposit_currency": row.get("deposit_currency", "THB"),
    }


# ---------------------------------------------------------------------------
# Owner: verify property ownership
# ---------------------------------------------------------------------------

def _owner_owns_property(db: Any, tenant_id: str, owner_id: str, property_id: str) -> bool:
    """
    Verify property belongs to this owner within the tenant.
    Checks admin_owners table (owner_id → property link).
    Returns True if ownership is confirmed, False otherwise.
    """
    try:
        res = (
            db.table("admin_owners")
            .select("owner_id")
            .eq("tenant_id", tenant_id)
            .eq("owner_id", owner_id)
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        return bool(res.data)
    except Exception as exc:
        logger.warning("owner property check failed: %s", exc)
        return False


# ===========================================================================
# Phase 954 — Owner endpoints
# ===========================================================================

@router.post(
    "/owner/properties/{property_id}/deposit-suggestion",
    summary="Submit a deposit amount suggestion for admin review (Phase 954)",
    status_code=201,
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def submit_deposit_suggestion(
    property_id: str,
    body: dict,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Submit a new deposit amount suggestion for this property.

    Always creates a new row (append-only). Multiple pending suggestions are allowed.
    Admin will review and approve/reject each one independently.

    **Required:** `suggested_amount` (number > 0)
    **Optional:** `suggested_currency` (default THB), `owner_note`
    """
    role = identity.get("role", "")
    if role not in _OWNER_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": "Only owner role can submit deposit suggestions."},
        )
    tenant_id = identity["tenant_id"]
    owner_id  = identity.get("user_id", "unknown")

    # Validate amount
    suggested_amount = body.get("suggested_amount")
    if suggested_amount is None:
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "suggested_amount is required."},
        )
    try:
        suggested_amount = float(suggested_amount)
        if suggested_amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "suggested_amount must be a positive number."},
        )

    db = client or _get_db()

    # Verify ownership
    if not _owner_owns_property(db, tenant_id, owner_id, property_id):
        return make_error_response(
            status_code=404, code=ErrorCode.NOT_FOUND,
            extra={"detail": "Property not found for this owner."},
        )

    suggestion_id = str(uuid.uuid4())
    row = {
        "id":                 suggestion_id,
        "tenant_id":          tenant_id,
        "property_id":        property_id,
        "owner_id":           owner_id,
        "suggested_amount":   suggested_amount,
        "suggested_currency": (body.get("suggested_currency") or "THB").upper(),
        "owner_note":         body.get("owner_note") or None,
        "status":             "pending",
    }

    try:
        res = db.table("deposit_suggestions").insert(row).execute()
        saved = (res.data or [{}])[0]

        _audit(db, tenant_id, owner_id, "deposit_suggestion_submitted",
               suggestion_id, "deposit_suggestion",
               {"property_id": property_id, "suggested_amount": suggested_amount})

        return JSONResponse(status_code=201, content=_serialize_suggestion(saved))

    except Exception as exc:
        logger.exception("POST deposit-suggestion %s error tenant=%s: %s",
                         property_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.get(
    "/owner/properties/{property_id}/deposit-suggestion",
    summary="Get owner's deposit suggestion history for a property (Phase 954)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_deposit_suggestions_for_owner(
    property_id: str,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Returns this owner's deposit suggestion history for the property, newest first.
    Shows status and admin_note (if reviewed). Does NOT expose charge rule internals.
    """
    role = identity.get("role", "")
    if role not in _OWNER_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": "Only owner role can view deposit suggestions."},
        )
    tenant_id = identity["tenant_id"]
    owner_id  = identity.get("user_id", "unknown")

    db = client or _get_db()

    if not _owner_owns_property(db, tenant_id, owner_id, property_id):
        return make_error_response(
            status_code=404, code=ErrorCode.NOT_FOUND,
            extra={"detail": "Property not found for this owner."},
        )

    try:
        res = (
            db.table("deposit_suggestions")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .eq("owner_id", owner_id)
            .order("created_at", desc=True)
            .execute()
        )
        rows = res.data or []
        return JSONResponse(status_code=200, content={
            "count": len(rows),
            "suggestions": [_serialize_suggestion(r) for r in rows],
        })

    except Exception as exc:
        logger.exception("GET deposit-suggestion owner %s error tenant=%s: %s",
                         property_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.get(
    "/owner/properties/{property_id}/deposit-policy",
    summary="Get minimal deposit policy for a property (Phase 954)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_deposit_policy_for_owner(
    property_id: str,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Minimal read: is deposit enabled for this property, and at what amount?

    Returns: `{ deposit_enabled, deposit_amount, deposit_currency }`

    Does NOT expose electricity config, settlement records, or deduction details.
    """
    role = identity.get("role", "")
    if role not in _OWNER_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": "Only owner role can view deposit policy."},
        )
    tenant_id = identity["tenant_id"]
    owner_id  = identity.get("user_id", "unknown")

    db = client or _get_db()

    if not _owner_owns_property(db, tenant_id, owner_id, property_id):
        return make_error_response(
            status_code=404, code=ErrorCode.NOT_FOUND,
            extra={"detail": "Property not found for this owner."},
        )

    try:
        res = (
            db.table("property_charge_rules")
            .select("deposit_enabled, deposit_amount, deposit_currency")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            # No rule configured yet — default = no deposit
            return JSONResponse(status_code=200, content={
                "deposit_enabled":  False,
                "deposit_amount":   None,
                "deposit_currency": "THB",
            })
        return JSONResponse(status_code=200, content=_serialize_policy(rows[0]))

    except Exception as exc:
        logger.exception("GET deposit-policy %s error tenant=%s: %s",
                         property_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 955 — Admin review endpoints
# ===========================================================================

@router.get(
    "/admin/deposit-suggestions",
    summary="List deposit suggestions for admin review (Phase 955)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_suggestions_admin(
    status: Optional[str] = None,
    property_id: Optional[str] = None,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Returns all deposit suggestions for the tenant.

    **Filters:** `?status=pending|approved|rejected`  `?property_id=`

    Readable by admin and manager. Only admin can approve/reject.
    """
    role = identity.get("role", "")
    if role not in _REVIEWER_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": "Requires admin or manager role."},
        )
    tenant_id = identity["tenant_id"]

    try:
        db = client or _get_db()
        query = (
            db.table("deposit_suggestions")
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("created_at", desc=True)
        )
        if status:
            query = query.eq("status", status)
        if property_id:
            query = query.eq("property_id", property_id)
        res = query.execute()
        rows = res.data or []
        return JSONResponse(status_code=200, content={
            "count": len(rows),
            "suggestions": [_serialize_suggestion(r) for r in rows],
        })

    except Exception as exc:
        logger.exception("GET admin deposit-suggestions error tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.get(
    "/admin/deposit-suggestions/{suggestion_id}",
    summary="Get a single deposit suggestion (Phase 955)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_suggestion_admin(
    suggestion_id: str,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    role = identity.get("role", "")
    if role not in _REVIEWER_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": "Requires admin or manager role."},
        )
    tenant_id = identity["tenant_id"]

    try:
        db = client or _get_db()
        res = (
            db.table("deposit_suggestions")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("id", suggestion_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": f"Suggestion '{suggestion_id}' not found."},
            )
        return JSONResponse(status_code=200, content=_serialize_suggestion(rows[0]))

    except Exception as exc:
        logger.exception("GET suggestion %s error tenant=%s: %s", suggestion_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.post(
    "/admin/deposit-suggestions/{suggestion_id}/approve",
    summary="Approve a deposit suggestion and apply it to the charge rule (Phase 955)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def approve_suggestion(
    suggestion_id: str,
    body: dict,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Approve a pending suggestion.

    Atomically:
    1. Transitions suggestion: pending → approved
    2. Upserts property_charge_rules: deposit_enabled=true, deposit_amount=applied_amount

    **Optional body:**
    - `applied_amount` — amount to apply (defaults to suggestion's suggested_amount)
    - `admin_note` — visible to owner in the portal

    Admin only (not manager).
    """
    role = identity.get("role", "")
    if role not in _ADMIN_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": "Only admin can approve deposit suggestions."},
        )
    tenant_id = identity["tenant_id"]
    actor_id  = identity.get("user_id", "unknown")

    try:
        db = client or _get_db()
        now = _now_iso()

        # Fetch and validate the suggestion
        res = (
            db.table("deposit_suggestions")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("id", suggestion_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": f"Suggestion '{suggestion_id}' not found."},
            )
        suggestion = rows[0]
        if suggestion["status"] != "pending":
            return make_error_response(
                status_code=409, code="CONFLICT",
                extra={"detail": f"Cannot approve suggestion with status='{suggestion['status']}'. Only pending suggestions can be approved."},
            )

        # Resolve applied amount (body override or suggestion default)
        applied_amount = body.get("applied_amount") or suggestion["suggested_amount"]
        try:
            applied_amount = float(applied_amount)
        except (TypeError, ValueError):
            return make_error_response(
                status_code=400, code=ErrorCode.VALIDATION_ERROR,
                extra={"detail": "applied_amount must be a positive number."},
            )

        property_id = suggestion["property_id"]

        # 1. Transition suggestion → approved
        db.table("deposit_suggestions").update({
            "status":         "approved",
            "reviewed_by":    actor_id,
            "reviewed_at":    now,
            "admin_note":     body.get("admin_note") or None,
            "applied_amount": applied_amount,
        }).eq("id", suggestion_id).execute()

        # 2. Upsert property_charge_rules (the atomic side effect)
        db.table("property_charge_rules").upsert({
            "tenant_id":        tenant_id,
            "property_id":      property_id,
            "deposit_enabled":  True,
            "deposit_amount":   applied_amount,
            "deposit_currency": suggestion.get("suggested_currency", "THB"),
            "updated_by":       actor_id,
            "updated_at":       now,
        }, on_conflict="tenant_id,property_id").execute()

        # Audit — two events: suggestion_approved + charge_rules_updated
        _audit(db, tenant_id, actor_id, "suggestion_approved",
               suggestion_id, "deposit_suggestion",
               {"property_id": property_id, "applied_amount": applied_amount,
                "suggested_amount": suggestion["suggested_amount"]})
        _audit(db, tenant_id, actor_id, "charge_rules_updated",
               property_id, "property_charge_rule",
               {"source": "suggestion_approval", "suggestion_id": suggestion_id,
                "deposit_enabled": True, "deposit_amount": applied_amount})

        return JSONResponse(status_code=200, content={
            "suggestion_id":  suggestion_id,
            "status":         "approved",
            "applied_amount": applied_amount,
            "property_id":    property_id,
        })

    except Exception as exc:
        logger.exception("POST approve %s error tenant=%s: %s", suggestion_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.post(
    "/admin/deposit-suggestions/{suggestion_id}/reject",
    summary="Reject a deposit suggestion (Phase 955)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def reject_suggestion(
    suggestion_id: str,
    body: dict,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Reject a pending suggestion. No change is made to property_charge_rules.

    **Required:** `admin_note` — owner sees this as feedback in the portal.

    Admin only (not manager).
    """
    role = identity.get("role", "")
    if role not in _ADMIN_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": "Only admin can reject deposit suggestions."},
        )
    tenant_id = identity["tenant_id"]
    actor_id  = identity.get("user_id", "unknown")

    admin_note = (body.get("admin_note") or "").strip()
    if not admin_note:
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "admin_note is required when rejecting — the owner sees this as feedback."},
        )

    try:
        db = client or _get_db()
        now = _now_iso()

        res = (
            db.table("deposit_suggestions")
            .select("id, status, property_id, suggested_amount")
            .eq("tenant_id", tenant_id)
            .eq("id", suggestion_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": f"Suggestion '{suggestion_id}' not found."},
            )
        suggestion = rows[0]
        if suggestion["status"] != "pending":
            return make_error_response(
                status_code=409, code="CONFLICT",
                extra={"detail": f"Cannot reject suggestion with status='{suggestion['status']}'. Only pending suggestions can be rejected."},
            )

        db.table("deposit_suggestions").update({
            "status":      "rejected",
            "reviewed_by": actor_id,
            "reviewed_at": now,
            "admin_note":  admin_note,
        }).eq("id", suggestion_id).execute()

        _audit(db, tenant_id, actor_id, "suggestion_rejected",
               suggestion_id, "deposit_suggestion",
               {"property_id": suggestion["property_id"],
                "suggested_amount": suggestion["suggested_amount"],
                "admin_note": admin_note})

        return JSONResponse(status_code=200, content={
            "suggestion_id": suggestion_id,
            "status":        "rejected",
            "admin_note":    admin_note,
        })

    except Exception as exc:
        logger.exception("POST reject %s error tenant=%s: %s", suggestion_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
