"""
Phase 217 — Integration Management UI

Admin surface for managing OTA connections and viewing sync status per property-channel pair.

This is the management-layer read endpoint that powers the Integration Management UI.
It provides a cross-property, cross-provider view of all channel connections,
enriched with their last sync status and health signal.

Endpoints:
    GET /admin/integrations
        Cross-property, cross-provider view of all channel mappings for this tenant.
        Enriched with last sync attempt (status, executed_at, error_message).
        Grouped by property_id. Supports filtering by provider or enabled status.

    GET /admin/integrations/summary
        Tenant-level integration summary: total connections, enabled count,
        stale count, failed connections, provider distribution.

Design:
    - Reads `property_channel_map` (channel configuration).
    - Reads `outbound_sync_log` (last sync status per property-provider pair).
    - Join is done in-memory — no JOINs in the DB.
    - Stale threshold: same as Phase 127 integration health router (24 hours).
    - Each connection entry contains full channel map config + last sync context.
    - Sorted within each property: enabled first, then alphabetical by provider.
    - Read-only. Never writes to any table.

Invariants:
    - JWT auth required.
    - Tenant isolation on all queries.
    - Never reads or writes booking_state.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["integrations"])

_STALE_HOURS = 24


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_channel_map(db: Any, tenant_id: str, provider_filter: Optional[str],
                       enabled_filter: Optional[bool]) -> List[dict]:
    try:
        q = (
            db.table("property_channel_map")
            .select("*")
            .eq("tenant_id", tenant_id)
        )
        if provider_filter:
            q = q.eq("provider", provider_filter)
        if enabled_filter is not None:
            q = q.eq("enabled", enabled_filter)
        result = q.order("property_id", desc=False).order("provider", desc=False).execute()
        return result.data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("_fetch_channel_map error: %s", exc)
        return []


def _fetch_last_sync_per_pair(db: Any, tenant_id: str) -> Dict[str, dict]:
    """Return dict keyed (property_id, provider) → most-recent outbound_sync_log row."""
    try:
        result = (
            db.table("outbound_sync_log")
            .select("property_id, provider, status, executed_at, error_message")
            .eq("tenant_id", tenant_id)
            .order("executed_at", desc=True)
            .limit(1000)
            .execute()
        )
        rows = result.data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("_fetch_last_sync_per_pair error: %s", exc)
        return {}

    # For each (property_id, provider) take the most-recent row
    best: Dict[str, dict] = {}
    for row in rows:
        key = f"{row.get('property_id')}:{row.get('provider')}"
        if key not in best or (row.get("executed_at") or "") > (best[key].get("executed_at") or ""):
            best[key] = row
    return best


def _is_stale(executed_at: Optional[str], now_iso: str) -> Optional[bool]:
    if not executed_at:
        return None
    try:
        delta = (
            datetime.fromisoformat(now_iso.replace("Z", ""))
            - datetime.fromisoformat(executed_at.replace("Z", "").replace("+00:00", ""))
        ).total_seconds()
        return delta > (_STALE_HOURS * 3600)
    except Exception:  # noqa: BLE001
        return None


def _build_connection(row: dict, sync_row: Optional[dict], now_iso: str) -> Dict[str, Any]:
    """Build one connection card from a channel_map row + optional last sync row."""
    last_sync_at     = sync_row.get("executed_at") if sync_row else None
    last_sync_status = sync_row.get("status") if sync_row else None
    last_sync_error  = sync_row.get("error_message") if sync_row else None
    stale            = _is_stale(last_sync_at, now_iso)

    return {
        "property_id":    row.get("property_id"),
        "provider":       row.get("provider"),
        "external_id":    row.get("external_id"),
        "inventory_type": row.get("inventory_type", "single_unit"),
        "sync_mode":      row.get("sync_mode", "api_first"),
        "enabled":        row.get("enabled", True),
        "created_at":     row.get("created_at"),
        "updated_at":     row.get("updated_at"),
        "last_sync": {
            "executed_at": last_sync_at,
            "status":      last_sync_status,
            "error":       last_sync_error,
            "stale":       stale,
        },
    }


# ---------------------------------------------------------------------------
# GET /admin/integrations
# ---------------------------------------------------------------------------

@router.get(
    "/admin/integrations",
    tags=["integrations"],
    summary="Integration Management UI — all OTA connections with sync status (Phase 217)",
    description=(
        "Cross-property admin view of all OTA channel connections for this tenant.\\n\\n"
        "Each entry includes full channel map config (sync_mode, inventory_type, enabled) "
        "plus last sync context (executed_at, status, error, stale flag).\\n\\n"
        "**Grouped by property.** Sorted: enabled connections first, then by provider.\\n\\n"
        "**Filters (optional):**\\n"
        "- `provider` — filter by OTA provider name (exact match)\\n"
        "- `enabled` — filter by enabled status (`true`/`false`)\\n\\n"
        "**Stale threshold:** >24 hours since last sync attempt.\\n\\n"
        "**Source:** `property_channel_map` + `outbound_sync_log`. Read-only."
    ),
    responses={
        200: {"description": "Connection list grouped by property."},
        401: {"description": "Missing or invalid JWT."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_integrations(
    provider: Optional[str] = Query(default=None, description="Filter by provider name"),
    enabled:  Optional[bool] = Query(default=None, description="Filter by enabled status"),
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        now_iso = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        db = client if client is not None else _get_supabase_client()

        channel_rows = _fetch_channel_map(db, tenant_id, provider, enabled)
        sync_map     = _fetch_last_sync_per_pair(db, tenant_id)

        # Build connection cards
        connections: List[Dict[str, Any]] = []
        for row in channel_rows:
            key       = f"{row.get('property_id')}:{row.get('provider')}"
            sync_row  = sync_map.get(key)
            card      = _build_connection(row, sync_row, now_iso)
            connections.append(card)

        # Group by property_id
        by_property: Dict[str, list] = {}
        for c in connections:
            pid = c["property_id"] or "unknown"
            by_property.setdefault(pid, []).append(c)

        # Sort each property's connections: enabled first, then alphabetical provider
        for pid in by_property:
            by_property[pid].sort(key=lambda x: (not x.get("enabled", True), x.get("provider") or ""))

        # Build grouped output sorted by property_id
        properties_list = [
            {
                "property_id":        pid,
                "connection_count":   len(conns),
                "connections":        conns,
            }
            for pid, conns in sorted(by_property.items())
        ]

        # Aggregate stats
        total    = len(connections)
        n_enabled = sum(1 for c in connections if c.get("enabled"))
        n_stale  = sum(1 for c in connections if c.get("last_sync", {}).get("stale"))
        n_failed = sum(1 for c in connections if c.get("last_sync", {}).get("status") == "error")

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id":          tenant_id,
                "generated_at":       now_iso,
                "total_connections":  total,
                "enabled_count":      n_enabled,
                "stale_count":        n_stale,
                "failed_count":       n_failed,
                "property_count":     len(properties_list),
                "properties":         properties_list,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/integrations error tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /admin/integrations/summary
# ---------------------------------------------------------------------------

@router.get(
    "/admin/integrations/summary",
    tags=["integrations"],
    summary="Integration Management — tenant-level summary (Phase 217)",
    description=(
        "Lightweight summary of all OTA integrations for this tenant.\\n\\n"
        "Returns aggregate counts and provider distribution — useful for a dashboard header.\\n\\n"
        "**Source:** `property_channel_map` + `outbound_sync_log`. Read-only."
    ),
    responses={
        200: {"description": "Tenant integration summary."},
        401: {"description": "Missing or invalid JWT."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_integrations_summary(
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        now_iso = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        db = client if client is not None else _get_supabase_client()

        channel_rows = _fetch_channel_map(db, tenant_id, None, None)
        sync_map     = _fetch_last_sync_per_pair(db, tenant_id)

        total      = len(channel_rows)
        n_enabled  = sum(1 for r in channel_rows if r.get("enabled"))
        n_disabled = total - n_enabled

        # Provider distribution
        provider_counts: Dict[str, int] = {}
        n_stale  = 0
        n_failed = 0

        for row in channel_rows:
            prov = row.get("provider") or "unknown"
            provider_counts[prov] = provider_counts.get(prov, 0) + 1
            key = f"{row.get('property_id')}:{prov}"
            sync_row = sync_map.get(key)
            if sync_row:
                if _is_stale(sync_row.get("executed_at"), now_iso):
                    n_stale += 1
                if sync_row.get("status") == "error":
                    n_failed += 1

        provider_dist = [
            {"provider": p, "count": c}
            for p, c in sorted(provider_counts.items(), key=lambda x: -x[1])
        ]

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id":          tenant_id,
                "generated_at":       now_iso,
                "total_connections":  total,
                "enabled_count":      n_enabled,
                "disabled_count":     n_disabled,
                "stale_count":        n_stale,
                "failed_count":       n_failed,
                "providers":          provider_dist,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/integrations/summary error tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
