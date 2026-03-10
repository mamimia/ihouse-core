"""
Phase 152 — iCal Sync-on-Amendment Push Trigger

When BOOKING_AMENDED is APPLIED, this module fires a best-effort iCal
re-push to all iCal (ical_fallback) providers mapped for the booking's
property, using the updated check_in and check_out dates.

Design:
  - Mirrors cancel_sync_trigger.py (Phase 151) — best-effort, never blocks.
  - Iterates property_channel_map for the (property_id, tenant_id) pair.
  - Calls ICalPushAdapter(provider).push(external_id, booking_id, check_in,
    check_out) for every channel whose sync_strategy is 'ical_fallback'.
  - Dates are accepted in YYYYMMDD (compact) or YYYY-MM-DD (ISO) format;
    the helper _to_ical() normalises them.
  - On any exception → log warning, swallow, continue to next provider.
  - Returns a list of AmendSyncResult (pure data; not used for branching).

Invariants honoured:
  - iCal is degraded-mode only — never the primary sync strategy (Phase 135).
  - Outbound sync is always best-effort and non-blocking (Phase 135).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Providers served by ICalPushAdapter
_ICAL_PROVIDERS = {"hotelbeds", "tripadvisor", "despegar"}


def _to_ical(iso: Optional[str]) -> Optional[str]:
    """
    Convert ISO date (YYYY-MM-DD) or compact (YYYYMMDD) to YYYYMMDD.
    Returns None if the input is empty or None.
    """
    if not iso:
        return None
    return str(iso).replace("-", "")[:8]


@dataclass
class AmendSyncResult:
    """Result of a single provider amendment re-push attempt."""
    provider: str
    external_id: str
    status: str          # 'ok' | 'failed' | 'dry_run' | 'skipped'
    message: str


def _get_ical_channels(property_id: str, tenant_id: str) -> list[dict]:
    """
    Fetch property_channel_map rows for this property/tenant where
    sync_strategy = 'ical_fallback'.

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
            .select("provider,external_id,sync_strategy,timezone")
            .eq("property_id", property_id)
            .eq("tenant_id", tenant_id)
            .eq("sync_strategy", "ical_fallback")
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.warning("amend_sync_trigger: DB lookup failed: %s", exc)
        return []


def fire_amend_sync(
    *,
    booking_id: str,
    property_id: str,
    tenant_id: str,
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
    # Dependency injection for testing — skip DB if channels supplied directly
    channels: Optional[list[dict]] = None,
) -> list[AmendSyncResult]:
    """
    Re-push iCal block with updated dates for all ical_fallback channels.

    Args:
        booking_id:   Canonical booking_id.
        property_id:  Used to look up property_channel_map.
        tenant_id:    Tenant scope for DB query.
        check_in:     New check-in date (ISO or YYYYMMDD). May be None.
        check_out:    New check-out date (ISO or YYYYMMDD). May be None.
        channels:     Optional — inject channel list directly (testing).

    Returns:
        List of AmendSyncResult, one per channel attempted.
    """
    from adapters.outbound.ical_push_adapter import ICalPushAdapter

    resolved_channels = channels if channels is not None else _get_ical_channels(property_id, tenant_id)
    results: list[AmendSyncResult] = []

    # Normalise dates to YYYYMMDD; ICalPushAdapter.push() handles fallback
    # internally when None is passed in.
    ical_check_in  = _to_ical(check_in)
    ical_check_out = _to_ical(check_out)

    for ch in resolved_channels:
        provider    = ch.get("provider", "")
        external_id = ch.get("external_id", "")
        timezone    = ch.get("timezone")  # nullable — may be None

        if not provider or not external_id:
            logger.warning(
                "amend_sync_trigger: skipping channel with missing fields: %s", ch
            )
            results.append(AmendSyncResult(
                provider=provider or "unknown",
                external_id=external_id or "unknown",
                status="skipped",
                message="Missing provider or external_id in channel map row.",
            ))
            continue

        if provider not in _ICAL_PROVIDERS:
            logger.warning(
                "amend_sync_trigger: provider %s is not an iCal provider — skipping", provider
            )
            results.append(AmendSyncResult(
                provider=provider,
                external_id=external_id,
                status="skipped",
                message=f"Provider {provider!r} is not an ical_fallback provider.",
            ))
            continue

        try:
            adapter = ICalPushAdapter(provider)
            adapter_result = adapter.push(
                external_id=external_id,
                booking_id=booking_id,
                check_in=ical_check_in,
                check_out=ical_check_out,
                timezone=timezone,
            )
            results.append(AmendSyncResult(
                provider=provider,
                external_id=external_id,
                status=adapter_result.status,
                message=adapter_result.message,
            ))
        except Exception as exc:
            logger.warning(
                "amend_sync_trigger: push failed for %s/%s: %s",
                provider, external_id, exc,
            )
            results.append(AmendSyncResult(
                provider=provider,
                external_id=external_id,
                status="failed",
                message=f"Exception during amend push: {exc}",
            ))

    return results
