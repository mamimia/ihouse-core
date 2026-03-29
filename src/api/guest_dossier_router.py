"""
Phase 972 — Guest Dossier Composite API (upgraded Phase 976)
=============================================================

Single composite endpoint that returns everything needed to render the
Guest Dossier UI in one round-trip:

  GET /guests/{guest_id}/dossier

Phase 976 additions:
  - checkin_record per stay: photos (booking_checkin_photos),
    checked_in_at (booking_state), worker (from audit log)
  - portal state per stay: URL + qr_generated + issued_at (guest_tokens)
  - checkout_record per stay: from booking_state (checkout fields)

Returns:
  - Full guest identity record (including document fields)
  - Signed URL for passport/document photo (15-min expiry)
  - Current active stay (if any): booking + checkin_record + portal + settlement
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


def _serialize_settlement_record(sr: dict) -> dict:
    """Flatten a booking_settlement_records row for API output."""
    return {
        "id":                          sr.get("id"),
        "status":                      sr.get("status"),
        "deposit_held":                _safe_float(sr.get("deposit_held")),
        "deposit_currency":            sr.get("deposit_currency"),
        "opening_meter_value":         _safe_float(sr.get("opening_meter_value")),
        "closing_meter_value":         _safe_float(sr.get("closing_meter_value")),
        "electricity_kwh_used":        _safe_float(sr.get("electricity_kwh_used")),
        "electricity_rate_kwh":        _safe_float(sr.get("electricity_rate_kwh")),
        "electricity_charged":         _safe_float(sr.get("electricity_charged")),
        "electricity_currency":        sr.get("electricity_currency"),
        "damage_deductions_total":     _safe_float(sr.get("damage_deductions_total")),
        "miscellaneous_deductions_total": _safe_float(sr.get("miscellaneous_deductions_total")),
        "total_deductions":            _safe_float(sr.get("total_deductions")),
        "refund_amount":               _safe_float(sr.get("refund_amount")),
        "retained_amount":             _safe_float(sr.get("retained_amount")),
        "finalized_by":                sr.get("finalized_by"),
        "finalized_at":                sr.get("finalized_at"),
        "created_at":                  sr.get("created_at"),
    }


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# GET /guests/{guest_id}/dossier
# ---------------------------------------------------------------------------

@router.get(
    "/guests/{guest_id}/dossier",
    summary="Full guest dossier: identity + stays + checkin_record + portal + settlement + activity (Phase 972/976)",
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

    Returns identity, document signed URL, current stay (with checkin record,
    portal state, settlement), stay history, and activity timeline.
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
                "booking_source, reservation_ref, guest_name, checked_in_at, "
                "checked_out_at, updated_at_ms, "
                # Phase 1002: Full early checkout context for dossier
                "early_checkout_approved, early_checkout_approved_by, "
                "early_checkout_approved_at, early_checkout_date, "
                "early_checkout_effective_at, early_checkout_status, "
                "early_checkout_reason, early_checkout_requested_at, "
                "early_checkout_request_source"
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
                    db.table("properties")
                    .select("property_id, display_name")
                    .in_("property_id", prop_ids)
                    .execute()
                )
                for p in (props_res.data or []):
                    prop_names[p["property_id"]] = p.get("display_name") or p["property_id"]
            except Exception:
                pass

        # ── 4. Settlement data per booking ─────────────────────────────
        booking_ids = [b["booking_id"] for b in bookings]
        deposits_by_booking: dict[str, dict] = {}
        meters_by_booking: dict[str, list] = {}

        if booking_ids:
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

        # ── 5. Check-in photos per booking ─────────────────────────────
        photos_by_booking: dict[str, list] = {}
        if booking_ids:
            try:
                photos_res = (
                    db.table("booking_checkin_photos")
                    .select("*")
                    .eq("tenant_id", tenant_id)
                    .in_("booking_id", booking_ids)
                    .order("captured_at", desc=False)
                    .execute()
                )
                for ph in (photos_res.data or []):
                    bid = ph.get("booking_id")
                    if bid:
                        if bid not in photos_by_booking:
                            photos_by_booking[bid] = []
                        photos_by_booking[bid].append({
                            "id":           ph.get("id"),
                            "room_label":   ph.get("room_label"),
                            "purpose":      ph.get("purpose"),
                            "storage_path": ph.get("storage_path"),
                            "captured_at":  ph.get("captured_at"),
                            "uploaded_by":  ph.get("uploaded_by"),
                            "notes":        ph.get("notes"),
                        })
            except Exception as exc:
                logger.warning("dossier: photos fetch failed: %s", exc)

        # ── 5b. Checkout photos from checkout_photos table (Phase 692 uploads) ──
        #     These are real uploaded files stored in Supabase Storage.
        #     Merge them into photos_by_booking with purpose=checkout_condition.
        if booking_ids:
            try:
                co_photos_res = (
                    db.table("checkout_photos")
                    .select("id, booking_id, room_label, photo_url, notes, taken_by, created_at")
                    .in_("booking_id", booking_ids)
                    .order("created_at", desc=False)
                    .execute()
                )
                for ph in (co_photos_res.data or []):
                    bid = ph.get("booking_id")
                    if bid:
                        if bid not in photos_by_booking:
                            photos_by_booking[bid] = []
                        photos_by_booking[bid].append({
                            "id":           ph.get("id"),
                            "room_label":   ph.get("room_label"),
                            "purpose":      "checkout_condition",
                            "storage_path": ph.get("photo_url"),
                            "captured_at":  ph.get("created_at"),
                            "uploaded_by":  ph.get("taken_by"),
                            "notes":        ph.get("notes"),
                        })
            except Exception as exc:
                logger.warning("dossier: checkout_photos fetch failed: %s", exc)

        # ── 6. Portal / guest token per booking ────────────────────────
        portal_by_booking: dict[str, dict] = {}
        if booking_ids:
            try:
                # portal URL is in guest_qr_tokens (not guest_tokens)
                for bid in booking_ids:
                    qr_res = (
                        db.table("guest_qr_tokens")
                        .select("portal_url, created_at, expires_at")
                        .eq("booking_id", bid)
                        .eq("tenant_id", tenant_id)
                        .order("created_at", desc=True)
                        .limit(1)
                        .execute()
                    )
                    if qr_res.data:
                        t = qr_res.data[0]
                        portal_by_booking[bid] = {
                            "qr_generated": True,
                            "portal_url":   t.get("portal_url"),
                            "issued_at":    t.get("created_at"),
                            "expires_at":   t.get("expires_at"),
                        }
            except Exception as exc:
                logger.warning("dossier: guest_qr_tokens fetch failed: %s", exc)

        # ── 7. Fetch checkin worker from audit_events ─────────────────
        checkin_worker_by_booking: dict[str, str] = {}
        checkin_at_from_audit: dict[str, str] = {}
        if booking_ids:
            try:
                checkin_audit = (
                    db.table("audit_events")
                    .select("entity_id, actor_id, occurred_at")
                    .eq("tenant_id", tenant_id)
                    .in_("entity_id", booking_ids)
                    .eq("action", "booking.checkin")
                    .order("occurred_at", desc=True)
                    .execute()
                )
                for evt in (checkin_audit.data or []):
                    bid = evt.get("entity_id")
                    if bid and bid not in checkin_worker_by_booking:
                        checkin_worker_by_booking[bid] = evt.get("actor_id", "")
                        checkin_at_from_audit[bid] = evt.get("occurred_at", "")
            except Exception as exc:
                logger.warning("dossier: checkin worker fetch failed: %s", exc)

        # ── 7b. Checkout worker from audit_events ─────────────────────
        checkout_worker_by_booking: dict[str, str] = {}
        if booking_ids:
            try:
                checkout_audit = (
                    db.table("audit_events")
                    .select("entity_id, actor_id")
                    .eq("tenant_id", tenant_id)
                    .in_("entity_id", booking_ids)
                    .eq("action", "booking.checkout")
                    .order("occurred_at", desc=True)
                    .execute()
                )
                for evt in (checkout_audit.data or []):
                    bid = evt.get("entity_id")
                    if bid and bid not in checkout_worker_by_booking:
                        checkout_worker_by_booking[bid] = evt.get("actor_id", "")
            except Exception as exc:
                logger.warning("dossier: checkout worker fetch failed: %s", exc)

        # ── 7c. Settlement records per booking ────────────────────────
        settlement_by_booking: dict[str, dict] = {}
        if booking_ids:
            try:
                sr_res = (
                    db.table("booking_settlement_records")
                    .select("*")
                    .eq("tenant_id", tenant_id)
                    .in_("booking_id", booking_ids)
                    .neq("status", "voided")
                    .order("created_at", desc=True)
                    .execute()
                )
                for sr in (sr_res.data or []):
                    bid = sr.get("booking_id")
                    if bid and bid not in settlement_by_booking:
                        settlement_by_booking[bid] = _serialize_settlement_record(sr)
            except Exception as exc:
                logger.warning("dossier: settlement records fetch failed: %s", exc)

        # ── 8. Build stay records (date-aware classification) ────────
        #
        # A stay is "current" only when ALL of the following hold:
        #   1. The booking status indicates it is active (checked-in, confirmed, etc.)
        #   2. The checkout date is today or in the future  (date-wall guard)
        #   3. No current_stay has been picked yet  (first match wins)
        #
        # If a stay has an "active" status but its checkout date is in the
        # past (stale / DB not updated), we classify it as history and
        # normalise its status to "completed" so the UI renders it correctly.

        active_statuses = {"InStay", "CheckedIn", "checked_in", "active"}
        # Confirmed = future / upcoming, not yet checked-in
        upcoming_statuses = {"Confirmed", "confirmed", "booked", "approved"}

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")  # YYYY-MM-DD

        def _checkout_is_future_or_today(checkout: str | None) -> bool:
            """Return True when checkout >= today (i.e. stay is not over yet)."""
            if not checkout:
                return True  # unknown — give benefit of the doubt
            try:
                co = checkout[:10]  # accept both 'YYYY-MM-DD' and ISO timestamps
                return co >= today_str
            except Exception:
                return True

        def _normalise_status(raw_status: str | None, checkout: str | None) -> str:
            """Return a clean, unambiguous lifecycle label."""
            s = (raw_status or "").lower()
            # Past stay that was never marked completed by the system
            if s in {"active", "instay", "checkedin", "checked_in"} and not _checkout_is_future_or_today(checkout):
                return "completed"
            # Map DB variants to canonical labels
            mapping = {
                "instay":     "checked_in",
                "checkedin":  "checked_in",
                "active":     "checked_in",
                "confirmed":  "Confirmed",
                "booked":     "Confirmed",
                "approved":   "Confirmed",
            }
            return mapping.get(s, raw_status or "unknown")

        current_stay = None
        stay_history = []

        for b in bookings:
            bid = b["booking_id"]
            pid = b.get("property_id", "")

            # Separate photos by purpose
            all_photos = photos_by_booking.get(bid, [])
            walkthrough_photos = [p for p in all_photos if p.get("purpose") == "walkthrough"]
            meter_photos = [p for p in all_photos if p.get("purpose") == "meter"]
            checkout_photos = [p for p in all_photos if (p.get("purpose") or "").startswith("checkout_")]

            meters = meters_by_booking.get(bid, [])
            opening_meter = next((m for m in meters if m.get("reading_type") == "opening"), None)
            closing_meter = next((m for m in meters if m.get("reading_type") == "closing"), None)

            # checked_in_at: prefer booking_state column, fall back to audit_events timestamp
            checked_in_at = b.get("checked_in_at") or checkin_at_from_audit.get(bid)

            checkin_record = {
                "checked_in_at":      checked_in_at,
                "checked_in_by":      checkin_worker_by_booking.get(bid),
                "walkthrough_photos": walkthrough_photos,
                "meter_photos":       meter_photos,
                "opening_meter":      opening_meter,
            }

            # Phase 989d / Phase 1002: Rich checkout record with settlement, photos, worker, and early checkout context
            sr = settlement_by_booking.get(bid)
            checkout_record = None
            checked_out_at = b.get("checked_out_at")
            if checked_out_at or (b.get("status") or "").lower() == "checked_out":
                # Phase 1002: Assemble full early checkout sub-object if applicable
                early_checkout_record = None
                if b.get("early_checkout_approved"):
                    early_checkout_record = {
                        "is_early_checkout":        True,
                        "early_checkout_status":    b.get("early_checkout_status"),
                        "original_checkout_date":   b.get("check_out"),
                        "effective_checkout_date":  b.get("early_checkout_date"),
                        "effective_checkout_at":    b.get("early_checkout_effective_at"),
                        "approved_by":              b.get("early_checkout_approved_by"),
                        "approved_at":              b.get("early_checkout_approved_at"),
                        "reason":                   b.get("early_checkout_reason"),
                        "requested_at":             b.get("early_checkout_requested_at"),
                        "request_source":           b.get("early_checkout_request_source"),
                    }
                    # Also pull approved_by from settlement record as a fallback
                    if sr and not early_checkout_record["approved_by"]:
                        early_checkout_record["approved_by"] = sr.get("early_checkout_approved_by")

                checkout_record = {
                    "checked_out_at":    checked_out_at,
                    "checked_out_by":    checkout_worker_by_booking.get(bid),
                    "closing_meter":     closing_meter,
                    "checkout_photos":   checkout_photos,
                    "inspection_notes":  next((p.get("notes") for p in checkout_photos
                                               if p.get("purpose") == "checkout_inspection" and p.get("notes")), None),
                    "settlement":        sr,
                    "early_checkout":    early_checkout_record,
                }

            raw_status = b.get("status")
            checkout_date = b.get("check_out")
            normalised_status = _normalise_status(raw_status, checkout_date)

            stay = {
                "booking_id":      bid,
                "property_id":     pid,
                "property_name":   prop_names.get(pid, pid),
                "check_in":        b.get("check_in"),
                "check_out":       checkout_date,
                "status":          normalised_status,
                "source":          b.get("booking_source") or b.get("source"),
                "reservation_ref": b.get("reservation_ref"),
                "guest_name":      b.get("guest_name"),
                "created_at":      b.get("created_at") or b.get("updated_at_ms"),
                "checkin_record":  checkin_record,
                "checkout_record": checkout_record,
                "portal":          portal_by_booking.get(bid, {"qr_generated": False, "portal_url": None}),
                "settlement": {
                    "deposit":        deposits_by_booking.get(bid),
                    "meter_readings": meters,
                    "settlement_record": sr,
                },
            }

            # A booking is "current" only if status is active AND checkout is future/today
            raw_s_lower = (raw_status or "").lower()
            is_genuinely_active = (
                raw_s_lower in {"instay", "checkedin", "checked_in", "active"}
                and _checkout_is_future_or_today(checkout_date)
            )
            is_upcoming = raw_s_lower in {"confirmed", "booked", "approved"}

            if (is_genuinely_active or is_upcoming) and current_stay is None:
                current_stay = stay
            else:
                stay_history.append(stay)

        # ── 9. Activity trail — merge admin_audit_log + audit_events ───
        activity: list[dict] = []

        # 9a. admin_audit_log — guest-level events
        try:
            aal_res = (
                db.table("admin_audit_log")
                .select("action, performed_at, actor_id, details, entity_type, entity_id")
                .eq("tenant_id", tenant_id)
                .eq("entity_type", "guest")
                .eq("entity_id", guest_id)
                .order("performed_at", desc=True)
                .limit(50)
                .execute()
            )
            for a in (aal_res.data or []):
                activity.append({
                    "action":       a.get("action"),
                    "performed_at": a.get("performed_at"),
                    "actor_id":     a.get("actor_id"),
                    "details":      a.get("details"),
                    "entity_type":  a.get("entity_type"),
                    "entity_id":    a.get("entity_id"),
                })
        except Exception as exc:
            logger.warning("dossier: admin_audit_log guest fetch failed: %s", exc)

        # 9b. audit_events — guest-level events (GUEST_IDENTITY_SAVED etc.)
        try:
            ae_guest = (
                db.table("audit_events")
                .select("action, occurred_at, actor_id, payload, entity_type, entity_id")
                .eq("tenant_id", tenant_id)
                .eq("entity_type", "guest")
                .eq("entity_id", guest_id)
                .order("occurred_at", desc=True)
                .limit(50)
                .execute()
            )
            for a in (ae_guest.data or []):
                activity.append({
                    "action":       a.get("action"),
                    "performed_at": a.get("occurred_at"),
                    "actor_id":     a.get("actor_id"),
                    "details":      a.get("payload"),
                    "entity_type":  a.get("entity_type"),
                    "entity_id":    a.get("entity_id"),
                })
        except Exception as exc:
            logger.warning("dossier: audit_events guest fetch failed: %s", exc)

        # 9c. audit_events — booking-level events (booking.checkin, etc.)
        if booking_ids:
            try:
                ae_booking = (
                    db.table("audit_events")
                    .select("action, occurred_at, actor_id, payload, entity_type, entity_id")
                    .eq("tenant_id", tenant_id)
                    .eq("entity_type", "booking")
                    .in_("entity_id", booking_ids)
                    .order("occurred_at", desc=True)
                    .limit(50)
                    .execute()
                )
                for a in (ae_booking.data or []):
                    activity.append({
                        "action":       a.get("action"),
                        "performed_at": a.get("occurred_at"),
                        "actor_id":     a.get("actor_id"),
                        "details":      a.get("payload"),
                        "entity_type":  a.get("entity_type"),
                        "entity_id":    a.get("entity_id"),
                    })
            except Exception:
                pass

        # 9d. Phase 1002: admin_audit_log — early checkout lifecycle events per booking
        # These are written by early_checkout_router for request, approve, revoke;
        # and by booking_checkin_router for the completed checkout with early context.
        if booking_ids:
            try:
                ec_events = (
                    db.table("admin_audit_log")
                    .select("action, performed_at, actor_id, details, entity_type, entity_id")
                    .eq("tenant_id", tenant_id)
                    .eq("entity_type", "booking")
                    .in_("entity_id", booking_ids)
                    .in_("action", [
                        "early_checkout.request_received",
                        "early_checkout.approved",
                        "early_checkout.revoked",
                        "booking.checkout",          # includes early_checkout context in details
                    ])
                    .order("performed_at", desc=True)
                    .limit(50)
                    .execute()
                )
                for a in (ec_events.data or []):
                    activity.append({
                        "action":       a.get("action"),
                        "performed_at": a.get("performed_at"),
                        "actor_id":     a.get("actor_id"),
                        "details":      a.get("details"),
                        "entity_type":  a.get("entity_type"),
                        "entity_id":    a.get("entity_id"),
                    })
            except Exception as exc:
                logger.warning("dossier: early checkout events fetch failed: %s", exc)

        # Deduplicate by (action, performed_at) and sort desc
        seen: set[tuple[str, str]] = set()
        deduped: list[dict] = []
        for ev in activity:
            key = (ev.get("action", ""), ev.get("performed_at", ""))
            if key not in seen:
                seen.add(key)
                deduped.append(ev)
        deduped.sort(key=lambda x: x.get("performed_at") or "", reverse=True)


        # ── 10. Compose response ───────────────────────────────────────
        return JSONResponse(status_code=200, content={
            "guest":                      _serialize_guest(guest),
            "document_photo_signed_url":  document_photo_signed_url,
            "current_stay":               current_stay,
            "stay_history":               stay_history,
            "activity":                   deduped[:50],
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
        "issuing_country":     row.get("issuing_country"),
        "identity_source":     row.get("identity_source"),
        "identity_verified_at": row.get("identity_verified_at"),
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


def _serialize_audit(row: dict) -> dict:
    return {
        "action":       row.get("action"),
        "performed_at": row.get("performed_at"),
        "actor_id":     row.get("actor_id"),
        "details":      row.get("details"),
        "entity_type":  row.get("entity_type"),
        "entity_id":    row.get("entity_id"),
    }
