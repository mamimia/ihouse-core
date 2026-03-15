"""
Phase 493 — Booking Write Operations Service

Provides mutation operations for bookings from the frontend:
- Create booking manually (non-OTA)
- Update booking dates/status
- Cancel booking

All writes go through event_log (event-sourced) and update booking_state.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("ihouse.booking_writer")


def _get_db():
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def create_manual_booking(
    db: Any,
    tenant_id: str,
    property_id: str,
    check_in: str,
    check_out: str,
    guest_name: str = "",
    guest_email: str = "",
    source: str = "manual",
    notes: str = "",
) -> Dict[str, Any]:
    """
    Create a booking manually (not from OTA sync).

    Writes to event_log as BOOKING_CREATED and updates booking_state.

    Returns:
        Created booking dict.
    """
    booking_id = f"manual_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    # Write event
    event_payload = {
        "booking_id": booking_id,
        "property_id": property_id,
        "tenant_id": tenant_id,
        "source": source,
        "check_in": check_in,
        "check_out": check_out,
        "guest_name": guest_name,
        "guest_email": guest_email,
        "notes": notes,
        "raw_payload": {
            "guest": {"name": guest_name, "email": guest_email},
        },
    }

    try:
        db.table("event_log").insert({
            "event_id": str(uuid.uuid4()),
            "kind": "BOOKING_CREATED",
            "occurred_at": now.isoformat(),
            "tenant_id": tenant_id,
            "payload_json": event_payload,
        }).execute()
    except Exception as exc:
        logger.warning("create_manual_booking: event_log write failed: %s", exc)

    # Write to booking_state
    booking_row = {
        "booking_id": booking_id,
        "property_id": property_id,
        "tenant_id": tenant_id,
        "source": source,
        "status": "active",
        "check_in": check_in,
        "check_out": check_out,
    }

    try:
        result = db.table("booking_state").insert(booking_row).execute()
        saved = result.data[0] if result.data else booking_row
    except Exception as exc:
        logger.warning("create_manual_booking: booking_state write failed: %s", exc)
        saved = booking_row

    # Extract guest profile
    try:
        from adapters.ota.guest_profile_extractor import extract_guest_profile
        profile = extract_guest_profile(source, event_payload.get("raw_payload", {}))
        if not profile.is_empty():
            db.table("guest_profile").upsert(
                {
                    "booking_id": booking_id,
                    "tenant_id": tenant_id,
                    **profile.to_dict(),
                },
                on_conflict="booking_id,tenant_id",
            ).execute()
    except Exception:
        pass

    return saved


def cancel_booking(
    db: Any,
    tenant_id: str,
    booking_id: str,
    reason: str = "",
) -> Dict[str, Any]:
    """
    Cancel a booking. Updates booking_state and writes BOOKING_CANCELED event.
    """
    now = datetime.now(timezone.utc)

    # Write cancellation event
    try:
        db.table("event_log").insert({
            "event_id": str(uuid.uuid4()),
            "kind": "BOOKING_CANCELED",
            "occurred_at": now.isoformat(),
            "tenant_id": tenant_id,
            "payload_json": {
                "booking_id": booking_id,
                "tenant_id": tenant_id,
                "reason": reason,
            },
        }).execute()
    except Exception as exc:
        logger.warning("cancel_booking: event_log write failed: %s", exc)

    # Update booking_state
    try:
        result = (
            db.table("booking_state")
            .update({
                "status": "canceled",
            })
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        return result.data[0] if result.data else {"booking_id": booking_id, "status": "canceled"}
    except Exception as exc:
        logger.warning("cancel_booking: booking_state update failed: %s", exc)
        return {"booking_id": booking_id, "status": "canceled", "error": str(exc)}


def update_booking_dates(
    db: Any,
    tenant_id: str,
    booking_id: str,
    check_in: str,
    check_out: str,
) -> Dict[str, Any]:
    """
    Update booking dates. Writes BOOKING_AMENDED event and updates booking_state.
    """
    now = datetime.now(timezone.utc)

    try:
        db.table("event_log").insert({
            "event_id": str(uuid.uuid4()),
            "kind": "BOOKING_AMENDED",
            "occurred_at": now.isoformat(),
            "tenant_id": tenant_id,
            "payload_json": {
                "booking_id": booking_id,
                "tenant_id": tenant_id,
                "check_in": check_in,
                "check_out": check_out,
            },
        }).execute()
    except Exception as exc:
        logger.warning("update_booking_dates: event_log write failed: %s", exc)

    try:
        result = (
            db.table("booking_state")
            .update({
                "check_in": check_in,
                "check_out": check_out,
                "canonical_check_in": check_in,
                "canonical_check_out": check_out,
            })
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        return result.data[0] if result.data else {"booking_id": booking_id}
    except Exception as exc:
        logger.warning("update_booking_dates: update failed: %s", exc)
        return {"booking_id": booking_id, "error": str(exc)}
