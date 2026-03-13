"""
Phase 485 — Guest Profile Backfill Service

Scans event_log for BOOKING_CREATED events and retroactively extracts
guest profile data into the guest_profile table.

This fills the gap between 1516 bookings and 0 guest profiles.
Uses the same extract_guest_profile() function as the live pipeline.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger("ihouse.guest_profile_backfill")


def _get_db():
    """Get a Supabase client using service role key."""
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def backfill_guest_profiles(
    *,
    tenant_id: Optional[str] = None,
    batch_size: int = 100,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Backfill guest_profile from event_log BOOKING_CREATED events.

    Args:
        tenant_id: Optional filter — backfill only for this tenant.
        batch_size: Number of events to process per batch.
        dry_run: If True, extract but don't write to Supabase.

    Returns:
        Summary dict with counts: total_events, extracted, skipped, errors.
    """
    from adapters.ota.guest_profile_extractor import extract_guest_profile

    db = _get_db()

    # Fetch all BOOKING_CREATED events from event_log
    query = db.table("event_log").select("event_id, payload_json").eq("kind", "BOOKING_CREATED")
    response = query.execute()
    events = response.data or []

    stats = {
        "total_events": len(events),
        "extracted": 0,
        "skipped_empty": 0,
        "skipped_no_booking_id": 0,
        "errors": 0,
        "dry_run": dry_run,
    }

    upsert_batch = []

    for event in events:
        try:
            payload = event.get("payload_json", {})
            if not isinstance(payload, dict):
                stats["errors"] += 1
                continue

            # Extract provider and booking_id from the event payload
            provider = payload.get("source", payload.get("provider", "unknown"))
            booking_id = payload.get("booking_id", "")
            event_tenant_id = payload.get("tenant_id", tenant_id or "")

            if not booking_id:
                stats["skipped_no_booking_id"] += 1
                continue

            if tenant_id and event_tenant_id != tenant_id:
                continue

            # Use the same extractor as the live pipeline
            # The payload inside event_log is the envelope payload,
            # which may contain the original OTA payload nested
            raw_payload = payload.get("raw_payload", payload)
            profile = extract_guest_profile(provider, raw_payload)

            if profile.is_empty():
                stats["skipped_empty"] += 1
                continue

            upsert_batch.append({
                "booking_id": booking_id,
                "tenant_id": event_tenant_id,
                "guest_name": profile.guest_name,
                "guest_email": profile.guest_email,
                "guest_phone": profile.guest_phone,
                "source": profile.source or provider,
            })
            stats["extracted"] += 1

            # Write in batches
            if len(upsert_batch) >= batch_size and not dry_run:
                _write_batch(db, upsert_batch)
                upsert_batch = []

        except Exception as exc:
            logger.warning("Guest profile backfill error for event %s: %s",
                           event.get("event_id", "?"), exc)
            stats["errors"] += 1

    # Write remaining batch
    if upsert_batch and not dry_run:
        _write_batch(db, upsert_batch)

    logger.info("Guest profile backfill complete: %s", stats)
    return stats


def _write_batch(db, batch):
    """Upsert a batch of guest profiles. Best-effort — errors logged, never raised."""
    try:
        db.table("guest_profile").upsert(
            batch,
            on_conflict="booking_id,tenant_id",
        ).execute()
    except Exception as exc:
        logger.error("Guest profile batch write failed (%d rows): %s", len(batch), exc)
