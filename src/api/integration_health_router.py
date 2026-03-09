"""
Phase 127 — Integration Health Dashboard

Provides a comprehensive per-provider integration health view covering all 13 OTA
providers: last ingest timestamp, occurred_at vs recorded_at lag, buffer depth,
DLQ reject counts per provider, and stale-provider alerts.

Enhancement over Phase 82 /admin/health/providers:
- All 13 providers (was: 5)
- lag_seconds: recorded_at - occurred_at (detects delayed events)
- buffer_count: pending rows in ota_ordering_buffer per provider
- dlq_count: pending rows in ota_dead_letter per provider (source-based)
- stale_alert: True when last_ingest_at > 24h ago (or no data at all)
- summary block: total ok/stale/unknown + alert count

Endpoint:
    GET /integration-health

Invariants:
- JWT auth required.
- Reads from: event_log, ota_ordering_buffer, ota_dead_letter. Never writes.
- Tenant-scoped for event_log. DLQ/buffer are global infrastructure metrics.
- All provider lookups are best-effort; per-provider error → status=unknown, no 500.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# All 13 registered OTA providers (registry order)
# ---------------------------------------------------------------------------

_ALL_PROVIDERS = (
    "bookingcom",
    "airbnb",
    "expedia",
    "agoda",
    "tripcom",
    "vrbo",
    "gvr",
    "traveloka",
    "makemytrip",
    "klook",
    "despegar",
    "rakuten",
    "hotelbeds",
)

# Stale threshold: if last_ingest_at older than this, raise alert
_STALE_HOURS = 24


# ---------------------------------------------------------------------------
# DB client helper — matches existing admin_router pattern
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Per-provider data gathering helpers
# ---------------------------------------------------------------------------

def _provider_event_info(db: Any, tenant_id: str, provider: str) -> Dict[str, Any]:
    """
    Get last ingest info for a single provider from event_log.

    Returns:
        {
            "last_ingest_at": str | None,
            "lag_seconds": float | None,   # recorded_at - occurred_at of last event
            "status": "ok" | "unknown"
        }
    """
    try:
        result = (
            db.table("event_log")
            .select("recorded_at, occurred_at")
            .eq("tenant_id", tenant_id)
            .eq("source", provider)
            .order("recorded_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return {"last_ingest_at": None, "lag_seconds": None, "status": "unknown"}

        row = rows[0]
        recorded_at_str = row.get("recorded_at")
        occurred_at_str = row.get("occurred_at")

        lag_seconds: Optional[float] = None
        if recorded_at_str and occurred_at_str:
            try:
                recorded_dt = datetime.fromisoformat(recorded_at_str.replace("Z", "+00:00"))
                occurred_dt = datetime.fromisoformat(occurred_at_str.replace("Z", "+00:00"))
                lag_seconds = (recorded_dt - occurred_dt).total_seconds()
            except (ValueError, AttributeError):
                lag_seconds = None

        return {
            "last_ingest_at": recorded_at_str,
            "lag_seconds": lag_seconds,
            "status": "ok",
        }
    except Exception:  # noqa: BLE001
        return {"last_ingest_at": None, "lag_seconds": None, "status": "unknown"}


def _provider_buffer_count(db: Any, provider: str) -> int:
    """
    Count pending rows in ota_ordering_buffer for this provider.
    Buffer is global (no tenant_id). Best-effort: returns 0 on error.
    """
    try:
        result = (
            db.table("ota_ordering_buffer")
            .select("id")
            .eq("source", provider)
            .is_("replayed_at", "null")
            .execute()
        )
        return len(result.data or [])
    except Exception:  # noqa: BLE001
        return 0


def _provider_dlq_count(db: Any, provider: str) -> int:
    """
    Count pending (unresolved) rows in ota_dead_letter for this provider.
    DLQ is global. A row is pending if replay_result is null or not an APPLIED status.
    Best-effort: returns 0 on error.
    """
    _APPLIED_STATUSES = frozenset({"APPLIED", "ALREADY_APPLIED", "ALREADY_EXISTS", "ALREADY_EXISTS_BUSINESS"})
    try:
        result = (
            db.table("ota_dead_letter")
            .select("id, replay_result, source")
            .eq("source", provider)
            .execute()
        )
        return sum(
            1 for r in (result.data or [])
            if r.get("replay_result") not in _APPLIED_STATUSES
        )
    except Exception:  # noqa: BLE001
        return 0


def _is_stale(last_ingest_at: Optional[str]) -> bool:
    """
    Returns True if last_ingest_at is None or older than _STALE_HOURS.
    """
    if last_ingest_at is None:
        return True
    try:
        last_dt = datetime.fromisoformat(last_ingest_at.replace("Z", "+00:00"))
        now_utc = datetime.now(tz=timezone.utc)
        return (now_utc - last_dt) > timedelta(hours=_STALE_HOURS)
    except (ValueError, AttributeError):
        return True


def _build_provider_record(
    db: Any,
    tenant_id: str,
    provider: str,
) -> Dict[str, Any]:
    """
    Build the full health record for a single provider.

    Shape:
    {
        "provider": str,
        "last_ingest_at": str | null,
        "lag_seconds": float | null,
        "buffer_count": int,
        "dlq_count": int,
        "stale_alert": bool,
        "status": "ok" | "unknown"
    }
    """
    event_info = _provider_event_info(db, tenant_id, provider)
    buffer_count = _provider_buffer_count(db, provider)
    dlq_count = _provider_dlq_count(db, provider)
    stale = _is_stale(event_info["last_ingest_at"])

    return {
        "provider": provider,
        "last_ingest_at": event_info["last_ingest_at"],
        "lag_seconds": event_info["lag_seconds"],
        "buffer_count": buffer_count,
        "dlq_count": dlq_count,
        "stale_alert": stale,
        "status": event_info["status"],
    }


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/integration-health",
    tags=["admin"],
    summary="Integration Health Dashboard (Phase 127)",
    description=(
        "Per-provider integration health view for all 13 OTA providers.\n\n"
        "Covers: last ingest timestamp, occurred_at→recorded_at lag, "
        "ordering buffer depth, DLQ pending count, and stale-provider alert.\n\n"
        "**Providers:** bookingcom, airbnb, expedia, agoda, tripcom, vrbo, gvr, "
        "traveloka, makemytrip, klook, despegar, rakuten, hotelbeds.\n\n"
        "**Stale alert:** raised when no events received in the last 24h.\n\n"
        "**Source tables:** `event_log` (tenant-scoped), `ota_ordering_buffer` (global), "
        "`ota_dead_letter` (global). Read-only."
    ),
    responses={
        200: {"description": "Per-provider integration health for all 13 OTA providers."},
        401: {"description": "Missing or invalid JWT token."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_integration_health(
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /integration-health

    Returns per-provider integration health for all 13 OTA providers:
    - last_ingest_at: ISO timestamp of last event received
    - lag_seconds: recorded_at minus occurred_at (event processing delay)
    - buffer_count: pending rows in ordering buffer for this provider
    - dlq_count: unresolved rows in DLQ for this provider
    - stale_alert: True if no events in last 24h
    - status: "ok" | "unknown"

    Plus a summary block with aggregate counts.

    Authentication: Bearer JWT required. tenant_id from sub claim.
    """
    try:
        db = client if client is not None else _get_supabase_client()

        providers_health: List[Dict[str, Any]] = []
        for provider in _ALL_PROVIDERS:
            record = _build_provider_record(db, tenant_id, provider)
            providers_health.append(record)

        # Summary
        ok_count = sum(1 for p in providers_health if p["status"] == "ok")
        stale_count = sum(1 for p in providers_health if p["stale_alert"])
        unknown_count = sum(1 for p in providers_health if p["status"] == "unknown")
        total_dlq = sum(p["dlq_count"] for p in providers_health)
        total_buffer = sum(p["buffer_count"] for p in providers_health)
        has_alerts = stale_count > 0 or total_dlq > 0

        checked_at = datetime.now(tz=timezone.utc).isoformat()

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "checked_at": checked_at,
                "providers": providers_health,
                "summary": {
                    "total_providers": len(_ALL_PROVIDERS),
                    "ok": ok_count,
                    "stale": stale_count,
                    "unknown": unknown_count,
                    "total_dlq_pending": total_dlq,
                    "total_buffer_pending": total_buffer,
                    "has_alerts": has_alerts,
                },
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /integration-health error for tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
