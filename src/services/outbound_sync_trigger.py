"""
Phase 137 — Outbound Sync Trigger (Service Layer)

This module computes a `sync_plan` for a given booking by joining:
  1. `property_channel_map`    — which OTA channels exist for this property
  2. `provider_capability_registry` — what each OTA supports (tier, sync_mode)

The output is a deterministic, ordered list of `SyncAction` objects — one per
enabled channel — that tells the outbound executor (Phase 138) what to do for
each provider.

The trigger itself is read-only: it NEVER writes to any table directly.
It only produces a plan. The executor applies it.

SyncAction schema:
    booking_id      TEXT
    property_id     TEXT
    provider        TEXT
    external_id     TEXT
    strategy        TEXT  (api_first | ical_fallback | skip)
    reason          TEXT  (explanation for why this strategy was chosen)
    tier            TEXT  (A | B | C | D)
    rate_limit      INT

Strategy resolution rules (deterministic, no randomness):
    IF channel.enabled = false                  → skip  (disabled in channel map)
    IF channel.sync_mode = 'disabled'           → skip  (explicitly disabled)
    IF channel.sync_mode = 'api_first'
        AND registry.supports_api_write = true  → api_first
        AND registry.supports_api_write = false → ical_fallback (degraded)
    IF channel.sync_mode = 'ical_fallback'
        AND (registry.supports_ical_push OR registry.supports_ical_pull)
                                                → ical_fallback
        AND neither                             → skip
    IF provider not in registry                 → skip  (unknown provider)
    Tier D always                               → skip

Invariants:
    - Pure function: same inputs → same outputs.
    - Never writes to database.
    - apply_envelope is NOT involved.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class SyncAction:
    booking_id:  str
    property_id: str
    provider:    str
    external_id: str
    strategy:    str   # api_first | ical_fallback | skip
    reason:      str
    tier:        Optional[str]
    rate_limit:  int


def _resolve_strategy(
    channel: Dict[str, Any],
    registry_row: Optional[Dict[str, Any]],
) -> tuple[str, str]:
    """
    Returns (strategy, reason) for one channel+registry pair.

    Parameters
    ----------
    channel      : row from property_channel_map
    registry_row : row from provider_capability_registry, or None if not found
    """
    if not channel.get("enabled", True):
        return "skip", "Channel is disabled in property_channel_map."

    sync_mode = channel.get("sync_mode", "api_first")

    if sync_mode == "disabled":
        return "skip", "sync_mode=disabled set on this channel mapping."

    if registry_row is None:
        return "skip", "Provider not found in provider_capability_registry — cannot determine strategy."

    tier = registry_row.get("tier", "D")
    if tier == "D":
        return "skip", f"Provider tier=D — no outbound sync supported (provider={channel.get('provider')})."

    if sync_mode == "api_first":
        if registry_row.get("supports_api_write", False):
            return "api_first", (
                f"sync_mode=api_first and provider supports write API (tier={tier})."
            )
        # Graceful degradation: api_first requested but registry says no write API
        if registry_row.get("supports_ical_push", False) or registry_row.get("supports_ical_pull", True):
            return "ical_fallback", (
                f"sync_mode=api_first but provider does not support write API — degraded to ical_fallback (tier={tier})."
            )
        return "skip", (
            f"sync_mode=api_first but provider supports neither write API nor iCal (tier={tier})."
        )

    if sync_mode == "ical_fallback":
        if registry_row.get("supports_ical_push", False) or registry_row.get("supports_ical_pull", True):
            return "ical_fallback", (
                f"sync_mode=ical_fallback and provider supports iCal (tier={tier})."
            )
        return "skip", (
            f"sync_mode=ical_fallback but provider supports neither iCal push nor pull (tier={tier})."
        )

    # Unrecognised sync_mode — be safe
    return "skip", f"Unknown sync_mode='{sync_mode}' — cannot determine strategy."


def build_sync_plan(
    booking_id: str,
    property_id: str,
    channels: List[Dict[str, Any]],
    registry: Dict[str, Dict[str, Any]],
) -> List[SyncAction]:
    """
    Produce a sync plan for a booking, given:
        channels  — list of rows from property_channel_map for this property/tenant
        registry  — dict keyed by provider name → provider_capability_registry row

    Returns an ordered list of SyncAction (all channels included, even skips).
    The executor (Phase 138) filters by strategy != 'skip' before sending.

    Pure function — deterministic — no DB calls.
    """
    actions: List[SyncAction] = []

    for channel in channels:
        provider = channel.get("provider", "")
        registry_row = registry.get(provider)

        strategy, reason = _resolve_strategy(channel, registry_row)

        tier: Optional[str] = registry_row.get("tier") if registry_row else None
        rate_limit: int = registry_row.get("rate_limit_per_min", 0) if registry_row else 0

        actions.append(SyncAction(
            booking_id=booking_id,
            property_id=property_id,
            provider=provider,
            external_id=channel.get("external_id", ""),
            strategy=strategy,
            reason=reason,
            tier=tier,
            rate_limit=rate_limit,
        ))

    return actions


def summarise_plan(actions: List[SyncAction]) -> Dict[str, Any]:
    """
    Summarise a sync plan for the API response.
    Returns the JSON-serialisable shape used by /internal/sync/trigger.
    """
    return {
        "total_channels":   len(actions),
        "api_first_count":  sum(1 for a in actions if a.strategy == "api_first"),
        "ical_count":       sum(1 for a in actions if a.strategy == "ical_fallback"),
        "skip_count":       sum(1 for a in actions if a.strategy == "skip"),
        "actions": [
            {
                "booking_id":  a.booking_id,
                "property_id": a.property_id,
                "provider":    a.provider,
                "external_id": a.external_id,
                "strategy":    a.strategy,
                "reason":      a.reason,
                "tier":        a.tier,
                "rate_limit":  a.rate_limit,
            }
            for a in actions
        ],
    }
