"""
iCal Normalizer — bookings (landing) → booking_state (canonical)
================================================================

Reads iCal-imported rows from `bookings` table and:
1. Determines semantics: Reserved → observed, Not available → blocked
2. Writes canonical row to `booking_state`
3. Creates synthetic `event_log` entry for audit trail
4. Marks `bookings` row as `imported_to_state`

Call from _parse_ical_bookings (Phase 751) or as scheduled batch.
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _get_db() -> Any:
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def normalize_ical_bookings(
    tenant_id: str,
    property_id: str | None = None,
    client: Any | None = None,
) -> dict:
    """
    Normalize pending iCal rows from `bookings` into `booking_state`.

    Args:
        tenant_id: required
        property_id: optional filter (specific property only)
        client: optional Supabase client (for testing)

    Returns:
        {"observed": int, "blocked": int, "skipped": int, "errors": int}
    """
    db = client if client is not None else _get_db()
    stats = {"observed": 0, "blocked": 0, "skipped": 0, "errors": 0}

    # 1. Read pending iCal rows
    query = (db.table("bookings")
             .select("*")
             .like("booking_id", "ICAL-%")
             .eq("import_status", "pending"))

    if property_id:
        query = query.eq("property_id", property_id)

    result = query.limit(500).execute()
    rows = result.data or []

    if not rows:
        logger.info("ical_normalizer: no pending rows")
        return stats

    now_ms = int(time.time() * 1000)
    now_iso = datetime.now(tz=timezone.utc).isoformat()

    for row in rows:
        bid = row["booking_id"]
        guest_name = row.get("guest_name", "")
        start_date = row.get("start_date", "")
        end_date = row.get("end_date", "")
        external_ref = row.get("external_ref", "")

        # 2. Determine semantics
        if "Not available" in guest_name:
            status = "blocked"
        elif "Reserved" in guest_name:
            status = "observed"
        else:
            status = "observed"  # default for unknown iCal entries

        # 3. Write to booking_state
        try:
            state_json = {
                "guest_name": guest_name,
                "source_type": "ical",
                "source_provider": "ical",
                "source_booking_ref": external_ref,
            }

            db.table("booking_state").upsert({
                "booking_id": bid,
                "tenant_id": tenant_id,
                "property_id": row.get("property_id", ""),
                "reservation_ref": external_ref,
                "source": "ical",
                "source_type": "ical",
                "status": status,
                "check_in": start_date,
                "check_out": end_date,
                "guest_name": guest_name,
                "guest_count": None,
                "total_price": None,
                "currency": None,
                "state_json": state_json,
                "version": 1,
                "updated_at_ms": now_ms,
            }, on_conflict="booking_id").execute()

            # 4. Synthetic event_log entry
            evt_id = hashlib.sha256(f"ICAL_NORM:{bid}:{now_ms}".encode()).hexdigest()[:24]
            try:
                db.table("event_log").insert({
                    "event_id": f"ical-{evt_id}",
                    "kind": "BOOKING_CREATED",
                    "occurred_at": now_iso,
                    "payload_json": {
                        "source": "ical",
                        "booking_id": bid,
                        "property_id": row.get("property_id", ""),
                        "vevent_uid": external_ref,
                        "dtstart": start_date,
                        "dtend": end_date,
                        "summary": guest_name,
                        "normalized_status": status,
                    },
                }).execute()
            except Exception as exc:
                logger.warning("ical_normalizer: event_log insert failed for %s: %s", bid, exc)

            # 5. Mark as imported
            db.table("bookings").update(
                {"import_status": "imported_to_state"}
            ).eq("booking_id", bid).execute()

            if status == "blocked":
                stats["blocked"] += 1
            else:
                stats["observed"] += 1

        except Exception as exc:
            logger.exception("ical_normalizer: failed to normalize %s: %s", bid, exc)
            stats["errors"] += 1

    logger.info(
        "ical_normalizer: done tenant=%s — observed=%d blocked=%d skipped=%d errors=%d",
        tenant_id, stats["observed"], stats["blocked"], stats["skipped"], stats["errors"],
    )
    return stats
