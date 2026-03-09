"""
Phase 139 — Adapter Registry

Maps provider names → concrete adapter instances.
Used by outbound_executor.py to look up the right adapter per SyncAction.

Registry rules:
  - api_first providers → ApiFirstAdapter subclass with send()
  - ical_fallback providers → ICalPushAdapter with push()
  - Unknown providers → not in registry → executor keeps dry_run stub

This module is the ONLY place that instantiates adapters.
"""
from __future__ import annotations

from typing import Dict, Optional

from adapters.outbound import OutboundAdapter
from adapters.outbound.airbnb_adapter import AirbnbAdapter
from adapters.outbound.bookingcom_adapter import BookingComAdapter
from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
from adapters.outbound.ical_push_adapter import ICalPushAdapter


def build_adapter_registry() -> Dict[str, OutboundAdapter]:
    """
    Returns dict: provider_name → adapter instance.
    Instantiated fresh on each call (adapters are stateless).
    """
    return {
        # Tier A — api_first
        "airbnb":    AirbnbAdapter(),
        "bookingcom": BookingComAdapter(),
        "expedia":   ExpediaVrboAdapter(provider="expedia"),
        "vrbo":      ExpediaVrboAdapter(provider="vrbo"),

        # Tier B — ical_fallback (push)
        "hotelbeds":   ICalPushAdapter(provider="hotelbeds"),
        "tripadvisor": ICalPushAdapter(provider="tripadvisor"),
        "despegar":    ICalPushAdapter(provider="despegar"),
    }


def get_adapter(provider: str, registry: Optional[Dict[str, OutboundAdapter]] = None) -> Optional[OutboundAdapter]:
    """Return the adapter for a provider, or None if not registered."""
    reg = registry if registry is not None else build_adapter_registry()
    return reg.get(provider)
