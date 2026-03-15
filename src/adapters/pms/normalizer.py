"""
Phase 810 — PMS Booking Normalizer
====================================

Transforms PMSBooking objects → canonical booking_state + event_log entries.
Same normalization pattern as ical_normalizer, but with full data richness.
"""
from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from adapters.pms.base import PMSBooking, PMSSyncResult

logger = logging.getLogger(__name__)


def normalize_pms_bookings(
    bookings: List[PMSBooking],
    tenant_id: str,
    provider: str,
    property_map: Dict[str, str],  # external_property_id → domaniqo property_id
    db: Any,
) -> PMSSyncResult:
    """
    Normalize PMS bookings into canonical booking_state + event_log.

    Args:
        bookings: list of PMSBooking from adapter
        tenant_id: owning tenant
        provider: 'guesty' | 'hostaway'
        property_map: maps PMS property IDs → Domaniqo property IDs
        db: Supabase client

    Returns:
        PMSSyncResult with counts
    """
    result = PMSSyncResult()
    now_ms = int(time.time() * 1000)
    now_iso = datetime.now(tz=timezone.utc).isoformat()

    for booking in bookings:
        result.bookings_fetched += 1

        # Resolve Domaniqo property_id
        domaniqo_property = property_map.get(booking.property_external_id)
        if not domaniqo_property:
            logger.warning(
                "pms_normalizer: unmapped property %s — skipping booking %s",
                booking.property_external_id, booking.external_id,
            )
            result.errors += 1
            result.error_details.append(f"Unmapped property: {booking.property_external_id}")
            continue

        # Canonical booking_id
        booking_id = f"{provider}_{booking.external_id}"

        # Check if exists (for new vs update count)
        existing = (db.table("booking_state")
                    .select("booking_id, version, status")
                    .eq("booking_id", booking_id)
                    .limit(1)
                    .execute())
        is_update = bool(existing.data)

        if is_update:
            old = existing.data[0]
            old_status = old.get("status")
            new_version = (old.get("version") or 0) + 1
            # Detect cancellation
            if booking.status == "canceled" and old_status != "canceled":
                result.bookings_canceled += 1
                event_kind = "BOOKING_CANCELED"
            else:
                result.bookings_updated += 1
                event_kind = "BOOKING_AMENDED"
        else:
            new_version = 1
            event_kind = "BOOKING_CREATED"
            result.bookings_new += 1

        # Build state_json (non-promoted fields)
        state_json = {
            "guest_email": booking.guest_email,
            "guest_phone": booking.guest_phone,
            "source_type": "pms",
            "source_provider": provider,
            "source_channel": booking.channel or "",
            "source_booking_ref": booking.external_id,
            "channel_commission": booking.commission,
            "net_to_property": booking.net_to_property,
            "special_requests": booking.special_requests,
            "internal_notes": booking.internal_notes,
            "cancellation_policy": booking.cancellation_policy,
        }

        try:
            # Generate event_id
            evt_id = hashlib.sha256(
                f"PMS:{provider}:{booking_id}:{now_ms}".encode()
            ).hexdigest()[:24]
            full_event_id = f"pms-{evt_id}"

            # 1. Write to event_log FIRST (booking_state.last_event_id FK requires this)
            db.table("event_log").insert({
                "event_id": full_event_id,
                "kind": event_kind,
                "occurred_at": now_iso,
                "payload_json": {
                    "source": provider,
                    "source_type": "pms",
                    "booking_id": booking_id,
                    "property_id": domaniqo_property,
                    "external_id": booking.external_id,
                    "status": booking.status,
                    "check_in": booking.check_in,
                    "check_out": booking.check_out,
                    "guest_name": booking.guest_name,
                    "total_price": booking.total_price,
                    "currency": booking.currency,
                    "channel": booking.channel,
                    "raw_payload_keys": list(booking.raw.keys())[:20],
                },
            }).execute()

            # 2. Write to booking_state (canonical) — FK on last_event_id now satisfied
            db.table("booking_state").upsert({
                "booking_id": booking_id,
                "tenant_id": tenant_id,
                "property_id": domaniqo_property,
                "reservation_ref": booking.external_id,
                "source": provider,
                "source_type": "pms",
                "status": booking.status,
                "check_in": booking.check_in,
                "check_out": booking.check_out,
                "guest_name": booking.guest_name,
                "guest_count": booking.guest_count,
                "total_price": booking.total_price,
                "currency": booking.currency,
                "state_json": state_json,
                "version": new_version,
                "last_event_id": full_event_id,
                "updated_at_ms": now_ms,
            }, on_conflict="booking_id").execute()

        except Exception as exc:
            logger.exception("pms_normalizer: failed %s: %s", booking_id, exc)
            result.errors += 1
            result.error_details.append(f"{booking_id}: {str(exc)[:200]}")

    logger.info(
        "pms_normalizer: provider=%s fetched=%d new=%d updated=%d canceled=%d errors=%d",
        provider, result.bookings_fetched, result.bookings_new,
        result.bookings_updated, result.bookings_canceled, result.errors,
    )
    return result
