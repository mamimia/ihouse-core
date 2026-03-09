"""
Phase 145 — Outbound Sync Log Inspector API
Phase 146 — Sync Health Dashboard

Provides read-only visibility into all outbound adapter calls via the
`outbound_sync_log` table written by Phase 144.

Read-only. Never writes. JWT required. Tenant-scoped.

Endpoints:
  GET /admin/outbound-log
      Query params: booking_id, provider, status, limit (default 50, max 200)
      Returns: list of outbound_sync_log rows for this tenant, newest-first.

  GET /admin/outbound-log/{booking_id}
      Returns: all sync log rows for a specific booking (this tenant only).
      404 if no rows found for this booking.

  GET /admin/outbound-health       (Phase 146)
      Returns per-provider aggregate: ok/failed/dry_run/skipped counts,
      last_sync_at, failure_rate_7d. Only providers that have at least
      one row in outbound_sync_log for this tenant are included.

  POST /admin/outbound-replay   (Phase 147)
      Body: {booking_id, provider}
      Re-executes the most recent sync attempt for that booking+provider
      by looking up strategy/external_id from outbound_sync_log and calling
      execute_single_provider(). Fail-isolated (same guarantees as Phase 138-144).

Invariant:
  GET endpoints NEVER write to any table.
  POST /admin/outbound-replay writes to outbound_sync_log (via best-effort
  sync_log_writer) and dispatches to real OTA adapters.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from fastapi import Depends
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()

_VALID_STATUSES = frozenset({"ok", "failed", "dry_run", "skipped"})
_DEFAULT_LIMIT  = 50
_MAX_LIMIT      = 200


# ---------------------------------------------------------------------------
# Supabase client helper (follows admin_router.py pattern)
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def _query_log(
    db: Any,
    tenant_id: str,
    booking_id: Optional[str],
    provider: Optional[str],
    status: Optional[str],
    limit: int,
) -> List[dict]:
    """
    Fetch outbound_sync_log rows for this tenant, newest-first.
    Applies optional filters: booking_id, provider, status.
    Returns empty list on any error (best-effort read).
    """
    try:
        q = (
            db.table("outbound_sync_log")
            .select(
                "id, booking_id, tenant_id, provider, external_id, "
                "strategy, status, http_status, message, synced_at"
            )
            .eq("tenant_id", tenant_id)
            .order("synced_at", desc=True)
            .limit(limit)
        )
        if booking_id:
            q = q.eq("booking_id", booking_id)
        if provider:
            q = q.eq("provider", provider)
        if status:
            q = q.eq("status", status)

        result = q.execute()
        return result.data or []

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "_query_log error for tenant=%s booking=%s: %s",
            tenant_id, booking_id, exc,
        )
        return []


# ---------------------------------------------------------------------------
# GET /admin/outbound-log
# ---------------------------------------------------------------------------

@router.get(
    "/admin/outbound-log",
    tags=["admin", "outbound"],
    summary="List outbound sync log entries",
    responses={
        200: {"description": "Outbound sync log entries for this tenant"},
        400: {"description": "Invalid filter parameter"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_outbound_log(
    booking_id: Optional[str] = Query(None, description="Filter by booking_id"),
    provider:   Optional[str] = Query(None, description="Filter by OTA provider"),
    status:     Optional[str] = Query(None, description="Filter by status: ok|failed|dry_run|skipped"),
    limit:      int           = Query(_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT, description="Max rows (1-200)"),
    tenant_id:  str           = Depends(jwt_auth),
    client:     Optional[Any] = None,
) -> JSONResponse:
    """
    List outbound sync log entries for the authenticated tenant.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Tenant isolation:** Only this tenant's rows are returned.

    **Ordering:** Newest `synced_at` first.

    **Query parameters:**
    - `booking_id` — filter to a specific booking
    - `provider`   — filter to a specific OTA provider (e.g. `airbnb`, `bookingcom`)
    - `status`     — filter by status: `ok`, `failed`, `dry_run`, `skipped`
    - `limit`      — max number of rows to return (default 50, max 200)

    **Source:** `outbound_sync_log` — read-only.
    """
    # Validate optional status filter
    if status and status not in _VALID_STATUSES:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"status must be one of: {sorted(_VALID_STATUSES)}"},
        )

    try:
        db = client if client is not None else _get_supabase_client()
        rows = _query_log(db, tenant_id, booking_id, provider, status, limit)

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "count":     len(rows),
                "limit":     limit,
                "entries":   rows,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/outbound-log error for tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /admin/outbound-log/{booking_id}
# ---------------------------------------------------------------------------

@router.get(
    "/admin/outbound-log/{booking_id}",
    tags=["admin", "outbound"],
    summary="Get all outbound sync log entries for a booking",
    responses={
        200: {"description": "All outbound sync log entries for this booking"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "No sync log entries for this booking"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_outbound_log_for_booking(
    booking_id: str,
    tenant_id:  str           = Depends(jwt_auth),
    client:     Optional[Any] = None,
) -> JSONResponse:
    """
    Get all outbound sync log entries for a specific booking.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Tenant isolation:** Cross-tenant reads return 404 (not 403) to avoid
    leaking booking existence. Same convention as the booking timeline endpoint.

    **Ordering:** Newest `synced_at` first.

    **Source:** `outbound_sync_log` — read-only.

    Returns **404** if no log entries exist yet for this booking.
    """
    try:
        db    = client if client is not None else _get_supabase_client()
        rows  = _query_log(db, tenant_id, booking_id, None, None, _MAX_LIMIT)

        if not rows:
            return make_error_response(
                status_code=404,
                code=ErrorCode.BOOKING_NOT_FOUND,
                extra={"booking_id": booking_id},
            )

        return JSONResponse(
            status_code=200,
            content={
                "booking_id": booking_id,
                "tenant_id":  tenant_id,
                "count":      len(rows),
                "entries":    rows,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /admin/outbound-log/%s error for tenant=%s: %s",
            booking_id, tenant_id, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# _compute_health — Phase 146 helper
# ---------------------------------------------------------------------------

def _compute_health(db: Any, tenant_id: str) -> List[Dict[str, Any]]:
    """
    Compute per-provider sync health for this tenant.

    Fetches all outbound_sync_log rows for this tenant (newest 2000, enough
    for any reasonable operator view), then aggregates in-memory:
      - ok_count, failed_count, dry_run_count, skipped_count
      - last_sync_at   — latest synced_at across all statuses
      - failure_rate_7d — failed / (ok + failed) in last 7 days (None if no data)

    Only providers that have at least one row are included in the result.
    Never raises — returns [] on error.
    """
    try:
        result = (
            db.table("outbound_sync_log")
            .select("provider, status, synced_at")
            .eq("tenant_id", tenant_id)
            .order("synced_at", desc=True)
            .limit(2000)
            .execute()
        )
        rows = result.data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("_compute_health: DB error for tenant=%s: %s", tenant_id, exc)
        return []

    if not rows:
        return []

    now_utc   = datetime.now(tz=timezone.utc)
    cutoff_7d = now_utc - timedelta(days=7)

    # Aggregate per provider
    by_provider: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        prov     = row.get("provider") or "unknown"
        status   = row.get("status")   or "unknown"
        synced   = row.get("synced_at")

        if prov not in by_provider:
            by_provider[prov] = {
                "provider":       prov,
                "ok_count":       0,
                "failed_count":   0,
                "dry_run_count":  0,
                "skipped_count":  0,
                "last_sync_at":   None,
                "_ok_7d":         0,
                "_failed_7d":     0,
            }

        agg = by_provider[prov]

        # Status counters (all time)
        if status == "ok":       agg["ok_count"]      += 1
        elif status == "failed": agg["failed_count"]  += 1
        elif status == "dry_run": agg["dry_run_count"] += 1
        elif status == "skipped": agg["skipped_count"] += 1

        # last_sync_at (newest-first from DB, so first row per provider wins
        # but we keep it safe by comparing)
        if agg["last_sync_at"] is None or (synced and synced > agg["last_sync_at"]):
            agg["last_sync_at"] = synced

        # 7-day window counters
        if synced:
            try:
                synced_dt = datetime.fromisoformat(synced.replace("Z", "+00:00"))
                if synced_dt >= cutoff_7d:
                    if status == "ok":     agg["_ok_7d"]     += 1
                    elif status == "failed": agg["_failed_7d"] += 1
            except (ValueError, AttributeError):
                pass  # malformed timestamp — skip

    # Build final list
    result_list = []
    for agg in by_provider.values():
        ok_7d     = agg.pop("_ok_7d")
        failed_7d = agg.pop("_failed_7d")
        denom     = ok_7d + failed_7d
        agg["failure_rate_7d"] = round(failed_7d / denom, 4) if denom > 0 else None
        result_list.append(agg)

    # Sort alphabetically by provider for stable output
    result_list.sort(key=lambda r: r["provider"])
    return result_list


# ---------------------------------------------------------------------------
# GET /admin/outbound-health  (Phase 146)
# ---------------------------------------------------------------------------

@router.get(
    "/admin/outbound-health",
    tags=["admin", "outbound"],
    summary="Per-provider outbound sync health dashboard",
    responses={
        200: {"description": "Per-provider sync health stats for this tenant"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_outbound_health(
    tenant_id: str           = Depends(jwt_auth),
    client:    Optional[Any] = None,
) -> JSONResponse:
    """
    Per-provider outbound sync health aggregate for the authenticated tenant.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Tenant isolation:** Only this tenant's sync attempts are included.

    **Response fields per provider:**
    - `provider`        — OTA provider name (e.g. `airbnb`, `bookingcom`)
    - `ok_count`        — total successful syncs (all time)
    - `failed_count`    — total failed syncs (all time)
    - `dry_run_count`   — total dry-run syncs (all time)
    - `skipped_count`   — total skipped actions (all time)
    - `last_sync_at`    — ISO timestamp of most recent sync attempt
    - `failure_rate_7d` — failed / (ok + failed) in last 7 days, null if no data

    **Ordering:** Alphabetical by provider name.

    **Source:** `outbound_sync_log` — read-only.

    Only providers with at least one row in `outbound_sync_log` are returned.
    An empty `providers` list means no syncs have been logged yet.
    """
    try:
        db       = client if client is not None else _get_supabase_client()
        providers = _compute_health(db, tenant_id)

        checked_at = datetime.now(tz=timezone.utc).isoformat()
        return JSONResponse(
            status_code=200,
            content={
                "tenant_id":   tenant_id,
                "provider_count": len(providers),
                "checked_at": checked_at,
                "providers":  providers,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/outbound-health error for tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Phase 147 — Replay helper + endpoint
# ---------------------------------------------------------------------------

@dataclass
class _ReplayRequest:
    booking_id: str
    provider:   str


def _fetch_last_log_row(
    db: Any,
    tenant_id:  str,
    booking_id: str,
    provider:   str,
) -> Optional[Dict[str, Any]]:
    """
    Find the most recent outbound_sync_log row for this tenant+booking+provider.
    Returns the full row dict or None if not found.
    Used by the replay endpoint to discover external_id and strategy.
    """
    try:
        result = (
            db.table("outbound_sync_log")
            .select("provider, external_id, strategy, status, synced_at")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .eq("provider", provider)
            .order("synced_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "_fetch_last_log_row error tenant=%s booking=%s provider=%s: %s",
            tenant_id, booking_id, provider, exc,
        )
        return None


@router.post(
    "/admin/outbound-replay",
    tags=["admin", "outbound"],
    summary="Replay a failed outbound sync for a specific booking+provider",
    responses={
        200: {"description": "Replay attempt completed (check result.status for outcome)"},
        400: {"description": "Missing required fields in request body"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "No prior sync log row found for this booking+provider"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def replay_outbound_sync(
    body:      Dict[str, Any],
    tenant_id: str           = Depends(jwt_auth),
    client:    Optional[Any] = None,
) -> JSONResponse:
    """
    Re-execute the most recent outbound sync attempt for `booking_id + provider`.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Tenant isolation:** Only this tenant's log rows are considered.

    **Body fields:**
    - `booking_id` — required, the booking to replay
    - `provider`   — required, the OTA provider to re-target (e.g. `airbnb`)

    **Behaviour:**
    - Looks up the most recent `outbound_sync_log` row for this booking+provider+tenant.
    - Re-uses the `external_id` and `strategy` from that row.
    - Calls `execute_single_provider()` — the full fail-isolated executor path.
    - The new result is persisted to `outbound_sync_log` (best-effort).
    - Returns 200 with the result envelope regardless of whether the sync succeeded.
      Inspect `.result.status` (`ok` / `failed` / `dry_run`) to see the outcome.
    - Returns **404** if no prior log row exists (nothing to replay).
    - Returns **400** if `booking_id` or `provider` is missing from the body.

    **Source:** `outbound_sync_log` — reads to discover parameters, then writes via executor.
    """
    # Validate body
    booking_id = (body.get("booking_id") or "").strip()
    provider   = (body.get("provider")   or "").strip()

    if not booking_id or not provider:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'booking_id' and 'provider' are required"},
        )

    try:
        db  = client if client is not None else _get_supabase_client()
        row = _fetch_last_log_row(db, tenant_id, booking_id, provider)

        if row is None:
            return make_error_response(
                status_code=404,
                code=ErrorCode.BOOKING_NOT_FOUND,
                extra={
                    "booking_id": booking_id,
                    "provider":   provider,
                    "detail":     "No prior sync log entry found for this booking+provider",
                },
            )

        external_id = row.get("external_id") or ""
        strategy    = row.get("strategy")    or "api_first"

        # Import here (lazy) — mirrors the admin_router.py lazy import pattern
        from services.outbound_executor import execute_single_provider, serialise_report  # noqa: PLC0415

        report = execute_single_provider(
            booking_id=booking_id,
            property_id="",         # not stored in sync log; replay operates without it
            tenant_id=tenant_id,
            provider=provider,
            external_id=external_id,
            strategy=strategy,
        )

        serialised = serialise_report(report)
        # Flatten for readability — there is exactly one result entry
        result_entry = serialised["results"][0] if serialised["results"] else {}

        return JSONResponse(
            status_code=200,
            content={
                "replayed":   True,
                "booking_id": booking_id,
                "provider":   provider,
                "tenant_id":  tenant_id,
                "result":     result_entry,
                "replayed_at": datetime.now(tz=timezone.utc).isoformat(),
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "POST /admin/outbound-replay error booking=%s provider=%s tenant=%s: %s",
            booking_id, provider, tenant_id, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
