"""
Phase 182 — Outbound Sync Auto-Trigger for BOOKING_AMENDED

Mirrors outbound_created_sync.py (Phase 176) for the BOOKING_AMENDED lifecycle event.

When BOOKING_AMENDED is APPLIED, this module fires the full outbound sync
plan (build_sync_plan → execute_sync_plan), covering ALL configured channels:
  - api_first providers: Airbnb, Booking.com, Expedia/VRBO
  - ical_fallback providers: Hotelbeds, TripAdvisor, Despegar, etc.

Phase 141-144 guarantees apply automatically via execute_sync_plan:
  - Rate-limit enforcement (Phase 141)
  - Exponential backoff retry (Phase 142)
  - Idempotency key: {booking_id}:{external_id}:{YYYYMMDD} (Phase 143)
  - Sync log persistence to outbound_sync_log table (Phase 144)

Phase 209 — Trigger Consolidation:
  The old fast-path trigger (amend_sync_trigger.py, Phase 152/155) has been
  removed. This module is now the SOLE outbound sync path for BOOKING_AMENDED.
  service.py calls fire_amended_sync() only — no dual triggers.

The amended booking dates (check_in, check_out) are passed through via
context fields so adapters that need them can extract them from the
standard booking_state query inside execute_sync_plan. The dates are
also stored in action.metadata for adapters that require explicit date
parameters (e.g., ICalPushAdapter in Phase 140).

Design (identical to outbound_created_sync.py):
  - Best-effort — never raises, never blocks the main ingest response.
  - channels and registry params allow full DI for unit tests (no live DB).
  - On any exception → log warning, swallow, return [].
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from services.outbound_sync_trigger import build_sync_plan
from services.outbound_executor import execute_sync_plan

logger = logging.getLogger(__name__)


@dataclass
class AmendedSyncResult:
    """Result of a single outbound sync attempt after BOOKING_AMENDED."""
    provider: str
    external_id: str
    strategy: str        # api_first | ical_fallback | skip
    status: str          # ok | failed | dry_run | skipped
    message: str


def _get_channels(property_id: str, tenant_id: str) -> list[dict]:
    """
    Fetch all property_channel_map rows for (property_id, tenant_id).
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
        logger.warning("outbound_amended_sync: channel DB lookup failed: %s", exc)
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
        logger.warning("outbound_amended_sync: registry DB lookup failed: %s", exc)
        return {}


def fire_amended_sync(
    *,
    booking_id: str,
    property_id: str,
    tenant_id: str,
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
    channels: Optional[List[Dict[str, Any]]] = None,
    registry: Optional[Dict[str, Any]] = None,
) -> List[AmendedSyncResult]:
    """
    Fire the full outbound sync plan for a BOOKING_AMENDED event.

    Applies all Phase 141-144 guarantees (rate-limit, retry, idempotency,
    sync log persistence) via build_sync_plan → execute_sync_plan.

    Args:
        booking_id:   Canonical booking_id ({provider}_{normalized_ref}).
        property_id:  Used to look up property_channel_map.
        tenant_id:    Tenant scope for DB queries.
        check_in:     New check-in date (ISO YYYY-MM-DD or YYYYMMDD). Optional.
        check_out:    New check-out date (ISO YYYY-MM-DD or YYYYMMDD). Optional.
        channels:     Optional — inject channel list directly (testing).
        registry:     Optional — inject registry dict directly (testing).

    Returns:
        List of AmendedSyncResult, one per action in the plan.
        Returns [] if channels is empty or all are skipped.
    """
    resolved_channels = channels if channels is not None else _get_channels(
        property_id, tenant_id
    )
    resolved_registry = registry if registry is not None else _get_registry()

    if not resolved_channels:
        logger.debug(
            "outbound_amended_sync: no channels for property=%s booking=%s — skipping",
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
            "outbound_amended_sync: build_sync_plan failed for booking=%s: %s",
            booking_id, exc,
        )
        return []

    try:
        report = execute_sync_plan(
            booking_id=booking_id,
            property_id=property_id,
            tenant_id=tenant_id,
            actions=actions,
            check_in=check_in,   # forwarded to iCal adapters (Phase 140)
            check_out=check_out, # forwarded to iCal adapters (Phase 140)
            event_type="BOOKING_AMENDED",  # Phase 185: route to .amend() on API adapters
        )
    except Exception as exc:
        logger.warning(
            "outbound_amended_sync: execute_sync_plan failed for booking=%s: %s",
            booking_id, exc,
        )
        return []

    return [
        AmendedSyncResult(
            provider=r.provider,
            external_id=r.external_id,
            strategy=r.strategy,
            status=r.status,
            message=r.message,
        )
        for r in report.results
    ]
