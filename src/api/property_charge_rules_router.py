"""
Phase 952 — Property Charge Rules (Admin CRUD)
===============================================

Per-property deposit and electricity configuration controlled exclusively by admin/manager.
This is the live operational source of truth for:
  - Whether a deposit is required at check-in and at what amount
  - Whether electricity is billed and at what rate per kWh

Endpoints:
    GET  /admin/properties/{property_id}/charge-rules  — read single property rule
    PUT  /admin/properties/{property_id}/charge-rules  — upsert rule (full replace)
    GET  /admin/properties/charge-rules                — list all properties' rules

Invariants:
    - JWT auth required. Role: admin or manager.
    - Tenant isolation: tenant_id always from JWT, never from body.
    - updated_by is always the real user_id from JWT — no hardcoded actors.
    - All PUT mutations write a charge_rules_updated audit event to admin_audit_log.
    - This router NEVER writes to event_log or booking_state.
    - Electricity billing against bookings is a future workstream; this router
      only stores the configured rate.

Integration:
    - Phase 953: /worker/bookings/{id}/charge-config reads from this table to
      pre-fill deposit amounts in the check-in wizard.
    - Phase 955: suggestion approve atomically upserts this table when admin
      approves an owner deposit suggestion.
    - Phase 690+ deposit collection (deposit_settlement_router) uses this table
      as the authoritative deposit amount reference.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_identity_simple as jwt_identity
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["property-charge-rules"])

_ALLOWED_ROLES = frozenset({"admin", "manager"})


# ---------------------------------------------------------------------------
# DB helper
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
# Role guard
# ---------------------------------------------------------------------------

def _assert_role(identity: dict) -> Optional[JSONResponse]:
    role = identity.get("role", "")
    if role not in _ALLOWED_ROLES:
        return make_error_response(
            status_code=403,
            code="FORBIDDEN",
            extra={"detail": f"Role '{role}' cannot manage charge rules. Requires admin or manager."},
        )
    return None


# ---------------------------------------------------------------------------
# Audit helper
# ---------------------------------------------------------------------------

def _audit(db: Any, tenant_id: str, actor_id: str, action: str,
           property_id: str, details: dict) -> None:
    """Best-effort write to admin_audit_log."""
    try:
        db.table("admin_audit_log").insert({
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "action": action,
            "entity_type": "property_charge_rule",
            "entity_id": property_id,
            "details": details,
            "performed_at": _now_iso(),
        }).execute()
    except Exception as exc:
        logger.warning("property_charge_rules: audit write failed (non-blocking): %s", exc)


# ---------------------------------------------------------------------------
# Serialiser
# ---------------------------------------------------------------------------

def _serialize(row: dict) -> dict:
    return {
        "id":                   row.get("id"),
        "tenant_id":            row.get("tenant_id"),
        "property_id":          row.get("property_id"),
        "deposit_enabled":      row.get("deposit_enabled", False),
        "deposit_amount":       row.get("deposit_amount"),
        "deposit_currency":     row.get("deposit_currency", "THB"),
        "deposit_notes":        row.get("deposit_notes"),
        "electricity_enabled":  row.get("electricity_enabled", False),
        "electricity_rate_kwh": row.get("electricity_rate_kwh"),
        "electricity_currency": row.get("electricity_currency", "THB"),
        "electricity_notes":    row.get("electricity_notes"),
        "updated_by":           row.get("updated_by"),
        "updated_at":           row.get("updated_at"),
        "created_at":           row.get("created_at"),
    }


# ---------------------------------------------------------------------------
# GET /admin/properties/{property_id}/charge-rules
# ---------------------------------------------------------------------------

@router.get(
    "/admin/properties/{property_id}/charge-rules",
    summary="Get deposit + electricity charge rule for a property (Phase 952)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_charge_rule(
    property_id: str,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Returns the active deposit and electricity charge configuration for one property.
    404 if no rule has been configured yet for this property.
    """
    err = _assert_role(identity)
    if err:
        return err
    tenant_id = identity["tenant_id"]

    try:
        db = client or _get_db()
        res = (
            db.table("property_charge_rules")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return make_error_response(
                status_code=404,
                code=ErrorCode.NOT_FOUND,
                extra={"detail": f"No charge rule configured for property '{property_id}'."},
            )
        return JSONResponse(status_code=200, content=_serialize(rows[0]))

    except Exception as exc:
        logger.exception("GET charge-rules %s error tenant=%s: %s", property_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# PUT /admin/properties/{property_id}/charge-rules
# ---------------------------------------------------------------------------

@router.put(
    "/admin/properties/{property_id}/charge-rules",
    summary="Upsert deposit + electricity charge rule for a property (Phase 952)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def upsert_charge_rule(
    property_id: str,
    body: dict,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Upsert the charge rule for one property (creates if absent, fully replaces if present).

    **Required:** `deposit_enabled` (bool), `electricity_enabled` (bool)
    **Optional:** `deposit_amount`, `deposit_currency`, `deposit_notes`,
                  `electricity_rate_kwh`, `electricity_currency`, `electricity_notes`
    """
    err = _assert_role(identity)
    if err:
        return err
    tenant_id = identity["tenant_id"]
    actor_id = identity.get("user_id", "unknown")

    # Validate required booleans
    if "deposit_enabled" not in body or "electricity_enabled" not in body:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "deposit_enabled and electricity_enabled are required boolean fields."},
        )

    now = _now_iso()
    row = {
        "tenant_id":            tenant_id,
        "property_id":          property_id,
        "deposit_enabled":      bool(body["deposit_enabled"]),
        "deposit_amount":       body.get("deposit_amount") or None,
        "deposit_currency":     (body.get("deposit_currency") or "THB").upper(),
        "deposit_notes":        body.get("deposit_notes") or None,
        "electricity_enabled":  bool(body["electricity_enabled"]),
        "electricity_rate_kwh": body.get("electricity_rate_kwh") or None,
        "electricity_currency": (body.get("electricity_currency") or "THB").upper(),
        "electricity_notes":    body.get("electricity_notes") or None,
        "updated_by":           actor_id,
        "updated_at":           now,
    }

    try:
        db = client or _get_db()
        res = (
            db.table("property_charge_rules")
            .upsert(row, on_conflict="tenant_id,property_id")
            .execute()
        )
        saved = (res.data or [{}])[0]

        _audit(db, tenant_id, actor_id, "charge_rules_updated", property_id, {
            "deposit_enabled":     row["deposit_enabled"],
            "deposit_amount":      row["deposit_amount"],
            "electricity_enabled": row["electricity_enabled"],
            "electricity_rate_kwh": row["electricity_rate_kwh"],
        })

        return JSONResponse(status_code=200, content=_serialize(saved))

    except Exception as exc:
        logger.exception("PUT charge-rules %s error tenant=%s: %s", property_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /admin/properties/charge-rules  (list all)
# ---------------------------------------------------------------------------

@router.get(
    "/admin/properties/charge-rules",
    summary="List all property charge rules for the tenant (Phase 952)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_charge_rules(
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Returns all configured charge rules for the tenant.
    Properties with no rule are not included — they have default (unconfigured) state.
    """
    err = _assert_role(identity)
    if err:
        return err
    tenant_id = identity["tenant_id"]

    try:
        db = client or _get_db()
        res = (
            db.table("property_charge_rules")
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("property_id", desc=False)
            .execute()
        )
        rows = res.data or []
        return JSONResponse(status_code=200, content={
            "count": len(rows),
            "rules": [_serialize(r) for r in rows],
        })

    except Exception as exc:
        logger.exception("GET charge-rules list error tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
