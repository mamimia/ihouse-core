"""
Phase 176 — Outbound Sync Auto-Trigger for BOOKING_CREATED

When BOOKING_CREATED is APPLIED, this module fires the full outbound sync
plan to all configured channels for the property:
  1. Fetches property_channel_map rows for (property_id, tenant_id)
  2. Fetches provider_capability_registry rows → builds {provider: row} dict
  3. Calls build_sync_plan(booking_id, property_id, channels, registry)
  4. Calls execute_sync_plan(booking_id, property_id, tenant_id, actions)
  5. Returns list of CreatedSyncResult (pure data, no side-effects beyond HTTP)

Design:
  - Shared pattern with outbound_canceled_sync.py and outbound_amended_sync.py.
  - Best-effort — never raises, never blocks the main ingest response.
  - channels and registry params allow full DI for unit tests (no live DB).
  - On any exception → log warning, swallow, return [].

Invariants honoured:
  - Outbound sync is always best-effort and non-blocking (Phase 135).
  - apply_envelope is NEVER called from here.
  - Callback/sync failures are always swallowed (Phase 148 pattern).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Top-level imports make these patchable in tests
from services.outbound_sync_trigger import build_sync_plan
from services.outbound_executor import execute_sync_plan

logger = logging.getLogger(__name__)


@dataclass
class CreatedSyncResult:
    """Result of a single outbound sync attempt after BOOKING_CREATED."""
    provider: str
    external_id: str
    strategy: str        # api_first | ical_fallback | skip
    status: str          # ok | failed | dry_run | skipped
    message: str


def _get_channels(property_id: str, tenant_id: str) -> list[dict]:
    """
    Fetch all property_channel_map rows for this (property_id, tenant_id).
    Returns [] on any DB error — never raises.
    """
    try:
        from supabase import create_client  # type: ignore[import]
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")
        if not url or not key:
            return []
        client = create_client(url, key)
        result = (
            client.table("property_channel_map")
            .select("provider,external_id,sync_strategy,sync_mode,enabled,timezone")
            .eq("property_id", property_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.warning("outbound_created_sync: channel DB lookup failed: %s", exc)
        return []


def _get_registry() -> Dict[str, Any]:
    """
    Fetch all provider_capability_registry rows.
    Returns {provider: row} dict. Returns {} on any DB error — never raises.
    """
    try:
        from supabase import create_client  # type: ignore[import]
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")
        if not url or not key:
            return {}
        client = create_client(url, key)
        result = (
            client.table("provider_capability_registry")
            .select(
                "provider,tier,supports_api_write,supports_ical_push,"
                "supports_ical_pull,rate_limit_per_min"
            )
            .execute()
        )
        rows = result.data or []
        return {r["provider"]: r for r in rows if r.get("provider")}
    except Exception as exc:
        logger.warning("outbound_created_sync: registry DB lookup failed: %s", exc)
        return {}


def fire_created_sync(
    *,
    booking_id: str,
    property_id: str,
    tenant_id: str,
    # Dependency injection for testing — skip DB if supplied directly
    channels: Optional[List[Dict[str, Any]]] = None,
    registry: Optional[Dict[str, Any]] = None,
) -> List[CreatedSyncResult]:
    """
    Fire the full outbound sync plan for a newly APPLIED booking.

    Calls build_sync_plan → execute_sync_plan with the full adapter registry,
    rate-limit throttle, retry backoff, idempotency key, and sync log
    persistence (all Phase 141-144 guarantees apply via execute_sync_plan).

    Args:
        booking_id:   Canonical booking_id ({provider}_{normalized_ref}).
        property_id:  Used to look up property_channel_map.
        tenant_id:    Tenant scope for DB queries.
        channels:     Optional — inject channel list directly (testing).
        registry:     Optional — inject registry dict directly (testing).

    Returns:
        List of CreatedSyncResult, one per action in the plan.
        Returns [] if channels is empty or all are skipped.
    """
    resolved_channels = channels if channels is not None else _get_channels(
        property_id, tenant_id
    )
    resolved_registry = registry if registry is not None else _get_registry()

    if not resolved_channels:
        logger.debug(
            "outbound_created_sync: no channels for property=%s booking=%s — skipping",
            property_id, booking_id,
        )
        return []

    try:
        actions = build_sync_plan(
            booking_id=booking_id,
            property_id=property_id,
            channels=resolved_channels,
            registry=resolved_registry,
        )
    except Exception as exc:
        logger.warning(
            "outbound_created_sync: build_sync_plan failed for booking=%s: %s",
            booking_id, exc,
        )
        return []

    try:
        report = execute_sync_plan(
            booking_id=booking_id,
            property_id=property_id,
            tenant_id=tenant_id,
            actions=actions,
        )
    except Exception as exc:
        logger.warning(
            "outbound_created_sync: execute_sync_plan failed for booking=%s: %s",
            booking_id, exc,
        )
        return []

    return [
        CreatedSyncResult(
            provider=r.provider,
            external_id=r.external_id,
            strategy=r.strategy,
            status=r.status,
            message=r.message,
        )
        for r in report.results
    ]
