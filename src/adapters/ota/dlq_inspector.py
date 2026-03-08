from __future__ import annotations

import os
from typing import Any, Dict, List

try:
    from supabase import create_client
except ImportError:  # pragma: no cover
    create_client = None  # type: ignore[assignment,misc]

# Replay result statuses that count as "replayed successfully"
_APPLIED_STATUSES = frozenset({
    "APPLIED",
    "ALREADY_APPLIED",
    "ALREADY_EXISTS",
    "ALREADY_EXISTS_BUSINESS",
})


def _get_client() -> Any:
    """Create and return a Supabase client using environment variables."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    if create_client is None:  # pragma: no cover
        raise EnvironmentError("supabase-py is not installed")
    return create_client(url, key)


def get_pending_count(client: Any = None) -> int:
    """
    Return the number of DLQ rows that have NOT yet been successfully replayed.

    A row is pending if its replay_result is NULL or not in the APPLIED statuses set.

    Read-only. No writes.
    """
    if client is None:
        client = _get_client()

    rows = client.table("ota_dead_letter").select("id, replay_result").execute()
    return sum(
        1 for r in (rows.data or [])
        if r.get("replay_result") not in _APPLIED_STATUSES
    )


def get_replayed_count(client: Any = None) -> int:
    """
    Return the number of DLQ rows that have been successfully replayed.

    Read-only. No writes.
    """
    if client is None:
        client = _get_client()

    rows = client.table("ota_dead_letter").select("id, replay_result").execute()
    return sum(
        1 for r in (rows.data or [])
        if r.get("replay_result") in _APPLIED_STATUSES
    )


def get_rejection_breakdown(client: Any = None) -> List[Dict[str, Any]]:
    """
    Return a list of rejection groups from the ota_dlq_summary view.

    Each entry contains:
      - event_type: str
      - rejection_code: str
      - total: int
      - pending: int
      - replayed: int

    Sorted by pending desc, total desc.
    Read-only. No writes.
    """
    if client is None:
        client = _get_client()

    result = client.table("ota_dlq_summary").select("*").execute()
    return result.data or []
