"""
Phase 151 — iCal Cancellation Push Trigger
Phase 154 — API-first Cancellation Push (Airbnb, Booking.com, Expedia/VRBO)

When BOOKING_CANCELED is APPLIED, this module fires cancellation signals to:
  1. All iCal (ical_fallback) providers via ICalPushAdapter.cancel()  [Phase 151]
  2. All api_first API providers via their adapter's cancel() method  [Phase 154]

Design:
  - Mirrors the pattern of task_writer.py — best-effort, never blocks.
  - Iterates property_channel_map for the (property_id, tenant_id) pair.
  - iCal providers: calls ICalPushAdapter(provider).cancel(external_id, booking_id)
  - API providers:  calls <Adapter>(provider).cancel(external_id, booking_id)
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

# Providers served by API-first adapters (Phase 154)
_API_PROVIDERS = {"airbnb", "bookingcom", "expedia", "vrbo"}


@dataclass
class CancelSyncResult:
    """Result of a single provider cancellation attempt."""
    provider: str
    external_id: str
    status: str          # 'ok' | 'failed' | 'dry_run' | 'skipped'
    message: str


def _get_channels(property_id: str, tenant_id: str) -> list[dict]:
    """
    Fetch ALL property_channel_map rows for this property/tenant,
    regardless of sync_strategy. Returns [] on any DB error.
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
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.warning("cancel_sync_trigger: DB lookup failed: %s", exc)
        return []


def _get_api_adapter(provider: str):
    """
    Return an instantiated API-first adapter for the given provider, or None.
    Lazy import to avoid circular dependencies.
    """
    try:
        if provider == "airbnb":
            from adapters.outbound.airbnb_adapter import AirbnbAdapter
            return AirbnbAdapter()
        if provider == "bookingcom":
            from adapters.outbound.bookingcom_adapter import BookingComAdapter
            return BookingComAdapter()
        if provider in ("expedia", "vrbo"):
            from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
            return ExpediaVrboAdapter(provider)
    except Exception as exc:  # noqa: BLE001
        logger.warning("cancel_sync_trigger: could not load adapter for %s: %s", provider, exc)
    return None


def fire_cancel_sync(
    *,
    booking_id: str,
    property_id: str,
    tenant_id: str,
    # Dependency injection for testing — skip DB if channels supplied directly
    channels: Optional[list[dict]] = None,
) -> list[CancelSyncResult]:
    """
    Fire cancel push for all mapped channels of the property.

    - ical_fallback channels  → ICalPushAdapter.cancel()
    - api_first channels      → {Provider}Adapter.cancel()

    Args:
        booking_id:   Canonical booking_id.
        property_id:  Used to look up property_channel_map.
        tenant_id:    Tenant scope for DB query.
        channels:     Optional — inject channel list directly (testing).

    Returns:
        List of CancelSyncResult, one per channel attempted.
    """
    from adapters.outbound.ical_push_adapter import ICalPushAdapter

    resolved_channels = channels if channels is not None else _get_channels(property_id, tenant_id)
    results: list[CancelSyncResult] = []

    for ch in resolved_channels:
        provider    = ch.get("provider", "")
        external_id = ch.get("external_id", "")
        strategy    = ch.get("sync_strategy", "")

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

        # ------------------------------------------------------------------
        # Route: iCal providers
        # ------------------------------------------------------------------
        if provider in _ICAL_PROVIDERS:
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
                    "cancel_sync_trigger: iCal cancel failed for %s/%s: %s",
                    provider, external_id, exc,
                )
                results.append(CancelSyncResult(
                    provider=provider,
                    external_id=external_id,
                    status="failed",
                    message=f"Exception during iCal cancel: {exc}",
                ))
            continue

        # ------------------------------------------------------------------
        # Route: API-first providers (Phase 154)
        # ------------------------------------------------------------------
        if provider in _API_PROVIDERS:
            adapter = _get_api_adapter(provider)
            if adapter is None:
                results.append(CancelSyncResult(
                    provider=provider,
                    external_id=external_id,
                    status="skipped",
                    message=f"Could not load API adapter for {provider!r}.",
                ))
                continue
            try:
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
                    "cancel_sync_trigger: API cancel failed for %s/%s: %s",
                    provider, external_id, exc,
                )
                results.append(CancelSyncResult(
                    provider=provider,
                    external_id=external_id,
                    status="failed",
                    message=f"Exception during API cancel: {exc}",
                ))
            continue

        # ------------------------------------------------------------------
        # Unknown provider
        # ------------------------------------------------------------------
        logger.warning(
            "cancel_sync_trigger: provider %s is not a known cancel provider — skipping",
            provider,
        )
        results.append(CancelSyncResult(
            provider=provider,
            external_id=external_id,
            status="skipped",
            message=f"Provider {provider!r} is not a known cancel provider.",
        ))

    return results
