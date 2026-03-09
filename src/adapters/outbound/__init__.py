"""
Phase 139 — Outbound Adapter Base Class

All outbound adapters for Phase 139 implement this interface.

An adapter receives a dispatch request and returns an AdapterResult.
It is responsible for:
  1. Reading its own credentials from environment variables.
  2. Making the outbound HTTP call (or iCal push).
  3. Returning a structured AdapterResult.

Adapters must NOT raise exceptions — catch internally and return status='failed'.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class AdapterResult:
    """The result of a single outbound adapter call."""
    provider:     str
    external_id:  str
    strategy:     str   # api_first | ical_fallback
    status:       str   # ok | failed | dry_run
    http_status:  Optional[int]
    message:      str


class OutboundAdapter:
    """
    Abstract base for outbound OTA adapters.
    Subclasses implement send() for api_first or push() for ical_fallback.
    """
    provider: str = "unknown"

    def send(
        self,
        external_id: str,
        booking_id: str,
        rate_limit: int,
        dry_run: bool = False,
    ) -> AdapterResult:
        """
        Send an availability lock to the OTA's write API.
        Override in api_first (Tier A) adapters.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support api_first.")

    def push(
        self,
        external_id: str,
        booking_id: str,
        rate_limit: int,
        dry_run: bool = False,
    ) -> AdapterResult:
        """
        Push an iCal feed update to the OTA.
        Override in ical_fallback (Tier B/C) adapters.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support ical_fallback.")
