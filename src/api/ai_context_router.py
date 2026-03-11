"""
Phase 222 — AI Context Aggregation Endpoints

Thin, read-only composition layer providing structured context bundles
for the AI copilot layer (Phase 223+).

No new tables. Pure aggregation over existing API data surfaces.
Never writes to any table. JWT required. Tenant-scoped.

Design principles (from ai-strategy.md):
  - The deterministic core is truth. AI is explanation.
  - Context bundles must never include write-path data.
  - PII isolation: guest names/emails are excluded unless explicitly needed.
  - All fields best-effort: errors in one sub-query degrade gracefully,
    never fail the whole bundle.
  - response_ms included for LLM token budget awareness.

Endpoints:
  GET /ai/context/property/{property_id}
    Full property context snapshot — bookings, tasks, sync, financials.
    For the Manager Copilot: per-property situation at a glance.

  GET /ai/context/operations-day
    Today's operational situation across the tenant — arrivals,
    departures, open tasks, DLQ status, top SLA risks.
    For the Manager Copilot: daily briefing seed.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_TASKS = 20       # max open tasks to include per property
_MAX_BOOKINGS = 10    # max active bookings to include per property
_MAX_SYNC_ROWS = 5    # max recent outbound sync events to include


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_db() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Sub-queries (each best-effort, return {} or [] on failure)
# ---------------------------------------------------------------------------

def _fetch_property_meta(db: Any, tenant_id: str, property_id: str) -> Dict[str, Any]:
    """Fetch property name + basic metadata from `properties` table."""
    try:
        result = (
            db.table("properties")
            .select("property_id, name, address, property_type, created_at")
            .eq("property_id", property_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return {"property_id": property_id, "status": "not_found"}
        r = rows[0]
        return {
            "property_id": r.get("property_id"),
            "name": r.get("name"),
            "address": r.get("address"),
            "property_type": r.get("property_type"),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("ai_context.property_meta: %s", exc)
        return {"property_id": property_id, "status": "error"}


def _fetch_active_bookings(
    db: Any, tenant_id: str, property_id: str
) -> List[Dict[str, Any]]:
    """Recent active bookings for this property. PII-free."""
    try:
        result = (
            db.table("booking_state")
            .select(
                "booking_id, source, status, check_in, check_out, "
                "nights, currency, total_amount"
            )
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .eq("status", "active")
            .order("check_in", desc=False)
            .limit(_MAX_BOOKINGS)
            .execute()
        )
        return result.data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("ai_context.active_bookings: %s", exc)
        return []


def _fetch_open_tasks(
    db: Any, tenant_id: str, property_id: str
) -> List[Dict[str, Any]]:
    """Open / in-progress tasks for this property. Includes SLA metadata."""
    try:
        result = (
            db.table("tasks")
            .select(
                "task_id, kind, status, priority, created_at, "
                "acknowledged_at, description"
            )
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .in_("status", ["PENDING", "ACKNOWLEDGED", "IN_PROGRESS"])
            .order("created_at", desc=False)
            .limit(_MAX_TASKS)
            .execute()
        )
        rows = result.data or []
        # Annotate each task with age_minutes
        now = datetime.now(tz=timezone.utc)
        for r in rows:
            try:
                created = datetime.fromisoformat(
                    str(r.get("created_at", "")).replace("Z", "+00:00")
                )
                r["age_minutes"] = int((now - created).total_seconds() / 60)
            except Exception:
                r["age_minutes"] = None
        return rows
    except Exception as exc:  # noqa: BLE001
        logger.warning("ai_context.open_tasks: %s", exc)
        return []


def _fetch_sync_health(
    db: Any, tenant_id: str, property_id: str
) -> Dict[str, Any]:
    """Recent outbound sync events for this property's channels."""
    try:
        result = (
            db.table("outbound_sync_log")
            .select("provider, status, synced_at, booking_id")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .order("synced_at", desc=True)
            .limit(_MAX_SYNC_ROWS)
            .execute()
        )
        rows = result.data or []
        failed = [r for r in rows if str(r.get("status", "")).lower() in ("failed", "error", "fail")]
        return {
            "recent_count": len(rows),
            "recent_failed": len(failed),
            "entries": rows,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("ai_context.sync_health: %s", exc)
        return {"recent_count": 0, "recent_failed": 0, "entries": [], "error": str(exc)[:80]}


def _fetch_financial_snapshot(
    db: Any, tenant_id: str, property_id: str
) -> Dict[str, Any]:
    """Revenue summary for this property from booking_financial_facts."""
    try:
        result = (
            db.table("booking_financial_facts")
            .select(
                "booking_id, currency, gross_amount, net_amount, "
                "commission_amount, lifecycle_status"
            )
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return {"total_bookings": 0, "currencies": []}

        # Group by currency
        by_currency: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            ccy = str(r.get("currency") or "UNKNOWN")
            if ccy not in by_currency:
                by_currency[ccy] = {"currency": ccy, "gross_total": 0.0, "net_total": 0.0, "count": 0, "active_count": 0}
            try:
                by_currency[ccy]["gross_total"] += float(r.get("gross_amount") or 0)
                by_currency[ccy]["net_total"] += float(r.get("net_amount") or 0)
                by_currency[ccy]["count"] += 1
                if str(r.get("lifecycle_status", "")).lower() in ("confirmed", "active"):
                    by_currency[ccy]["active_count"] += 1
            except Exception:
                pass

        return {
            "total_bookings": len(rows),
            "currencies": list(by_currency.values()),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("ai_context.financial: %s", exc)
        return {"total_bookings": 0, "currencies": [], "error": str(exc)[:80]}


def _fetch_availability_summary(
    db: Any, tenant_id: str, property_id: str
) -> Dict[str, Any]:
    """How many of the next 30 days are occupied."""
    try:
        from datetime import timedelta
        today = date.today()
        upcoming = [(today + timedelta(days=i)).isoformat() for i in range(30)]

        result = (
            db.table("booking_state")
            .select("booking_id, check_in, check_out, status")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .eq("status", "active")
            .execute()
        )
        rows = result.data or []

        # Set of occupied dates
        occupied: set = set()
        for r in rows:
            try:
                ci = date.fromisoformat(str(r["check_in"]))
                co = date.fromisoformat(str(r["check_out"]))
                d = ci
                from datetime import timedelta as td
                while d < co:
                    occupied.add(d.isoformat())
                    d += td(days=1)
            except Exception:
                pass

        occupied_next_30 = sum(1 for d in upcoming if d in occupied)
        return {
            "occupied_nights_next_30": occupied_next_30,
            "available_nights_next_30": 30 - occupied_next_30,
            "occupancy_rate_next_30": round(occupied_next_30 / 30, 3),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("ai_context.availability: %s", exc)
        return {"occupied_nights_next_30": None, "available_nights_next_30": None, "occupancy_rate_next_30": None}


# ---------------------------------------------------------------------------
# Operations-day sub-queries
# ---------------------------------------------------------------------------

def _fetch_tenant_tasks_summary(db: Any, tenant_id: str) -> Dict[str, Any]:
    """Count open tasks by priority and kind across all properties."""
    try:
        result = (
            db.table("tasks")
            .select("task_id, kind, status, priority, created_at")
            .eq("tenant_id", tenant_id)
            .in_("status", ["PENDING", "ACKNOWLEDGED", "IN_PROGRESS"])
            .execute()
        )
        rows = result.data or []

        by_priority: Dict[str, int] = {}
        by_kind: Dict[str, int] = {}
        critical_unacked = 0
        now = datetime.now(tz=timezone.utc)

        for r in rows:
            p = str(r.get("priority") or "NORMAL")
            k = str(r.get("kind") or "GENERAL")
            by_priority[p] = by_priority.get(p, 0) + 1
            by_kind[k] = by_kind.get(k, 0) + 1

            # Critical unacked within last 5 minutes = still within SLA
            if p == "CRITICAL" and str(r.get("status")) == "PENDING":
                try:
                    created = datetime.fromisoformat(
                        str(r.get("created_at", "")).replace("Z", "+00:00")
                    )
                    age_min = (now - created).total_seconds() / 60
                    if age_min > 5:
                        critical_unacked += 1
                except Exception:
                    pass

        return {
            "total_open": len(rows),
            "by_priority": by_priority,
            "by_kind": by_kind,
            "critical_past_ack_sla": critical_unacked,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("ai_context.tenant_tasks: %s", exc)
        return {"total_open": 0, "by_priority": {}, "by_kind": {}, "critical_past_ack_sla": 0}


def _fetch_tenant_operations(db: Any, tenant_id: str) -> Dict[str, Any]:
    """Today's arrivals, departures, cleanings across all properties."""
    try:
        today_str = date.today().isoformat()
        result = (
            db.table("booking_state")
            .select("booking_id, property_id, check_in, check_out, status")
            .eq("tenant_id", tenant_id)
            .eq("status", "active")
            .execute()
        )
        rows = result.data or []
        arrivals = [r for r in rows if str(r.get("check_in", "")) == today_str]
        departures = [r for r in rows if str(r.get("check_out", "")) == today_str]
        return {
            "date": today_str,
            "arrivals_count": len(arrivals),
            "departures_count": len(departures),
            "cleanings_due": len(departures),
            "active_bookings": len(rows),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("ai_context.tenant_operations: %s", exc)
        return {"date": date.today().isoformat(), "arrivals_count": 0, "departures_count": 0, "cleanings_due": 0, "active_bookings": 0}


def _fetch_dlq_summary(db: Any) -> Dict[str, Any]:
    """Unprocessed DLQ count (global) for ops context."""
    try:
        result = (
            db.table("ota_dead_letter")
            .select("id", count="exact")
            .is_("replay_result", "null")
            .execute()
        )
        count = result.count if result.count is not None else len(result.data or [])
        return {"unprocessed_count": count, "alert": count >= 5}
    except Exception as exc:  # noqa: BLE001
        logger.warning("ai_context.dlq: %s", exc)
        return {"unprocessed_count": None, "alert": None}


def _fetch_sync_summary(db: Any, tenant_id: str) -> Dict[str, Any]:
    """Outbound sync failure rate over last 24h."""
    try:
        from datetime import timedelta
        cutoff = (datetime.now(tz=timezone.utc) - timedelta(hours=24)).isoformat()
        result = (
            db.table("outbound_sync_log")
            .select("status")
            .eq("tenant_id", tenant_id)
            .gte("synced_at", cutoff)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return {"event_count_24h": 0, "failure_rate_24h": None}
        failed = sum(1 for r in rows if str(r.get("status", "")).lower() in ("failed", "error", "fail"))
        return {
            "event_count_24h": len(rows),
            "failure_count_24h": failed,
            "failure_rate_24h": round(failed / len(rows), 3),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("ai_context.sync_summary: %s", exc)
        return {"event_count_24h": 0, "failure_rate_24h": None}


# ---------------------------------------------------------------------------
# GET /ai/context/property/{property_id}
# ---------------------------------------------------------------------------

@router.get(
    "/ai/context/property/{property_id}",
    tags=["ai-context"],
    summary="AI property context bundle (Phase 222)",
    description=(
        "Returns a structured, LLM-ready property context bundle "
        "aggregating bookings, tasks, sync health, financials, and "
        "availability for the requested property.\\n\\n"
        "**No new tables.** Pure aggregation over existing data surfaces.\\n\\n"
        "**PII:** Guest names and emails are excluded.\\n\\n"
        "**Source:** `booking_state`, `tasks`, `outbound_sync_log`, "
        "`booking_financial_facts`, `properties`. All read-only."
    ),
    responses={
        200: {"description": "Property context bundle"},
        401: {"description": "Missing or invalid JWT"},
        403: {"description": "Property not found or not owned by tenant"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_property_ai_context(
    property_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /ai/context/property/{property_id}

    Returns a full property context bundle suitable for LLM consumption.

    **Intent:** Seed the Manager Copilot (Phase 223) with all relevant
    property state in a single request. The LLM can then explain,
    prioritize, and recommend without making additional DB calls.

    **Token guidance:** Response ~2,000–4,000 tokens depending on
    booking and task counts. Frontend should truncate if budget is tight.
    """
    t0 = time.monotonic()
    try:
        db = client if client is not None else _get_db()
    except Exception as exc:  # noqa: BLE001
        return make_error_response(500, "INTERNAL_ERROR", "DB unavailable")

    # Property auth check — if property_meta returns not_found, block
    meta = _fetch_property_meta(db, tenant_id, property_id)
    if meta.get("status") == "not_found":
        return make_error_response(403, "FORBIDDEN", f"Property not found: {property_id}")

    # Parallel aggregation (sync Python — each sub-query is fast)
    bookings = _fetch_active_bookings(db, tenant_id, property_id)
    tasks = _fetch_open_tasks(db, tenant_id, property_id)
    sync = _fetch_sync_health(db, tenant_id, property_id)
    financial = _fetch_financial_snapshot(db, tenant_id, property_id)
    availability = _fetch_availability_summary(db, tenant_id, property_id)

    response_ms = int((time.monotonic() - t0) * 1000)

    return JSONResponse(
        status_code=200,
        content={
            "context_type": "property",
            "property_id": property_id,
            "tenant_id": tenant_id,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "response_ms": response_ms,
            "property": meta,
            "bookings": {
                "active": bookings,
                "active_count": len(bookings),
            },
            "tasks": {
                "open": tasks,
                "open_count": len(tasks),
            },
            "sync": sync,
            "financial": financial,
            "availability": availability,
            # Annotations for LLM guidance
            "ai_hints": {
                "has_open_tasks": len(tasks) > 0,
                "has_sync_failures": sync.get("recent_failed", 0) > 0,
                "high_priority_tasks": [
                    t["task_id"] for t in tasks
                    if str(t.get("priority", "")).upper() in ("HIGH", "CRITICAL")
                ],
            },
        },
    )


# ---------------------------------------------------------------------------
# GET /ai/context/operations-day
# ---------------------------------------------------------------------------

@router.get(
    "/ai/context/operations-day",
    tags=["ai-context"],
    summary="AI daily operations context bundle (Phase 222)",
    description=(
        "Returns a structured, LLM-ready context bundle for today's "
        "operational situation across the tenant.\\n\\n"
        "**Use case:** Morning briefing seed for Manager Copilot (Phase 223).\\n\\n"
        "**Includes:** arrivals/departures/cleanings, open task summary "
        "(by priority + kind), critical SLA risks, DLQ alert status, "
        "outbound sync health.\\n\\n"
        "**PII:** No guest PII included.\\n\\n"
        "**Source:** `booking_state`, `tasks`, `ota_dead_letter`, "
        "`outbound_sync_log`. All read-only."
    ),
    responses={
        200: {"description": "Today's operations context bundle"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_operations_day_ai_context(
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /ai/context/operations-day

    Today's operational situation across all properties for this tenant.

    **Intent:** Feed the Manager Copilot morning briefing (Phase 223).
    The LLM receives a structured snapshot and generates a prioritized
    decision-ready briefing for the duty manager.
    """
    t0 = time.monotonic()
    try:
        db = client if client is not None else _get_db()
    except Exception:  # noqa: BLE001
        return make_error_response(500, "INTERNAL_ERROR", "DB unavailable")

    ops = _fetch_tenant_operations(db, tenant_id)
    tasks = _fetch_tenant_tasks_summary(db, tenant_id)
    dlq = _fetch_dlq_summary(db)
    sync = _fetch_sync_summary(db, tenant_id)

    response_ms = int((time.monotonic() - t0) * 1000)

    return JSONResponse(
        status_code=200,
        content={
            "context_type": "operations-day",
            "tenant_id": tenant_id,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "response_ms": response_ms,
            "operations": ops,
            "tasks": tasks,
            "dlq": dlq,
            "outbound_sync": sync,
            # Structured alert flags for LLM conditional logic
            "ai_hints": {
                "critical_tasks_over_sla": tasks.get("critical_past_ack_sla", 0),
                "dlq_alert": dlq.get("alert", False),
                "sync_degraded": (
                    sync.get("failure_rate_24h") is not None
                    and sync.get("failure_rate_24h", 0) > 0.2
                ),
                "high_arrival_day": ops.get("arrivals_count", 0) >= 3,
                "high_departure_day": ops.get("departures_count", 0) >= 3,
            },
        },
    )
