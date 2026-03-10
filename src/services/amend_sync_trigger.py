"""
Phase 152 — iCal Sync-on-Amendment Push Trigger
Phase 155 — API-first Amendment Push (Airbnb, Booking.com, Expedia/VRBO)

When BOOKING_AMENDED is APPLIED, this module fires amendment notifications to:
  1. All iCal (ical_fallback) providers via ICalPushAdapter.push()  [Phase 152]
  2. All api_first API providers via their adapter's amend() method [Phase 155]

Design:
  - Mirrors cancel_sync_trigger.py (Phase 154) — best-effort, never blocks.
  - Iterates property_channel_map for the (property_id, tenant_id) pair.
  - iCal providers: calls ICalPushAdapter(provider).push() with updated dates
  - API providers:  calls <Adapter>(provider).amend(external_id, booking_id,
    check_in, check_out) using the ISO date format they expect
  - Dates are accepted in YYYYMMDD (compact) or YYYY-MM-DD (ISO) format;
    _to_ical() normalises for iCal; _to_iso() normalises for API adapters.
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

# Providers served by API-first adapters (Phase 155)
_API_PROVIDERS = {"airbnb", "bookingcom", "expedia", "vrbo"}


def _to_ical(iso: Optional[str]) -> Optional[str]:
    """
    Convert ISO date (YYYY-MM-DD) or compact (YYYYMMDD) to YYYYMMDD.
    Returns None if the input is empty or None.
    """
    if not iso:
        return None
    return str(iso).replace("-", "")[:8]


def _to_iso(date_str: Optional[str]) -> Optional[str]:
    """
    Convert compact (YYYYMMDD) or ISO (YYYY-MM-DD) date to YYYY-MM-DD.
    API adapters (Airbnb, Booking.com, Expedia) expect ISO format.
    Returns None if the input is empty or None.
    """
    if not date_str:
        return None
    s = str(date_str).replace("-", "")[:8]
    if len(s) == 8:
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return date_str  # fallback: return as-is


@dataclass
class AmendSyncResult:
    """Result of a single provider amendment re-push attempt."""
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
            .select("provider,external_id,sync_strategy,timezone")
            .eq("property_id", property_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.warning("amend_sync_trigger: DB lookup failed: %s", exc)
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
        logger.warning("amend_sync_trigger: could not load adapter for %s: %s", provider, exc)
    return None


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
    Push amendment to all mapped channels.

    - ical_fallback channels  → ICalPushAdapter.push() with updated dates
    - api_first channels      → {Provider}Adapter.amend() with ISO dates

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

    resolved_channels = channels if channels is not None else _get_channels(property_id, tenant_id)
    results: list[AmendSyncResult] = []

    # Normalise dates for both paths
    ical_check_in  = _to_ical(check_in)
    ical_check_out = _to_ical(check_out)
    api_check_in   = _to_iso(check_in)
    api_check_out  = _to_iso(check_out)

    for ch in resolved_channels:
        provider    = ch.get("provider", "")
        external_id = ch.get("external_id", "")
        timezone    = ch.get("timezone")   # nullable — may be None

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

        # ------------------------------------------------------------------
        # Route: iCal providers (Phase 152)
        # ------------------------------------------------------------------
        if provider in _ICAL_PROVIDERS:
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
                    "amend_sync_trigger: iCal push failed for %s/%s: %s",
                    provider, external_id, exc,
                )
                results.append(AmendSyncResult(
                    provider=provider,
                    external_id=external_id,
                    status="failed",
                    message=f"Exception during iCal amend push: {exc}",
                ))
            continue

        # ------------------------------------------------------------------
        # Route: API-first providers (Phase 155)
        # ------------------------------------------------------------------
        if provider in _API_PROVIDERS:
            adapter = _get_api_adapter(provider)
            if adapter is None:
                results.append(AmendSyncResult(
                    provider=provider,
                    external_id=external_id,
                    status="skipped",
                    message=f"Could not load API adapter for {provider!r}.",
                ))
                continue
            try:
                adapter_result = adapter.amend(
                    external_id=external_id,
                    booking_id=booking_id,
                    check_in=api_check_in,
                    check_out=api_check_out,
                )
                results.append(AmendSyncResult(
                    provider=provider,
                    external_id=external_id,
                    status=adapter_result.status,
                    message=adapter_result.message,
                ))
            except Exception as exc:
                logger.warning(
                    "amend_sync_trigger: API amend failed for %s/%s: %s",
                    provider, external_id, exc,
                )
                results.append(AmendSyncResult(
                    provider=provider,
                    external_id=external_id,
                    status="failed",
                    message=f"Exception during API amend: {exc}",
                ))
            continue

        # ------------------------------------------------------------------
        # Unknown provider
        # ------------------------------------------------------------------
        logger.warning(
            "amend_sync_trigger: provider %s is not a known amend provider — skipping",
            provider,
        )
        results.append(AmendSyncResult(
            provider=provider,
            external_id=external_id,
            status="skipped",
            message=f"Provider {provider!r} is not a known amend provider.",
        ))

    return results
