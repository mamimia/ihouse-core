"""
idempotency_monitor.py -- Phase 79

Pure read-only module that collects idempotency health metrics from
ota_dead_letter and ota_ordering_buffer.

Zero side effects. Never writes. Never raises on missing data.

Public API:
    IDEMPOTENCY_REJECTION_CODES  -- frozenset of known idempotency rejection codes
    IdempotencyReport            -- frozen dataclass with all metrics
    collect_idempotency_report() -- collect and return the report
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from supabase import create_client
except ImportError:  # pragma: no cover
    create_client = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

IDEMPOTENCY_REJECTION_CODES: frozenset = frozenset({
    "ALREADY_APPLIED",
    "ALREADY_EXISTS",
    "ALREADY_EXISTS_BUSINESS",
    "DUPLICATE",
})

_APPLIED_STATUSES: frozenset = frozenset({
    "APPLIED",
    "ALREADY_APPLIED",
    "ALREADY_EXISTS",
    "ALREADY_EXISTS_BUSINESS",
})


# ---------------------------------------------------------------------------
# Report dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IdempotencyReport:
    """
    Immutable snapshot of idempotency health metrics.

    Fields:
        total_dlq_rows              -- total rows in ota_dead_letter
        pending_dlq_rows            -- rows where replay_result is not in APPLIED_STATUSES
        already_applied_count       -- rows where replay_result is in APPLIED_STATUSES
        idempotency_rejection_count -- rows where rejection_code is in IDEMPOTENCY_REJECTION_CODES
        ordering_buffer_depth       -- ota_ordering_buffer rows with status='waiting'
        checked_at                  -- ISO 8601 timestamp of when this report was collected
    """
    total_dlq_rows: int
    pending_dlq_rows: int
    already_applied_count: int
    idempotency_rejection_count: int
    ordering_buffer_depth: int
    checked_at: str


# ---------------------------------------------------------------------------
# Client helper
# ---------------------------------------------------------------------------

def _get_client() -> Any:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    if create_client is None:  # pragma: no cover
        raise EnvironmentError("supabase-py is not installed")
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _classify_dlq_rows(rows: list) -> tuple[int, int, int, int]:
    """
    Classify DLQ rows into metric buckets.

    Returns:
        (total, pending, already_applied, idempotency_rejection_count)
    """
    total = len(rows)
    pending = 0
    already_applied = 0
    idempotency_rejections = 0

    for row in rows:
        replay_result = row.get("replay_result")
        rejection_code = row.get("rejection_code") or ""

        if replay_result in _APPLIED_STATUSES:
            already_applied += 1
        else:
            pending += 1

        if rejection_code in IDEMPOTENCY_REJECTION_CODES:
            idempotency_rejections += 1

    return total, pending, already_applied, idempotency_rejections


def _count_ordering_buffer_waiting(rows: list) -> int:
    """Count ota_ordering_buffer rows with status='waiting'."""
    return sum(1 for r in rows if r.get("status") == "waiting")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def collect_idempotency_report(client: Optional[Any] = None) -> IdempotencyReport:
    """
    Collect idempotency health metrics from ota_dead_letter and ota_ordering_buffer.

    Args:
        client: Optional injected Supabase client. If None, a live client is created
                from SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY env vars.

    Returns:
        IdempotencyReport -- immutable. All fields are int or str. Never None.

    Raises:
        EnvironmentError: If client is None and env vars are missing.

    Notes:
        - Never writes to any table.
        - If a table returns no rows, metrics default to zero.
        - checked_at is set to UTC now at the moment of collection.
    """
    if client is None:
        client = _get_client()

    # Read DLQ rows
    try:
        dlq_result = (
            client.table("ota_dead_letter")
            .select("replay_result, rejection_code")
            .execute()
        )
        dlq_rows = dlq_result.data or []
    except Exception:  # noqa: BLE001
        dlq_rows = []

    # Read ordering buffer
    try:
        buffer_result = (
            client.table("ota_ordering_buffer")
            .select("status")
            .execute()
        )
        buffer_rows = buffer_result.data or []
    except Exception:  # noqa: BLE001
        buffer_rows = []

    total, pending, already_applied, idempotency_rejections = _classify_dlq_rows(dlq_rows)
    ordering_depth = _count_ordering_buffer_waiting(buffer_rows)

    checked_at = datetime.now(tz=timezone.utc).isoformat()

    return IdempotencyReport(
        total_dlq_rows=total,
        pending_dlq_rows=pending,
        already_applied_count=already_applied,
        idempotency_rejection_count=idempotency_rejections,
        ordering_buffer_depth=ordering_depth,
        checked_at=checked_at,
    )
