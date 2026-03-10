"""
Phase 173 — IPI: Proactive Availability Broadcasting

Extends the outbound sync pipeline to support property-level broadcast
of availability windows to ALL mapped channels when triggered by:
  - A new property being registered (onboarding broadcast)
  - A channel map change (new channel added / sync_mode changed)

Design: this module is a thin orchestration layer that sits ABOVE the
existing Phase 137/138 sync trigger + executor foundation.

Architecture fit (as documented in outbound-sync-layer.md):
  - Reads from property_channel_map (Phase 135)
  - Reads from provider_capability_registry (Phase 136)
  - Uses build_sync_plan() from outbound_sync_trigger (Phase 137)
  - Delegates execution to execute_sync_plan() from outbound_executor (Phase 138)
  - All Phase 141-144 guarantees apply: throttle, retry, idempotency key,
    sync_log persistence.
  - Never writes to booking_state or event_log.
  - apply_envelope is NOT involved.

Difference from the per-booking trigger (Phase 137):
  - The Phase 137 trigger fires for a SINGLE booking after BOOKING_CREATED/CANCELED APPLIED.
  - THIS broadcaster fires for a PROPERTY across ALL its active bookings
    when the property's channel configuration changes.
  - It produces one SyncAction list per booking, not globally.

Broadcast modes:
  PROPERTY_ONBOARDED — new property registered: broadcast all active bookings
                        to all mapped channels (closes the availability gaps
                        for existing bookings that were there before the mapping)
  CHANNEL_ADDED      — new channel mapping added: broadcast all active bookings
                        for the property only to the newly added channel

Invariants:
  - Best-effort: never raises. One booking/channel failure does not block others.
  - apply_envelope is never called.
  - Source channel is never included in outbound targets (same rule as Phase 137).
  - Skipped channels are logged but do not affect broadcast outcome.
  - Dry-run safe: respects IHOUSE_DRY_RUN env var via adapter registry.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.outbound_sync_trigger import build_sync_plan, SyncAction
from services.outbound_executor import execute_sync_plan, ExecutionReport

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Broadcast modes
# ---------------------------------------------------------------------------

class BroadcastMode:
    PROPERTY_ONBOARDED = "PROPERTY_ONBOARDED"
    CHANNEL_ADDED      = "CHANNEL_ADDED"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class BookingBroadcastResult:
    """
    Outcome for broadcasting one booking's availability to mapped channels.
    """
    booking_id:     str
    property_id:    str
    ok_count:       int
    failed_count:   int
    skip_count:     int
    dry_run:        bool
    error:          Optional[str] = None   # set if executor raised (should never happen)


@dataclass
class BroadcastReport:
    """
    Aggregate outcome of a property-level availability broadcast.

    Attributes:
        property_id:    The property that was broadcast.
        mode:           BroadcastMode — why the broadcast was triggered.
        bookings_found: Number of active booking_ids resolved.
        bookings_ok:    Bookings where all channels returned ok or dry_run.
        bookings_failed:Bookings where at least one channel failed.
        bookings_skipped:Bookings where all channels were skipped.
        results:        Per-booking results.
    """
    property_id:      str
    mode:             str
    bookings_found:   int
    bookings_ok:      int
    bookings_failed:  int
    bookings_skipped: int
    results:          List[BookingBroadcastResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Channel / registry data fetchers (injected in tests)
# ---------------------------------------------------------------------------

def _fetch_channels(
    db: Any,
    tenant_id: str,
    property_id: str,
    target_provider: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch property_channel_map rows for this property.

    If target_provider is set (CHANNEL_ADDED mode), returns only that channel.
    Otherwise returns all enabled channels.
    """
    q = (
        db.table("property_channel_map")
        .select("provider, external_id, sync_mode, enabled")
        .eq("tenant_id", tenant_id)
        .eq("property_id", property_id)
        .eq("enabled", True)
    )
    if target_provider:
        q = q.eq("provider", target_provider)
    result = q.execute()
    return result.data or []


def _fetch_registry(db: Any) -> Dict[str, Dict[str, Any]]:
    """
    Fetch all provider_capability_registry rows, keyed by provider name.
    """
    result = (
        db.table("provider_capability_registry")
        .select("provider, tier, supports_api_write, supports_ical_push, "
                "supports_ical_pull, rate_limit_per_min")
        .execute()
    )
    rows = result.data or []
    return {r["provider"]: r for r in rows}


def _fetch_active_booking_ids(
    db: Any,
    tenant_id: str,
    property_id: str,
) -> List[str]:
    """
    Fetch booking_ids for all ACTIVE (non-canceled) bookings for this property.

    Reads from booking_state (canonical operational read model).
    Returns a list of booking_id strings. Empty list if none.
    """
    result = (
        db.table("booking_state")
        .select("booking_id")
        .eq("tenant_id", tenant_id)
        .eq("property_id", property_id)
        .neq("status", "canceled")
        .execute()
    )
    rows = result.data or []
    return [r["booking_id"] for r in rows]


# ---------------------------------------------------------------------------
# Core broadcast function
# ---------------------------------------------------------------------------

def broadcast_availability(
    db: Any,
    *,
    tenant_id: str,
    property_id: str,
    mode: str,
    source_provider: Optional[str] = None,
    target_provider: Optional[str] = None,
    api_adapter: Optional[Any] = None,
    ical_adapter: Optional[Any] = None,
) -> BroadcastReport:
    """
    Broadcast availability for all active bookings of a property to mapped channels.

    This is the IPI (proactive) counterpart to the reactive per-booking trigger
    (Phase 137). It covers the cases where a property onboards or gains a new
    channel mapping after bookings already exist.

    Args:
        db:               Supabase client.
        tenant_id:        Tenant performing the broadcast.
        property_id:      Property to broadcast for.
        mode:             BroadcastMode — PROPERTY_ONBOARDED or CHANNEL_ADDED.
        source_provider:  exclude this provider from sync targets (the source OTA,
                          if relevant). None = no exclusion.
        target_provider:  in CHANNEL_ADDED mode, only sync to this provider.
        api_adapter:      Injectable for testing.
        ical_adapter:     Injectable for testing.

    Returns:
        BroadcastReport with per-booking outcomes.

    Notes:
        - Best-effort. Never raises. One failure does not block others.
        - All Phase 141-144 guarantees apply via execute_sync_plan().
        - Reads booking_state for active booking IDs.
        - Reads property_channel_map and provider_capability_registry for sync plan.
    """
    report = BroadcastReport(
        property_id=property_id,
        mode=mode,
        bookings_found=0,
        bookings_ok=0,
        bookings_failed=0,
        bookings_skipped=0,
    )

    try:
        # 1. Resolve channels to target
        channels = _fetch_channels(
            db, tenant_id, property_id,
            target_provider=target_provider,
        )
        if not channels:
            logger.info(
                "broadcast_availability: no enabled channels for "
                "property=%s tenant=%s mode=%s — nothing to do",
                property_id, tenant_id, mode,
            )
            return report

        # Exclude source provider (same rule as Phase 137)
        if source_provider:
            channels = [c for c in channels if c.get("provider") != source_provider]

        if not channels:
            logger.info(
                "broadcast_availability: all channels are the source provider — skip "
                "property=%s source_provider=%s",
                property_id, source_provider,
            )
            return report

        # 2. Resolve provider capability registry
        registry = _fetch_registry(db)

        # 3. Fetch active booking IDs
        booking_ids = _fetch_active_booking_ids(db, tenant_id, property_id)
        report.bookings_found = len(booking_ids)

        if not booking_ids:
            logger.info(
                "broadcast_availability: no active bookings for property=%s tenant=%s",
                property_id, tenant_id,
            )
            return report

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "broadcast_availability: DB setup failed for property=%s tenant=%s: %s",
            property_id, tenant_id, exc,
        )
        return report

    # 4. For each active booking: build sync plan → execute
    for booking_id in booking_ids:
        try:
            actions: List[SyncAction] = build_sync_plan(
                booking_id=booking_id,
                property_id=property_id,
                channels=channels,
                registry=registry,
            )

            exec_report: ExecutionReport = execute_sync_plan(
                booking_id=booking_id,
                property_id=property_id,
                tenant_id=tenant_id,
                actions=actions,
                api_adapter=api_adapter,
                ical_adapter=ical_adapter,
            )

            booking_result = BookingBroadcastResult(
                booking_id=booking_id,
                property_id=property_id,
                ok_count=exec_report.ok_count,
                failed_count=exec_report.failed_count,
                skip_count=exec_report.skip_count,
                dry_run=exec_report.dry_run,
            )

            if exec_report.failed_count > 0:
                report.bookings_failed += 1
            elif exec_report.ok_count > 0 or exec_report.dry_run:
                report.bookings_ok += 1
            else:
                report.bookings_skipped += 1

        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "broadcast_availability: executor error booking=%s property=%s: %s",
                booking_id, property_id, exc,
            )
            booking_result = BookingBroadcastResult(
                booking_id=booking_id,
                property_id=property_id,
                ok_count=0,
                failed_count=1,
                skip_count=0,
                dry_run=False,
                error=str(exc),
            )
            report.bookings_failed += 1

        report.results.append(booking_result)

    return report


def serialise_broadcast_report(report: BroadcastReport) -> Dict[str, Any]:
    """JSON-serialisable form of BroadcastReport for the API response."""
    return {
        "property_id":      report.property_id,
        "mode":             report.mode,
        "bookings_found":   report.bookings_found,
        "bookings_ok":      report.bookings_ok,
        "bookings_failed":  report.bookings_failed,
        "bookings_skipped": report.bookings_skipped,
        "results": [
            {
                "booking_id":   r.booking_id,
                "ok_count":     r.ok_count,
                "failed_count": r.failed_count,
                "skip_count":   r.skip_count,
                "dry_run":      r.dry_run,
                "error":        r.error,
            }
            for r in report.results
        ],
    }
