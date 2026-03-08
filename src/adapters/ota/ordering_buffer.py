from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

try:
    from supabase import create_client
except ImportError:  # pragma: no cover
    create_client = None  # type: ignore[assignment,misc]


def _get_client() -> Any:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    if create_client is None:  # pragma: no cover
        raise EnvironmentError("supabase-py is not installed")
    return create_client(url, key)


def buffer_event(
    dlq_row_id: Optional[int],
    booking_id: str,
    event_type: str,
    client: Any = None,
) -> int:
    """
    Write a row to ota_ordering_buffer, marking an event as ordering-blocked.

    Called when an event arrives before its corresponding BOOKING_CREATED
    (BOOKING_NOT_FOUND rejection). The event is buffered here and will be
    automatically replayed by ordering_trigger when BOOKING_CREATED is APPLIED.

    Args:
        dlq_row_id: FK to ota_dead_letter.id (Optional — None if DLQ write was not possible)
        booking_id: the booking_id the event is waiting for
        event_type: e.g. BOOKING_CANCELED
        client:     optional injected Supabase client

    Returns:
        int — the new buffer row id
    """
    if client is None:
        client = _get_client()

    insert_data: Dict[str, Any] = {
        "booking_id": booking_id,
        "event_type": event_type,
        "status": "waiting",
    }
    if dlq_row_id is not None:
        insert_data["dlq_row_id"] = dlq_row_id

    result = client.table("ota_ordering_buffer").insert(insert_data).execute()

    return result.data[0]["id"]


def get_buffered_events(
    booking_id: str,
    client: Any = None,
) -> List[Dict[str, Any]]:
    """
    Return all 'waiting' ordering buffer rows for a given booking_id.

    These are events that arrived before BOOKING_CREATED and are ready
    to be replayed now that the booking exists.

    Args:
        booking_id: the booking_id to look up
        client:     optional injected Supabase client

    Returns:
        list of buffer rows (dicts) with status='waiting'
    """
    if client is None:
        client = _get_client()

    result = (
        client.table("ota_ordering_buffer")
        .select("*")
        .eq("booking_id", booking_id)
        .eq("status", "waiting")
        .execute()
    )

    return result.data or []


def mark_replayed(
    buffer_id: int,
    client: Any = None,
) -> None:
    """
    Mark a buffer row as 'replayed' after successful replay.

    Args:
        buffer_id: the ota_ordering_buffer.id to update
        client:    optional injected Supabase client
    """
    if client is None:
        client = _get_client()

    client.table("ota_ordering_buffer").update({
        "status": "replayed",
    }).eq("id", buffer_id).execute()
