"""
Phase 972 — Guest Dossier Composite API
========================================

Single composite endpoint that returns everything needed to render the
Guest Dossier UI in one round-trip:

  GET /guests/{guest_id}/dossier

Returns:
  - Full guest identity record (including document fields)
  - Signed URL for passport/document photo (15-min expiry)
  - Current active stay (if any): booking + settlement + portal state
  - Stay history: all linked bookings with settlement summaries
  - Activity trail: recent audit events for this guest

Auth: admin, manager, ops only (same as guests_router).
Tenant isolation enforced on all queries.
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
router = APIRouter(tags=["guests"])

_ALLOWED_ROLES = frozenset({"admin", "manager", "ops"})


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

def _get_db() -> Any:
    from supabase import create_client  # type: ignore[import]
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


# ---------------------------------------------------------------------------
# GET /guests/{guest_id}/dossier
# ---------------------------------------------------------------------------

@router.get(
    "/guests/{guest_id}/dossier",
    summary="Full guest dossier: identity + stays + settlement + activity (Phase 972)",
    responses={
        200: {"description": "Composite guest dossier"},
        401: {"description": "Missing or invalid JWT"},
        403: {"description": "Requires admin, manager, or ops role"},
        404: {"description": "Guest not found"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_guest_dossier(
    guest_id: str,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Composite dossier for a guest, aggregating all related data.

    Returns identity, document signed URL, current stay, stay history,
    and activity timeline in one response.
    """
    role = identity.get("role", "")
    if role not in _ALLOWED_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": f"Role '{role}' cannot access guest dossier."},
        )
    tenant_id = identity["tenant_id"]

    try:
        db = client or _get_db()

        # ── 1. Guest identity ──────────────────────────────────────────
        guest_res = (
            db.table("guests")
            .select("*")
            .eq("id", guest_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        rows = guest_res.data or []
        if not rows:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"id": guest_id, "detail": "Guest not found"},
            )
        guest = rows[0]

        # ── 2. Document photo signed URL ───────────────────────────────
        document_photo_signed_url = None
        photo_path = guest.get("document_photo_url")
        if photo_path:
            try:
                signed = db.storage.from_("guest-documents").create_signed_url(
                    photo_path, 900  # 15-minute expiry
                )
                if signed and isinstance(signed, dict):
                    document_photo_signed_url = signed.get("signedURL") or signed.get("signedUrl")
                elif hasattr(signed, "signed_url"):
                    document_photo_signed_url = signed.signed_url
            except Exception as exc:
                logger.warning("dossier: signed URL generation failed (non-blocking): %s", exc)

        # ── 3. All bookings linked to this guest ───────────────────────
        bookings_res = (
            db.table("booking_state")
            .select(
                "booking_id, property_id, status, check_in, check_out, "
                "source, reservation_ref, guest_name, created_at, updated_at"
            )
            .eq("tenant_id", tenant_id)
            .eq("guest_id", guest_id)
            .order("check_in", desc=True)
            .limit(50)
            .execute()
        )
        bookings = bookings_res.data or []

        # Resolve property names in bulk
        prop_ids = list({b.get("property_id") for b in bookings if b.get("property_id")})
        prop_names: dict[str, str] = {}
        if prop_ids:
            try:
                props_res = (
                    db.table("property_config")
                    .select("property_id, display_name")
                    .in_("property_id", prop_ids)
                    .execute()
                )
                for p in (props_res.data or []):
                    prop_names[p["property_id"]] = p.get("display_name") or p["property_id"]
            except Exception:
                pass  # Fall back to property_id

        # ── 4. Settlement data per booking ─────────────────────────────
        booking_ids = [b["booking_id"] for b in bookings]
        deposits_by_booking: dict[str, dict] = {}
        meters_by_booking: dict[str, list] = {}

        if booking_ids:
            # Cash deposits
            try:
                dep_res = (
                    db.table("cash_deposits")
                    .select("*")
                    .eq("tenant_id", tenant_id)
                    .in_("booking_id", booking_ids)
                    .order("created_at", desc=True)
                    .execute()
                )
                for d in (dep_res.data or []):
                    bid = d.get("booking_id")
                    if bid and bid not in deposits_by_booking:
                        deposits_by_booking[bid] = _serialize_deposit(d)
            except Exception as exc:
                logger.warning("dossier: deposits fetch failed: %s", exc)

            # Electricity meter readings
            try:
                meter_res = (
                    db.table("electricity_meter_readings")
                    .select("*")
                    .eq("tenant_id", tenant_id)
                    .in_("booking_id", booking_ids)
                    .order("created_at", desc=True)
                    .execute()
                )
                for m in (meter_res.data or []):
                    bid = m.get("booking_id")
                    if bid:
                        if bid not in meters_by_booking:
                            meters_by_booking[bid] = []
                        meters_by_booking[bid].append(_serialize_meter(m))
            except Exception as exc:
                logger.warning("dossier: meters fetch failed: %s", exc)

        # ── 5. Build stay records ──────────────────────────────────────
        active_statuses = {"InStay", "Confirmed", "CheckedIn"}
        current_stay = None
        stay_history = []

        for b in bookings:
            bid = b["booking_id"]
            pid = b.get("property_id", "")
            stay = {
                "booking_id": bid,
                "property_id": pid,
                "property_name": prop_names.get(pid, pid),
                "check_in": b.get("check_in"),
                "check_out": b.get("check_out"),
                "status": b.get("status"),
                "source": b.get("source"),
                "reservation_ref": b.get("reservation_ref"),
                "guest_name": b.get("guest_name"),
                "created_at": b.get("created_at"),
                "settlement": {
                    "deposit": deposits_by_booking.get(bid),
                    "meter_readings": meters_by_booking.get(bid, []),
                },
            }

            if b.get("status") in active_statuses and current_stay is None:
                current_stay = stay
            else:
                stay_history.append(stay)

        # ── 6. Activity trail (audit events) ───────────────────────────
        activity = []
        try:
            audit_res = (
                db.table("admin_audit_log")
                .select("action, performed_at, actor_id, details, entity_type, entity_id")
                .eq("tenant_id", tenant_id)
                .eq("entity_type", "guest")
                .eq("entity_id", guest_id)
                .order("performed_at", desc=True)
                .limit(50)
                .execute()
            )
            activity = [
                {
                    "action": a.get("action"),
                    "performed_at": a.get("performed_at"),
                    "actor_id": a.get("actor_id"),
                    "details": a.get("details"),
                }
                for a in (audit_res.data or [])
            ]
        except Exception as exc:
            logger.warning("dossier: audit fetch failed: %s", exc)

        # Also fetch booking-level audit events (deposit, meter, checkin)
        if booking_ids:
            try:
                booking_audit_res = (
                    db.table("admin_audit_log")
                    .select("action, performed_at, actor_id, details, entity_type, entity_id")
                    .eq("tenant_id", tenant_id)
                    .in_("entity_id", booking_ids)
                    .in_("action", [
                        "deposit_collected_at_checkin",
                        "meter_opening_recorded",
                        "checkin_completed",
                        "guest_identity_saved",
                    ])
                    .order("performed_at", desc=True)
                    .limit(50)
                    .execute()
                )
                activity.extend([
                    {
                        "action": a.get("action"),
                        "performed_at": a.get("performed_at"),
                        "actor_id": a.get("actor_id"),
                        "details": a.get("details"),
                    }
                    for a in (booking_audit_res.data or [])
                ])
                # Sort combined activity by performed_at descending
                activity.sort(
                    key=lambda x: x.get("performed_at") or "", reverse=True
                )
            except Exception:
                pass

        # ── 7. Compose response ────────────────────────────────────────
        return JSONResponse(status_code=200, content={
            "guest": _serialize_guest(guest),
            "document_photo_signed_url": document_photo_signed_url,
            "current_stay": current_stay,
            "stay_history": stay_history,
            "activity": activity[:50],  # cap at 50
        })

    except Exception as exc:
        logger.exception("GET /guests/%s/dossier error: %s", guest_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def _serialize_guest(row: dict) -> dict:
    return {
        "id":                  row.get("id"),
        "tenant_id":           row.get("tenant_id"),
        "full_name":           row.get("full_name"),
        "email":               row.get("email"),
        "phone":               row.get("phone"),
        "nationality":         row.get("nationality"),
        "passport_no":         row.get("passport_no"),
        "notes":               row.get("notes"),
        "document_type":       row.get("document_type"),
        "passport_expiry":     row.get("passport_expiry"),
        "date_of_birth":       row.get("date_of_birth"),
        "document_photo_url":  row.get("document_photo_url"),
        "whatsapp":            row.get("whatsapp"),
        "line_id":             row.get("line_id"),
        "telegram":            row.get("telegram"),
        "preferred_channel":   row.get("preferred_channel"),
        "created_at":          row.get("created_at"),
        "updated_at":          row.get("updated_at"),
    }


def _serialize_deposit(row: dict) -> dict:
    return {
        "id":             row.get("id"),
        "booking_id":     row.get("booking_id"),
        "amount":         row.get("amount"),
        "currency":       row.get("currency", "THB"),
        "status":         row.get("status"),
        "collected_by":   row.get("collected_by"),
        "collected_at":   row.get("collected_at"),
        "notes":          row.get("notes"),
        "refund_amount":  row.get("refund_amount"),
    }


def _serialize_meter(row: dict) -> dict:
    return {
        "id":              row.get("id"),
        "booking_id":      row.get("booking_id"),
        "reading_type":    row.get("reading_type"),
        "meter_value":     row.get("meter_value"),
        "meter_unit":      row.get("meter_unit", "kWh"),
        "meter_photo_url": row.get("meter_photo_url"),
        "recorded_by":     row.get("recorded_by"),
        "recorded_at":     row.get("recorded_at"),
        "notes":           row.get("notes"),
    }
