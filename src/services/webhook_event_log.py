"""
Phase 261 — Webhook Event Log
==============================

Append-only, in-memory event log for all inbound webhook payloads.
Pure service layer — no new Supabase tables required.

Captures: provider, event_type, booking_ref, raw payload snapshot,
received_at, and processing outcome (accepted / rejected / duplicate).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

MAX_LOG_SIZE = 5000  # cap to prevent unbounded growth in long-running process

OUTCOME_ACCEPTED  = "accepted"
OUTCOME_REJECTED  = "rejected"
OUTCOME_DUPLICATE = "duplicate"


@dataclass
class WebhookEventEntry:
    """One logged webhook event."""
    entry_id: str
    provider: str          # e.g. "airbnb", "booking_com", "agoda"
    event_type: str        # e.g. "booking_created", "booking_cancelled"
    booking_ref: str | None
    outcome: str           # accepted | rejected | duplicate
    received_at: str       # ISO-8601 UTC
    payload_keys: list[str]  # top-level keys of raw payload (no PII stored)
    error: str | None = None


# Module-level log (singleton for the process lifetime)
_log: list[WebhookEventEntry] = []


# ---------------------------------------------------------------------------
# Append
# ---------------------------------------------------------------------------

def log_webhook_event(
    provider: str,
    event_type: str,
    payload: dict[str, Any],
    outcome: str = OUTCOME_ACCEPTED,
    booking_ref: str | None = None,
    error: str | None = None,
) -> WebhookEventEntry:
    """
    Append one webhook event to the in-memory log.

    Stores only top-level payload keys (not values) to avoid PII leakage.
    Returns the created entry.
    """
    entry = WebhookEventEntry(
        entry_id=str(uuid.uuid4()),
        provider=provider,
        event_type=event_type,
        booking_ref=booking_ref,
        outcome=outcome,
        received_at=datetime.now(timezone.utc).isoformat(),
        payload_keys=list(payload.keys()) if payload else [],
        error=error,
    )
    _log.append(entry)
    # Evict oldest if over cap
    if len(_log) > MAX_LOG_SIZE:
        del _log[0]
    return entry


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def get_webhook_log(
    provider: str | None = None,
    event_type: str | None = None,
    outcome: str | None = None,
    limit: int = 50,
) -> list[WebhookEventEntry]:
    """
    Return recent webhook log entries, newest first.

    All filter args are optional. Limit capped at 200.
    """
    limit = min(limit, 200)
    results = list(reversed(_log))  # newest first

    if provider:
        results = [r for r in results if r.provider == provider]
    if event_type:
        results = [r for r in results if r.event_type == event_type]
    if outcome:
        results = [r for r in results if r.outcome == outcome]

    return results[:limit]


def get_webhook_log_stats() -> dict:
    """
    Aggregate stats: counts per provider, per outcome, total.
    """
    total = len(_log)
    by_provider: dict[str, int] = {}
    by_outcome: dict[str, int] = {}

    for entry in _log:
        by_provider[entry.provider] = by_provider.get(entry.provider, 0) + 1
        by_outcome[entry.outcome] = by_outcome.get(entry.outcome, 0) + 1

    return {
        "total": total,
        "by_provider": by_provider,
        "by_outcome": by_outcome,
    }


def clear_webhook_log() -> int:
    """Flush the log. Returns count of entries cleared. For testing only."""
    count = len(_log)
    _log.clear()
    return count
