"""
Phase 140 — Booking Date Lookup

Fetches check_in / check_out from booking_state for use in iCal VEVENT
DTSTART / DTEND. Returns None for both fields if the row is not found or
if any DB error occurs (fail-safe — callers fall back to placeholder dates).

Design:
  - Read-only SELECT on booking_state — never writes anything.
  - Tenant-isolated: always filters by tenant_id.
  - Always called from the outbound_executor_router, not the adapter.
    This keeps adapters pure/testable without DB access.

Returned date strings are in iCal compact format: YYYYMMDD
(e.g. "20260301"). booking_state stores dates as ISO 8601 (YYYY-MM-DD).
"""
from __future__ import annotations

import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def fetch_booking_dates(
    booking_id: str,
    tenant_id: str,
    *,
    client: object | None = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Return (check_in_ical, check_out_ical) for the given booking.

    Both values are compact iCal date strings (YYYYMMDD).
    Returns (None, None) on any error or missing row.

    Parameters
    ----------
    booking_id : str
    tenant_id  : str
    client     : Supabase client (injectable for tests). If None, the real
                 Supabase client is created from environment variables.
    """
    try:
        if client is None:
            from supabase import create_client  # type: ignore[import]
            sb = create_client(
                os.environ["SUPABASE_URL"],
                os.environ["SUPABASE_SERVICE_ROLE_KEY"],
            )
        else:
            sb = client  # type: ignore[assignment]

        result = (
            sb.table("booking_state")
            .select("check_in, check_out")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            logger.warning(
                "fetch_booking_dates: booking_id=%s not found for tenant=%s",
                booking_id, tenant_id,
            )
            return None, None

        row = rows[0]
        raw_in  = row.get("check_in")
        raw_out = row.get("check_out")

        def _to_ical(iso: object) -> Optional[str]:
            if not iso:
                return None
            return str(iso).replace("-", "")[:8]

        return _to_ical(raw_in), _to_ical(raw_out)

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "fetch_booking_dates: failed for booking_id=%s: %s",
            booking_id, exc,
        )
        return None, None
