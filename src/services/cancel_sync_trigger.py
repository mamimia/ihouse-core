"""
Phase 151 — iCal Cancellation Push Trigger

When BOOKING_CANCELED is APPLIED, this module fires a best-effort iCal
cancellation push to all iCal (ical_fallback) providers mapped for the
booking's property.

Design:
  - Mirrors the pattern of task_writer.py — best-effort, never blocks.
  - Iterates property_channel_map for the (property_id, tenant_id) pair.
  - Calls ICalPushAdapter(provider).cancel(external_id, booking_id) for
    every channel whose sync_strategy is 'ical_fallback'.
  - On any exception → log warning, swallow, continue to next provider.
  - Returns a list of CancelSyncResult (pure data, no side-effects beyond
    the HTTP calls).

Invariants honoured:
  - iCal is degraded-mode only — never the primary sync strategy (Phase 135).
  - Outbound sync is always best-effort and non-blocking (Phase 135).
  - Callback/sync failures are always swallowed (Phase 148 pattern).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Providers served by ICalPushAdapter
_ICAL_PROVIDERS = {"hotelbeds", "tripadvisor", "despegar"}


@dataclass
class CancelSyncResult:
    """Result of a single provider cancellation attempt."""
    provider: str
    external_id: str
    status: str          # 'ok' | 'failed' | 'dry_run' | 'skipped'
    message: str


def _get_ical_channels(property_id: str, tenant_id: str) -> list[dict]:
    """
    Fetch property_channel_map rows for this property/tenant where
    sync_strategy = 'ical_fallback'.

    Returns list of dicts with keys: provider, external_id.
    Returns [] on any DB error (best-effort path).
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
            .select("provider,external_id,sync_strategy")
            .eq("property_id", property_id)
            .eq("tenant_id", tenant_id)
            .eq("sync_strategy", "ical_fallback")
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.warning("cancel_sync_trigger: DB lookup failed: %s", exc)
        return []


def fire_cancel_sync(
    *,
    booking_id: str,
    property_id: str,
    tenant_id: str,
    # Dependency injection for testing — skip DB if channels supplied directly
    channels: Optional[list[dict]] = None,
) -> list[CancelSyncResult]:
    """
    Fire iCal cancel push for all ical_fallback channels of property.

    Args:
        booking_id:   Canonical booking_id (used in VEVENT UID).
        property_id:  Used to look up property_channel_map.
        tenant_id:    Tenant scope for DB query.
        channels:     Optional — inject channel list directly (testing).

    Returns:
        List of CancelSyncResult, one per channel attempted.
    """
    from adapters.outbound.ical_push_adapter import ICalPushAdapter

    resolved_channels = channels if channels is not None else _get_ical_channels(property_id, tenant_id)
    results: list[CancelSyncResult] = []

    for ch in resolved_channels:
        provider    = ch.get("provider", "")
        external_id = ch.get("external_id", "")

        if not provider or not external_id:
            logger.warning(
                "cancel_sync_trigger: skipping channel with missing fields: %s", ch
            )
            results.append(CancelSyncResult(
                provider=provider or "unknown",
                external_id=external_id or "unknown",
                status="skipped",
                message="Missing provider or external_id in channel map row.",
            ))
            continue

        if provider not in _ICAL_PROVIDERS:
            logger.warning(
                "cancel_sync_trigger: provider %s is not an iCal provider — skipping", provider
            )
            results.append(CancelSyncResult(
                provider=provider,
                external_id=external_id,
                status="skipped",
                message=f"Provider {provider!r} is not an ical_fallback provider.",
            ))
            continue

        try:
            adapter = ICalPushAdapter(provider)
            adapter_result = adapter.cancel(
                external_id=external_id,
                booking_id=booking_id,
            )
            results.append(CancelSyncResult(
                provider=provider,
                external_id=external_id,
                status=adapter_result.status,
                message=adapter_result.message,
            ))
        except Exception as exc:
            logger.warning(
                "cancel_sync_trigger: cancel failed for %s/%s: %s",
                provider, external_id, exc,
            )
            results.append(CancelSyncResult(
                provider=provider,
                external_id=external_id,
                status="failed",
                message=f"Exception during cancel: {exc}",
            ))

    return results
