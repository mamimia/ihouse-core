"""
Phase 84 — Reservation Timeline / Audit Trail

Provides a unified per-booking story by aggregating events from multiple
source tables into a single ordered, enriched timeline.

Sources (all read-only):
  event_log              — canonical events (BOOKING_CREATED, BOOKING_AMENDED, BOOKING_CANCELED)
  ota_dead_letter        — DLQ entries that reference this booking
  booking_financial_facts — financial snapshots per event
  ota_ordering_buffer    — buffered events pending order resolution

Design:
  - Zero DB schema changes — only reads existing tables.
  - All queries are tenant-scoped (event_log / booking_financial_facts use tenant_id).
  - DLQ and ordering_buffer are global tables — filtered by booking context where possible.
  - Returns a sorted list of TimelineEvent instances ordered by occurred_at ascending.
  - Never raises on individual source failures — partial data is returned with a flag.

Invariants:
  - This module NEVER writes to any table.
  - booking_state is NOT a source — it contains derived state, not event history.
  - financial_facts are attached as metadata, not a primary event source.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TimelineEvent:
    """
    A single event in a booking's timeline.

    source_table identifies which table the event came from.
    event_kind is canonical for event_log, or descriptive for other sources.
    occurred_at and recorded_at are ISO strings or None when absent.
    metadata holds additional source-specific fields.
    """
    source_table: str           # event_log | ota_dead_letter | booking_financial_facts | ota_ordering_buffer
    event_kind: str             # e.g. BOOKING_CREATED, DLQ_INGESTED, FINANCIAL_RECORDED, BUFFERED
    occurred_at: Optional[str]  # business event time (ISO string)
    recorded_at: Optional[str]  # server ingestion time (ISO string)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def sort_key(self) -> str:
        """Sort by recorded_at, fallback to occurred_at, fallback to empty string."""
        return self.recorded_at or self.occurred_at or ""


@dataclass
class ReservationTimeline:
    """
    Aggregated timeline for a single booking.

    events: ordered list of TimelineEvent (ascending by recorded_at)
    booking_id: the booking identifier queried
    tenant_id: the tenant this timeline belongs to
    partial: True if one or more source queries failed — data may be incomplete
    """
    booking_id: str
    tenant_id: str
    events: List[TimelineEvent]
    partial: bool = False


# ---------------------------------------------------------------------------
# Internal source fetchers
# ---------------------------------------------------------------------------

def _fetch_event_log_events(db: Any, tenant_id: str, booking_id: str) -> List[TimelineEvent]:
    """
    Fetch all canonical events from event_log for this tenant+booking.
    Tenant-scoped.
    """
    try:
        result = (
            db.table("event_log")
            .select("event_kind, occurred_at, recorded_at, envelope_id, source")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .execute()
        )
        events = []
        for row in (result.data or []):
            events.append(TimelineEvent(
                source_table="event_log",
                event_kind=row.get("event_kind") or "UNKNOWN",
                occurred_at=row.get("occurred_at"),
                recorded_at=row.get("recorded_at"),
                metadata={
                    "envelope_id": row.get("envelope_id"),
                    "source": row.get("source"),
                },
            ))
        return events, False  # (events, failed)
    except Exception:  # noqa: BLE001
        return [], True


def _fetch_financial_events(db: Any, tenant_id: str, booking_id: str) -> List[TimelineEvent]:
    """
    Fetch financial snapshot events from booking_financial_facts.
    Each row represents a financial state recorded for this booking.
    Tenant-scoped.
    """
    try:
        result = (
            db.table("booking_financial_facts")
            .select("event_kind, recorded_at, total_price, currency, source_confidence")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .execute()
        )
        events = []
        for row in (result.data or []):
            events.append(TimelineEvent(
                source_table="booking_financial_facts",
                event_kind="FINANCIAL_RECORDED",
                occurred_at=None,        # booking_financial_facts has no occurred_at
                recorded_at=row.get("recorded_at"),
                metadata={
                    "event_kind_ref": row.get("event_kind"),
                    "total_price": str(row["total_price"]) if row.get("total_price") else None,
                    "currency": row.get("currency"),
                    "source_confidence": row.get("source_confidence"),
                },
            ))
        return events, False
    except Exception:  # noqa: BLE001
        return [], True


def _fetch_dlq_events(db: Any, booking_id: str) -> List[TimelineEvent]:
    """
    Fetch DLQ entries that reference this booking_id.
    ota_dead_letter is global — no tenant_id column.
    Matches on payload->>booking_id where present.
    """
    try:
        result = (
            db.table("ota_dead_letter")
            .select("id, recorded_at, rejection_reason, event_type, replay_result")
            .eq("booking_id", booking_id)
            .execute()
        )
        events = []
        for row in (result.data or []):
            events.append(TimelineEvent(
                source_table="ota_dead_letter",
                event_kind="DLQ_INGESTED",
                occurred_at=None,
                recorded_at=row.get("recorded_at"),
                metadata={
                    "dlq_id": row.get("id"),
                    "rejection_reason": row.get("rejection_reason"),
                    "event_type": row.get("event_type"),
                    "replay_result": row.get("replay_result"),
                },
            ))
        return events, False
    except Exception:  # noqa: BLE001
        return [], True


def _fetch_buffer_events(db: Any, booking_id: str) -> List[TimelineEvent]:
    """
    Fetch ordering buffer events that reference this booking_id.
    ota_ordering_buffer is global — no tenant_id column.
    """
    try:
        result = (
            db.table("ota_ordering_buffer")
            .select("id, received_at, event_kind, status")
            .eq("booking_id", booking_id)
            .execute()
        )
        events = []
        for row in (result.data or []):
            events.append(TimelineEvent(
                source_table="ota_ordering_buffer",
                event_kind="BUFFERED",
                occurred_at=None,
                recorded_at=row.get("received_at"),
                metadata={
                    "buffer_id": row.get("id"),
                    "original_event_kind": row.get("event_kind"),
                    "status": row.get("status"),
                },
            ))
        return events, False
    except Exception:  # noqa: BLE001
        return [], True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_reservation_timeline(
    db: Any,
    tenant_id: str,
    booking_id: str,
) -> ReservationTimeline:
    """
    Build a unified, ordered timeline for a booking.

    Aggregates events from:
      - event_log (canonical events, tenant-scoped)
      - booking_financial_facts (financial snapshots, tenant-scoped)
      - ota_dead_letter (DLQ entries, global)
      - ota_ordering_buffer (buffered events, global)

    Returns a ReservationTimeline with events sorted by recorded_at ascending.
    If any source query fails, partial=True is set and available data is returned.

    Args:
        db:          Supabase client (or compatible mock)
        tenant_id:   Authenticated tenant identifier
        booking_id:  Canonical booking_id (e.g. "airbnb_res123")

    Returns:
        ReservationTimeline — never raises.
    """
    all_events: List[TimelineEvent] = []
    had_failure = False

    # Fetch from each source
    el_events, el_failed = _fetch_event_log_events(db, tenant_id, booking_id)
    all_events.extend(el_events)
    if el_failed:
        had_failure = True

    fin_events, fin_failed = _fetch_financial_events(db, tenant_id, booking_id)
    all_events.extend(fin_events)
    if fin_failed:
        had_failure = True

    dlq_events, dlq_failed = _fetch_dlq_events(db, booking_id)
    all_events.extend(dlq_events)
    if dlq_failed:
        had_failure = True

    buf_events, buf_failed = _fetch_buffer_events(db, booking_id)
    all_events.extend(buf_events)
    if buf_failed:
        had_failure = True

    # Sort by recorded_at ascending (earliest first), with stable fallback
    sorted_events = sorted(all_events, key=lambda e: e.sort_key())

    return ReservationTimeline(
        booking_id=booking_id,
        tenant_id=tenant_id,
        events=sorted_events,
        partial=had_failure,
    )
