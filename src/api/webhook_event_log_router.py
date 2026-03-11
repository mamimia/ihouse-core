"""
Phase 261 — Webhook Event Log Router
======================================

GET  /admin/webhook-log          — Paginated log query (filter by provider / event_type / outcome)
GET  /admin/webhook-log/stats    — Aggregate stats (total, by_provider, by_outcome)
POST /admin/webhook-log/test     — Emit a test entry (dev/testing utility)
"""
from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from services.webhook_event_log import (
    log_webhook_event,
    get_webhook_log,
    get_webhook_log_stats,
    OUTCOME_ACCEPTED,
    OUTCOME_REJECTED,
    OUTCOME_DUPLICATE,
)

router = APIRouter(prefix="/admin/webhook-log", tags=["admin"])


def _entry_to_dict(entry) -> dict:
    return {
        "entry_id": entry.entry_id,
        "provider": entry.provider,
        "event_type": entry.event_type,
        "booking_ref": entry.booking_ref,
        "outcome": entry.outcome,
        "received_at": entry.received_at,
        "payload_keys": entry.payload_keys,
        "error": entry.error,
    }


@router.get(
    "",
    summary="Query webhook event log (max 200 results)",
)
async def query_webhook_log(
    provider: str | None = Query(default=None, description="Filter by provider name"),
    event_type: str | None = Query(default=None, description="Filter by event type"),
    outcome: str | None = Query(default=None, description="Filter by outcome: accepted | rejected | duplicate"),
    limit: int = Query(default=50, ge=1, le=200),
) -> JSONResponse:
    """
    GET /admin/webhook-log

    Returns webhook log entries newest-first.
    All filters are optional and combinable.
    """
    entries = get_webhook_log(
        provider=provider,
        event_type=event_type,
        outcome=outcome,
        limit=limit,
    )
    return JSONResponse(status_code=200, content={
        "total_returned": len(entries),
        "entries": [_entry_to_dict(e) for e in entries],
    })


@router.get(
    "/stats",
    summary="Webhook log aggregate stats",
)
async def webhook_log_stats() -> JSONResponse:
    """
    GET /admin/webhook-log/stats

    Returns total event count, breakdown by provider, by outcome.
    """
    return JSONResponse(status_code=200, content=get_webhook_log_stats())


@router.post(
    "/test",
    summary="Emit a test webhook log entry (dev utility)",
)
async def emit_test_entry(
    provider: str = Query(default="test"),
    event_type: str = Query(default="ping"),
) -> JSONResponse:
    """
    POST /admin/webhook-log/test

    Injects a synthetic entry into the log for testing/dev.
    """
    entry = log_webhook_event(
        provider=provider,
        event_type=event_type,
        payload={"synthetic": True, "source": "test_endpoint"},
        outcome=OUTCOME_ACCEPTED,
    )
    return JSONResponse(status_code=201, content=_entry_to_dict(entry))
