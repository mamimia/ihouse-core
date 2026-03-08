from __future__ import annotations

import os
from typing import Any, Optional

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


def get_booking_status(
    booking_id: str,
    client: Any = None,
) -> Optional[str]:
    """
    Read the lifecycle status of a booking from booking_state.

    Returns:
        'active'    — booking exists and is not canceled
        'canceled'  — booking was canceled
        None        — booking_id not found in booking_state

    Read-only. Never writes. Never called inside the ingestion path.

    CRITICAL CONSTRAINT:
        This function must ONLY be used in:
        - amendment pre-validation (future)
        - operator tooling and observability

        It must NEVER be called inside the OTA ingestion adapter path
        (process_ota_event, skills, adapters, pipeline).
        Adapters must not read booking_state.
    """
    if client is None:
        client = _get_client()

    rows = (
        client.table("booking_state")
        .select("booking_id, status")
        .eq("booking_id", booking_id)
        .execute()
    )

    if not rows.data:
        return None

    return rows.data[0].get("status")
